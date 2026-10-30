import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from fastapi.testclient import TestClient
from meetinglog.app import create_app

SECRET = "cli-secret-must-not-leak"


@pytest.fixture
def cli(tmp_path, monkeypatch):
    directory = tmp_path / "bin"
    directory.mkdir()
    state = tmp_path / "cli-state.json"
    state.write_text("{}")
    script = f"""#!{sys.executable}
import json, os, pathlib, sys, time
directory = pathlib.Path({str(tmp_path)!r})
provider = pathlib.Path(sys.argv[0]).name
state = json.loads((directory / "cli-state.json").read_text())
options = state.get(provider, {{}})
status = sys.argv[1:] in (["login", "status"], ["auth", "status", "--json"])
if status:
    if options.get("hang"):
        time.sleep(30)
    if options.get("error"):
        print({SECRET!r}, file=sys.stderr)
        sys.exit(2)
    if options.get("malformed"):
        print("not JSON")
        sys.exit(0)
    connected = options.get("connected", False) or (directory / (provider + "-connected")).exists()
    if provider == "codex":
        print(("Logged in using an API key - " + {SECRET!r}) if options.get("api_key") else
              ("Logged in using ChatGPT" if connected else "Not logged in"), file=sys.stderr)
    else:
        print(json.dumps({{"loggedIn": connected, "authMethod": "claude.ai" if connected else "none",
                          "accessToken": {SECRET!r}, "email": "private@example.test"}}))
    sys.exit(0 if connected else 1)
with (directory / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps({{"provider": provider, "args": sys.argv[1:], "pid": os.getpid()}}) + "\\n")
print({SECRET!r}, flush=True)
print("https://login.example.test/?code=" + {SECRET!r}, file=sys.stderr, flush=True)
if options.get("fail_login"):
    sys.exit(3)
while not (directory / (provider + "-complete")).exists():
    time.sleep(0.01)
(directory / (provider + "-connected")).touch()
"""
    for provider in ("codex", "claude"):
        executable = directory / provider
        executable.write_text(script)
        executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ.get("PATH", ""))
    return tmp_path


@pytest.fixture
def client(settings, cli):
    with TestClient(
        create_app(settings),
        base_url="http://localhost:8765",
        headers={"origin": "http://localhost:5173"},
    ) as client:
        yield client


def connection(client, provider):
    response = client.get("/api/settings/cli-connections")
    assert response.status_code == 200
    assert SECRET not in response.text
    assert "private@example.test" not in response.text
    return next(item for item in response.json() if item["provider"] == provider)


def wait_for(check):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.02)
    pytest.fail("CLI state did not settle")


def post(client, provider, operation="login", **body):
    return client.post(f"/api/settings/cli-connections/{provider}/{operation}", json=body)


def test_reports_cli_status_without_returning_credentials(client, cli):
    (cli / "cli-state.json").write_text(json.dumps({"codex": {"connected": True, "api_key": True}}))
    assert connection(client, "codex")["state"] == "connected"
    assert connection(client, "codex")["auth_method"] == "api_key"
    assert connection(client, "claude")["state"] == "logged_out"


def test_missing_cli_is_not_treated_as_logged_out(client, monkeypatch):
    monkeypatch.setenv("PATH", "")
    assert connection(client, "codex")["state"] == "not_installed"
    assert post(client, "codex").status_code == 409


@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_login_starts_official_command_and_rechecks_completion(client, cli, provider):
    response = post(client, provider)
    assert response.status_code == 200
    assert response.json()["state"] == "logging_in"
    assert SECRET not in response.text
    wait_for(lambda: (cli / "calls.jsonl").exists())
    call = json.loads((cli / "calls.jsonl").read_text().splitlines()[0])
    assert call["args"] == (["login"] if provider == "codex" else ["auth", "login", "--claudeai"])
    (cli / f"{provider}-complete").touch()
    wait_for(lambda: connection(client, provider)["state"] == "connected")
    assert connection(client, provider)["auth_method"] == "account"


