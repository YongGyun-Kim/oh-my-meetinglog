import json
import os
import sys
from pathlib import Path

import pytest

from tests.analysis_fixtures import form_analysis_fixture, transcript_fixture


@pytest.fixture
def executable(tmp_path, monkeypatch):
    directory = tmp_path / "bin"
    directory.mkdir()
    log = tmp_path / "call.json"
    body = form_analysis_fixture().model_dump_json()
    script = f"""#!{sys.executable}
import json, os, pathlib, sys, time
provider=pathlib.Path(sys.argv[0]).name
if sys.argv[1:] in (["login","status"], ["auth","status","--json"]):
 print("Logged in using ChatGPT" if provider=="codex" else json.dumps({{"loggedIn":True,"authMethod":"claude.ai"}}))
 sys.exit(0)
if 'app-server' in sys.argv or '--input-format' in sys.argv:
 for line in sys.stdin:
  msg=json.loads(line)
  if provider=='codex':
   if msg['method']=='initialized': continue
   response={{}} if msg['method']=='initialize' else {{"data":[{{"model":"test-model","displayName":"Test","isDefault":True,"supportedReasoningEfforts":[{{"reasoningEffort":"high"}}]}}],"nextCursor":None}}
   print(json.dumps({{"id":msg["id"],"result":response}}),flush=True)
  else:
   print(json.dumps({{"type":"control_response","response":{{"subtype":"success","request_id":msg["request_id"],"response":{{"models":[{{"value":"test-model","displayName":"Test","supportsEffort":True,"supportedEffortLevels":["high"]}}]}}}}}}),flush=True)
 sys.exit(0)
pathlib.Path({str(log)!r}).write_text(json.dumps({{"args":sys.argv[1:],"cwd":os.getcwd(),"prompt":sys.stdin.read(),"pid":os.getpid()}}))
mode = os.environ.get('TEST_CLI_MODE', '')
if mode == 'timeout': time.sleep(60)
if mode == 'timeout-child':
 import subprocess
 child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'])
 call = json.loads(pathlib.Path({str(log)!r}).read_text())
 call['child_pid'] = child.pid
 pathlib.Path({str(log)!r}).write_text(json.dumps(call))
 time.sleep(60)
if mode == 'error':
 print('secret-credential',file=sys.stderr)
 sys.exit(1)
if pathlib.Path(sys.argv[0]).name == 'codex':
 schema = json.loads(pathlib.Path(sys.argv[sys.argv.index('--output-schema')+1]).read_text())
 def strict(value):
  if isinstance(value, dict):
   if 'properties' in value: assert set(value.get('required', [])) == set(value['properties'])
   for child in value.values(): strict(child)
  elif isinstance(value,list):
   for child in value: strict(child)
 strict(schema)
 pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text({body!r} if mode != 'invalid' else 'not json')
else:
 print(json.dumps({{"is_error":False,"structured_output":json.loads({body!r}),"modelUsage":{{"actual-model":{{}}}}}}) if mode != 'invalid' else 'not json')
"""
    for name in ("codex", "claude"):
        path = directory / name
        path.write_text(script)
        path.chmod(0o700)
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ["PATH"])
    return log


@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_cli_uses_stdin_schema_selected_model_and_no_user_tools(executable, provider):
    from meetinglog.analysis.input import prepare_input
    from meetinglog.domain import AnalysisSettings
    from meetinglog.engines.cli_analysis import CliAnalysis

    engine = CliAnalysis(AnalysisSettings(provider=provider, model="test-model", reasoning="high"))
    body = engine.generate(prepare_input(transcript_fixture())[0])
    assert body.sections[0].title == "회의 결과"
    call = json.loads(executable.read_text())
    assert "test-model" in call["args"] and "high" in " ".join(call["args"])
    assert "언제 서비스를" in call["prompt"] and "언제 서비스를" not in " ".join(call["args"])
    assert not os.path.exists(call["cwd"])
    if provider == "codex":
        assert "--ignore-user-config" in call["args"] and "read-only" in call["args"]
        assert "features.shell_tool=false" in call["args"]
    else:
        assert "--safe-mode" in call["args"] and "--tools" in call["args"]
        assert call["args"][call["args"].index("--tools") + 1] == ""
        assert "--no-session-persistence" in call["args"]


