import json
import os
import signal
import sys
import time

import pytest


@pytest.fixture
def catalog_cli(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    state = tmp_path / "catalog.json"
    state.write_text(
        json.dumps(
            {
                "codex": [
                    {
                        "model": "alpha",
                        "displayName": "Alpha",
                        "isDefault": True,
                        "defaultReasoningEffort": "low",
                        "supportedReasoningEfforts": [
                            {"reasoningEffort": "low"},
                            {"reasoningEffort": "high"},
                        ],
                    },
                    {
                        "model": "beta",
                        "displayName": "Beta",
                        "isDefault": False,
                        "defaultReasoningEffort": "medium",
                        "supportedReasoningEfforts": [{"reasoningEffort": "medium"}],
                    },
                ],
                "claude": [
                    {
                        "value": "default",
                        "resolvedModel": "actual[1m]",
                        "displayName": "Default",
                        "supportsEffort": True,
                        "supportedEffortLevels": ["low", "high"],
                    },
                    {
                        "value": "sonnet",
                        "resolvedModel": "actual-sonnet",
                        "displayName": "Sonnet",
                        "supportsEffort": False,
                    },
                ],
            }
        )
    )
    script = f"""#!{sys.executable}
import json,os,pathlib,sys,time,subprocess
root=pathlib.Path({str(tmp_path)!r})
provider=pathlib.Path(sys.argv[0]).name
if sys.argv[1:] in (['login','status'],['auth','status','--json']):
 connected=os.environ.get('CATALOG_AUTH')!='logged_out'
 if provider=='codex': print('Logged in using ChatGPT' if connected else 'Not logged in',file=sys.stderr)
 else: print(json.dumps({{"loggedIn":connected,"authMethod":"claude.ai","accessToken":"do-not-leak"}}))
 sys.exit(0 if connected else 1)
(root/'pid').write_text(str(os.getpid()))
mode=os.environ.get('CATALOG_MODE','')
if mode=='timeout':
 child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
 (root/'child-pid').write_text(str(child.pid))
 time.sleep(60)
if mode=='scalar':
 print('[]',flush=True);sys.exit(0)
rows=json.loads((root/'catalog.json').read_text())[provider]
for line in sys.stdin:
 msg=json.loads(line)
 with (root/'requests.jsonl').open('a') as out: out.write(json.dumps(msg)+'\\n')
 if mode=='invalid': print('{{}}',flush=True);continue
 if provider=='codex':
  if msg['method']=='initialized': continue
  result={{}} if msg['method']=='initialize' else {{'data':rows[1:] if msg.get('params',{{}}).get('cursor') else rows[:1], 'nextCursor':None if msg.get('params',{{}}).get('cursor') else 'page2'}}
  print(json.dumps({{'id':msg['id'],'error':{{'message':'do-not-leak'}}}}) if mode=='error' else json.dumps({{'id':msg['id'],'result':result}}),flush=True)
 else:
  print(json.dumps({{'type':'control_response','response':{{'subtype':'success','request_id':msg['request_id'],'response':{{'models':rows,'account':{{'token':'do-not-leak'}}}}}}}}),flush=True)
"""
    for name in ("codex", "claude"):
        p = bin_dir / name
        p.write_text(script)
        p.chmod(0o700)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    return tmp_path


def test_codex_catalog_reads_all_pages_and_per_model_efforts(catalog_cli, settings):
    from meetinglog.analysis.settings import options

    result = options("codex", "beta", settings)
    assert result.models == ["alpha", "beta"]
    assert result.default_model == "alpha"
    assert result.reasoning == ["default", "medium"]
    assert result.catalog[0].reasoning == ["low", "high"]
    assert result.catalog[0].default_reasoning == "low"
    assert "do-not-leak" not in result.model_dump_json()
    requests = [json.loads(s) for s in (catalog_cli / "requests.jsonl").read_text().splitlines()]
    assert [s["method"] for s in requests] == [
        "initialize",
        "initialized",
        "model/list",
        "model/list",
    ]
    assert requests[-1]["params"]["cursor"] == "page2"


def test_claude_catalog_uses_initialize_models_and_supports_context_aliases(catalog_cli, settings):
    from meetinglog.analysis.settings import options

    result = options("claude", "actual[1m]", settings)
    assert result.models == ["default", "sonnet"]
    assert result.reasoning == ["default", "low", "high"]
    assert result.catalog[0].aliases == ["actual[1m]"]
    assert options("claude", "sonnet", settings).reasoning == ["default"]
    assert "do-not-leak" not in result.model_dump_json()
    req = json.loads((catalog_cli / "requests.jsonl").read_text().splitlines()[0])
    assert req["request"]["subtype"] == "initialize"
    assert not any(s.get("type") == "user" for s in [req])


def test_logged_out_cli_does_not_expose_fallback_catalog(catalog_cli, settings, monkeypatch):
    from meetinglog.analysis.settings import options

    monkeypatch.setenv("CATALOG_AUTH", "logged_out")
    result = options("claude", "", settings)
    assert result.models == [] and result.reasoning == ["default"]
    assert result.message and "로그인" in result.message
    assert not (catalog_cli / "pid").exists()


def test_catalog_timeout_kills_process_group_and_returns_safe_message(
    catalog_cli, settings, monkeypatch
):
    from meetinglog.analysis import cli_catalog
    from meetinglog.analysis.settings import options

    monkeypatch.setenv("CATALOG_MODE", "timeout")
    monkeypatch.setattr(cli_catalog, "CATALOG_TIMEOUT", 1)
    result = options("codex", "", settings)
    assert result.models == [] and result.message
    deadline = time.monotonic() + 2
    for pid_file in ("pid", "child-pid"):
        pid = int((catalog_cli / pid_file).read_text())
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.02)
        else:
            os.kill(pid, signal.SIGKILL)
            pytest.fail("Catalog subprocess still alive")