def test_duplicate_login_and_cancel_do_not_overwrite_a_new_attempt(client, cli):
    assert post(client, "codex").json()["state"] == "logging_in"
    wait_for(lambda: (cli / "calls.jsonl").exists())
    assert post(client, "codex").json()["state"] == "logging_in"
    assert len((cli / "calls.jsonl").read_text().splitlines()) == 1
    assert post(client, "codex", "cancel").json()["state"] == "logged_out"
    assert post(client, "codex").json()["state"] == "logging_in"
    (cli / "codex-complete").touch()
    wait_for(lambda: connection(client, "codex")["state"] == "connected")


def test_connected_account_is_kept_without_starting_login(client, cli):
    (cli / "codex-connected").touch()
    assert post(client, "codex").json()["state"] == "connected"
    assert not (cli / "calls.jsonl").exists()


def test_concurrent_login_does_not_restart_an_account_connected_during_status_check(
    client, cli, monkeypatch
):
    auth = client.app.state.cli_auth
    probe = auth._probe
    checking, release = Event(), Event()

    def delayed_probe(provider):
        result = probe(provider)
        if not checking.is_set():
            checking.set()
            assert release.wait(4)
        return result

    monkeypatch.setattr(auth, "_probe", delayed_probe)
    with ThreadPoolExecutor(max_workers=2) as requests:
        first = requests.submit(post, client, "codex")
        assert checking.wait(2)
        second = requests.submit(post, client, "codex")
        try:
            try:
                second.result(timeout=1)
            except TimeoutError:
                pass
            else:
                (cli / "codex-complete").touch()
                wait_for(lambda: connection(client, "codex")["state"] == "connected")
        finally:
            release.set()
        assert first.result().status_code == second.result().status_code == 200
    (cli / "codex-complete").touch()
    wait_for(lambda: connection(client, "codex")["state"] == "connected")
    assert len((cli / "calls.jsonl").read_text().splitlines()) == 1


def test_login_failure_is_reported_without_cli_output(client, cli):
    (cli / "cli-state.json").write_text(json.dumps({"claude": {"fail_login": True}}))
    post(client, "claude")
    wait_for(lambda: connection(client, "claude")["state"] == "error")
    assert connection(client, "claude")["message"]


def test_login_timeout_terminates_the_process(client, cli, monkeypatch):
    import meetinglog.cli_auth as auth

    monkeypatch.setattr(auth, "LOGIN_TIMEOUT", 0.1)
    post(client, "codex")
    wait_for(lambda: connection(client, "codex")["state"] == "error")
    call = json.loads((cli / "calls.jsonl").read_text().splitlines()[0])
    with pytest.raises(ProcessLookupError):
        os.kill(call["pid"], 0)


@pytest.mark.parametrize("options", [{"error": True}, {"hang": True}, {"malformed": True}])
def test_status_failure_is_not_reported_as_logged_out(client, cli, monkeypatch, options):
    import meetinglog.cli_auth as auth

    monkeypatch.setattr(auth, "STATUS_TIMEOUT", 0.1)
    (cli / "cli-state.json").write_text(json.dumps({"claude": options}))
    assert connection(client, "claude")["state"] == "error"


def test_shutdown_terminates_pending_login(settings, cli):
    with TestClient(
        create_app(settings),
        base_url="http://localhost:8765",
        headers={"origin": "http://localhost:5173"},
    ) as client:
        post(client, "claude")
        wait_for(lambda: (cli / "calls.jsonl").exists())
        call = json.loads((cli / "calls.jsonl").read_text().splitlines()[0])
    with pytest.raises(ProcessLookupError):
        os.kill(call["pid"], 0)


def test_login_rejects_unknown_commands_and_requests_without_trusted_origin(client, cli):
    assert post(client, "gemini").status_code == 422
    assert post(client, "codex", command="echo", args=[SECRET]).status_code == 422
    client.headers.pop("origin")
    assert post(client, "codex").status_code == 403
    assert (
        client.post(
            "/api/settings/cli-connections/codex/login",
            json={},
            headers={"origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert not (cli / "calls.jsonl").exists()