@pytest.mark.parametrize("mode", ["error", "invalid", "timeout"])
def test_cli_failure_does_not_leak_output_and_terminates(executable, monkeypatch, mode):
    import meetinglog.engines.cli_analysis as module
    from meetinglog.analysis.input import prepare_input
    from meetinglog.db import ApiError
    from meetinglog.domain import AnalysisSettings

    monkeypatch.setenv("TEST_CLI_MODE", mode)
    monkeypatch.setattr(module, "CLI_TIMEOUT", 1 if mode == "timeout" else 5)
    with pytest.raises(ApiError) as error:
        module.CliAnalysis(
            AnalysisSettings(provider="claude", model="", reasoning="default")
        ).generate(prepare_input(transcript_fixture())[0])
    assert (
        error.value.code
        == {
            "error": "cli_analysis_failed",
            "invalid": "invalid_cli_output",
            "timeout": "cli_timeout",
        }[mode]
    )
    assert "secret-credential" not in str(error.value)
    call = json.loads(executable.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(call["pid"], 0)


def test_worker_cancellation_reaps_cli_process(executable, tmp_path, monkeypatch):
    from meetinglog.db import ApiError
    from meetinglog.domain import StageRequest
    from meetinglog.jobs.process import ProcessRunner

    monkeypatch.setenv("TEST_CLI_MODE", "timeout")
    script = """from meetinglog.engines.cli_analysis import CliAnalysis
from meetinglog.domain import AnalysisSettings
from meetinglog.analysis.input import AnalysisInput
import sys
from pathlib import Path
CliAnalysis(AnalysisSettings(provider="claude",model="",reasoning="default"), workspace=Path(sys.argv[1])).generate(AnalysisInput(speakers=[],lines=[]))"""
    request = StageRequest(
        job_id="j",
        recording_id="r",
        generation=0,
        stage="analysis",
        input_path="in",
        output_path=str(tmp_path / "out.json"),
        mode="local_only",
    )
    runner = ProcessRunner(
        lambda r: [
            sys.executable,
            "-c",
            script,
            str(Path(r.output_path).with_suffix(".workspace")),
        ],
        cancelled=lambda: executable.exists(),
    )
    with pytest.raises(ApiError) as error:
        runner.run(request, 10)
    assert error.value.code == "job_cancelled"
    call = json.loads(executable.read_text())
    pid = call["pid"]

    assert not Path(call["cwd"]).exists()
    import time

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.02)
    else:
        pytest.fail("CLI remains after job cancellation")


@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_saved_cli_choice_runs_through_real_worker_and_exports(
    settings, db, tmp_path, executable, provider
):
    from meetinglog.jobs.runner import Worker

    from tests.api_fixtures import populated_client

    client, record_id, transcript = populated_client(settings, db, tmp_path)
    try:
        assert (
            client.patch(
                "/api/settings/analysis",
                json={"provider": provider, "model": "test-model", "reasoning": "high"},
            ).status_code
            == 200
        )
        response = client.post(
            f"/api/recordings/{record_id}/analyze",
            json={"transcript_id": transcript.id, "mode": "local_only", "form": "meeting"},
        )
        assert response.status_code == 200
        with Worker(settings, db) as worker:
            assert worker.run_once()
        detail = client.get(f"/api/recordings/{record_id}").json()
        assert detail["analysis"]["provider"] == provider
        assert detail["analysis"]["reasoning"] == "high"
        result = client.get(f"/api/recordings/{record_id}/export?format=json").json()
        assert result["analysis"]["provider"] == provider
        assert result["analysis"]["body"]["sections"]
    finally:
        client.__exit__(None, None, None)


def test_stage_timeout_reaps_cli_descendants_and_removes_workspace(
    executable, tmp_path, monkeypatch
):
    import time

    from meetinglog.db import ApiError
    from meetinglog.domain import StageRequest
    from meetinglog.jobs.process import ProcessRunner

    monkeypatch.setenv("TEST_CLI_MODE", "timeout-child")
    script = """import meetinglog.engines.cli_analysis as module
from meetinglog.domain import AnalysisSettings
from meetinglog.analysis.input import AnalysisInput
module.CLI_TIMEOUT=1
import sys
from pathlib import Path
module.CliAnalysis(AnalysisSettings(provider="claude",model="",reasoning="default"), workspace=Path(sys.argv[1])).generate(AnalysisInput(speakers=[],lines=[]))"""
    request = StageRequest(
        job_id="j",
        recording_id="r",
        generation=0,
        stage="analysis",
        input_path="in",
        output_path=str(tmp_path / "out.json"),
        mode="local_only",
    )
    runner = ProcessRunner(
        lambda r: [sys.executable, "-c", script, str(Path(r.output_path).with_suffix(".workspace"))]
    )
    with pytest.raises(ApiError):
        runner.run(request, 10)
    call = json.loads(executable.read_text())
    try:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                os.kill(call["child_pid"], 0)
            except ProcessLookupError:
                break
            time.sleep(0.02)
        else:
            pytest.fail("CLI child remains after internal timeout")
        assert not Path(call["cwd"]).exists()
    finally:
        import signal

        try:
            os.kill(call["child_pid"], signal.SIGKILL)
        except ProcessLookupError:
            pass