def test_server_rejects_unadvertised_model_effort(catalog_cli, settings):
    from fastapi.testclient import TestClient
    from meetinglog.app import create_app

    with TestClient(create_app(settings), base_url="http://localhost:8765") as client:
        path = "/api/settings/analysis"
        assert (
            client.patch(
                path, json={"provider": "codex", "model": "beta", "reasoning": "high"}
            ).status_code
            == 422
        )
        assert (
            client.patch(
                path, json={"provider": "codex", "model": "beta", "reasoning": "medium"}
            ).status_code
            == 200
        )
        assert (
            client.patch(
                path, json={"provider": "claude", "model": "actual[1m]", "reasoning": "high"}
            ).status_code
            == 200
        )
        assert (
            client.patch(
                path, json={"provider": "claude", "model": "sonnet", "reasoning": "high"}
            ).status_code
            == 422
        )


def test_control_error_does_not_leak_cli_message_or_offer_guessed_models(
    catalog_cli, settings, monkeypatch
):
    from meetinglog.analysis.settings import options

    monkeypatch.setenv("CATALOG_MODE", "error")
    result = options("codex", "alpha", settings)
    assert result.models == [] and result.catalog == []
    assert result.reasoning == ["default"]
    assert "do-not-leak" not in result.model_dump_json()
    pid = int((catalog_cli / "pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_missing_effort_metadata_is_not_replaced_with_a_fixed_list(catalog_cli, settings):
    from meetinglog.analysis.settings import options

    path = catalog_cli / "catalog.json"
    data = json.loads(path.read_text())
    data["claude"][0].pop("supportedEffortLevels")
    path.write_text(json.dumps(data))
    result = options("claude", "default", settings)
    assert result.reasoning == ["default"]


def test_malformed_control_shape_returns_safe_failure(catalog_cli, settings, monkeypatch):
    from meetinglog.analysis.settings import options

    monkeypatch.setenv("CATALOG_MODE", "scalar")
    result = options("codex", "", settings)
    assert result.models == [] and result.message


def test_control_output_limit_is_enforced(catalog_cli, settings, monkeypatch):
    from meetinglog.analysis import cli_catalog
    from meetinglog.analysis.settings import options

    monkeypatch.setattr(cli_catalog, "MAX_OUTPUT_BYTES", 8)
    result = options("codex", "", settings)
    assert result.models == [] and result.message
