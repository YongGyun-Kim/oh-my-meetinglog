import socket

import pytest
from meetinglog.db import ApiError


def test_local_only_never_falls_back_even_with_api_key(settings):
    from meetinglog.engines.policy import EnginePolicy, StageUnavailable

    settings.openai_api_key = "not-a-real-key"

    def local():
        raise ApiError("model_not_ready", "모델 준비 필요", 503)

    def forbidden():
        raise AssertionError("local_only must not send to external API")

    with pytest.raises(StageUnavailable) as error:
        EnginePolicy(settings).execute("speech", "local_only", 60000, local, forbidden)
    assert error.value.code == "model_not_ready"


def test_auto_fallback_records_reason_without_marking_quality_passed(settings):
    from meetinglog.engines.policy import EnginePolicy

    settings.openai_api_key = "not-a-real-key"
    policy = EnginePolicy(settings)

    def local():
        raise ApiError("model_not_ready", "모델 준비 필요", 503)

    assert policy.execute("speech", "auto", 60000, local, lambda: "cloud-result") == "cloud-result"
    assert policy.events[-1]["location"] == "api"
    assert policy.events[-1]["fallback_reason"] == "model_not_ready"
    assert policy.events[-1]["quality"] == "unverified"


def test_api_mode_never_calls_local(settings):
    from meetinglog.engines.policy import EnginePolicy

    settings.openai_api_key = "not-a-real-key"

    def forbidden():
        raise AssertionError("explicit API mode must not run local")

    assert (
        EnginePolicy(settings).execute("speech", "api", 1000, forbidden, lambda: "result")
        == "result"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://192.168.0.2:11434",
        "http://localhost.evil.test:11434",
        "http://user:password@localhost:11434",
    ],
)
def test_remote_ollama_endpoints_are_rejected(url):
    from meetinglog.engines.policy import assert_loopback_endpoint

    with pytest.raises(ApiError):
        assert_loopback_endpoint(url)


def test_localhost_dns_rebinding_is_rejected(monkeypatch):
    from meetinglog.engines.policy import assert_loopback_endpoint

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.8", 11434))
        ],
    )
    with pytest.raises(ApiError):
        assert_loopback_endpoint("http://localhost:11434")


def test_only_transient_failures_are_retried_and_cancellation_interrupts_wait():
    from meetinglog.engines.retries import retry

    attempts, sleeps = [], []

    def transient():
        attempts.append(1)
        if len(attempts) < 3:
            raise ApiError("upstream_429", "일시 오류", 503, True)
        return "ok"

    assert retry(transient, sleep=sleeps.append) == "ok"
    assert len(attempts) == 3
    assert sleeps
    attempts.clear()

    def authentication():
        attempts.append(1)
        raise ApiError("upstream_401", "인증 오류", 503, False)

    with pytest.raises(ApiError):
        retry(authentication, sleep=sleeps.append)
    assert len(attempts) == 1
    with pytest.raises(ApiError) as error:
        retry(transient, sleep=sleeps.append, cancelled=lambda: True)
    assert error.value.code == "job_cancelled"


def test_api_attempt_is_durable_before_call_even_when_request_fails(settings, tmp_path):
    import json

    from meetinglog.engines.policy import EnginePolicy

    settings.openai_api_key = "test-only"
    policy = EnginePolicy(settings)
    policy.event_path = tmp_path / "events.jsonl"

    def cloud():
        assert policy.event_path.is_file()
        event = json.loads(policy.event_path.read_text().splitlines()[-1])
        assert event["event"] == "request_started" and event["attempt"] == 1
        raise ApiError("upstream_401", "인증 오류", 503)

    with pytest.raises(ApiError):
        policy.execute("speech", "api", 0, lambda: None, cloud)
    assert "request_started" in policy.event_path.read_text()
