import json

import httpx
import pytest
from fastapi.testclient import TestClient
from meetinglog.app import create_app

from tests.analysis_fixtures import form_analysis_fixture, transcript_fixture


def test_analysis_preferences_persist_without_changing_speech_mode(settings, monkeypatch):
    from meetinglog.analysis import settings as analysis_module
    from meetinglog.analysis.cli_catalog import ModelOption

    monkeypatch.setattr(
        analysis_module,
        "cli_models",
        lambda provider: (
            [ModelOption(id="test-model", name="Test", reasoning=["high"])],
            "test-model",
        ),
    )
    settings.ollama_url = "http://127.0.0.1:1"
    with TestClient(create_app(settings), base_url="http://localhost:8765") as client:
        original = client.get("/api/settings").json()["mode"]
        result = client.patch(
            "/api/settings/analysis",
            json={"provider": "codex", "model": "test-model", "reasoning": "high"},
        )
        assert result.status_code == 200
        assert client.get("/api/settings").json()["mode"] == original
        assert (
            client.patch(
                "/api/settings/analysis",
                json={"provider": "codex", "model": "--bad", "reasoning": "high", "command": "sh"},
            ).status_code
            == 422
        )
        assert (
            client.patch(
                "/api/settings/analysis",
                json={"provider": "ollama", "model": "gpt-oss:20b", "reasoning": "off"},
            ).status_code
            == 422
        )
    with TestClient(create_app(settings), base_url="http://localhost:8765") as client:
        assert client.get("/api/settings/analysis").json() == {
            "provider": "codex",
            "model": "test-model",
            "reasoning": "high",
        }


def test_saved_local_preferences_reach_model_and_do_not_fallback(settings, db, monkeypatch):
    from meetinglog.analysis.service import AnalysisService
    from meetinglog.engines import local_analysis

    with db.session(immediate=True) as connection:
        connection.execute(
            "INSERT INTO settings(key,value) VALUES('analysis',?)",
            (json.dumps({"provider": "ollama", "model": "gpt-oss:120b", "reasoning": "high"}),),
        )
    seen = []
    fail = False

    def handler(request):
        if request.url.path == "/api/chat":
            data = json.loads(request.content)
            seen.append(data)
            if fail:
                return httpx.Response(503)
            return httpx.Response(
                200, json={"message": {"content": form_analysis_fixture().model_dump_json()}}
            )
        return httpx.Response(200, json={})

    client_type = httpx.Client
    monkeypatch.setattr(
        local_analysis.httpx,
        "Client",
        lambda **kwargs: client_type(
            base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handler)
        ),
    )
    result = AnalysisService(db, settings).generate_from(transcript_fixture(), "api")
    assert result.provider == "ollama" and result.model == "gpt-oss:120b"
    assert result.reasoning == "high"
    assert seen[0]["model"] == "gpt-oss:120b" and seen[0]["think"] == "high"
    fail = True
    from meetinglog.db import ApiError

    with pytest.raises(ApiError):
        AnalysisService(db, settings).generate_from(transcript_fixture(), "auto")


def test_worker_freezes_analysis_choice_and_does_not_api_fallback(
    settings, db, monkeypatch, tmp_path
):
    from meetinglog.db import ApiError
    from meetinglog.domain import Job
    from meetinglog.jobs.process import ProcessRunner
    from meetinglog.jobs.runner import Worker

    settings.openai_api_key = "never-use-this"
    with db.session(immediate=True) as c:
        c.execute(
            "INSERT INTO settings(key,value) VALUES('analysis',?)",
            (json.dumps({"provider": "codex", "model": "chosen", "reasoning": "high"}),),
        )
    requests = []

    def run(self, request, timeout):
        requests.append(request)
        with db.session(immediate=True) as c:
            c.execute(
                "UPDATE settings SET value=? WHERE key='analysis'",
                (json.dumps({"provider": "claude", "model": "opus", "reasoning": "low"}),),
            )
        raise ApiError("stage_timeout", "timed out", 503)

    monkeypatch.setattr(ProcessRunner, "run", run)
    worker = Worker(settings, db)
    monkeypatch.setattr(worker.repository, "raw", lambda _: {"attempts": 1})
    job = Job(
        id="j",
        recording_id="11111111-1111-4111-8111-111111111111",
        kind="analyze",
        state="running",
        stage="analysis",
        generation=0,
        mode="auto",
    )
    with pytest.raises(ApiError, match="timed out"):
        worker._stage(job, "analysis", str(tmp_path / "transcript.json"), 1000)
    assert len(requests) == 1
    assert requests[0].analysis_settings.model == "chosen"
    assert requests[0].analysis_settings.provider == "codex"


def test_ollama_options_use_capabilities_and_keep_endpoint_server_controlled(settings, monkeypatch):
    from meetinglog.analysis.settings import options

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen:8b"}]})
        assert json.loads(request.content) == {"model": "qwen:8b"}
        return httpx.Response(200, json={"capabilities": ["completion", "thinking"]})

    client_type = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client_type(
            base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handler)
        ),
    )
    result = options("ollama", "qwen:8b", settings)
    assert result.models == ["qwen:8b"]
    assert result.reasoning == ["default", "off", "on"]


def test_openai_selected_model_and_effort_reach_sdk(settings, db, monkeypatch):
    from types import SimpleNamespace

    import openai
    from meetinglog.analysis.service import AnalysisService
    from meetinglog.domain import AnalysisSettings

    seen = []

    def parse(**kwargs):
        seen.append(kwargs)
        return SimpleNamespace(output_parsed=form_analysis_fixture())

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse), close=lambda: None)
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: client)
    settings.openai_api_key = "test-key"
    version = AnalysisService(db, settings).generate_from(
        transcript_fixture(),
        "local_only",
        analysis_settings=AnalysisSettings(
            provider="openai", model="chosen-model", reasoning="high"
        ),
    )
    assert version.provider == "openai" and version.reasoning == "high"
    assert seen[0]["model"] == "chosen-model"
    assert seen[0]["reasoning"] == {"effort": "high"}
