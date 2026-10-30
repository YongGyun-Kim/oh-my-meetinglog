import hashlib
import ipaddress
import json
import socket
from collections.abc import Callable
from typing import Literal, TypeVar
from urllib.parse import urlsplit, urlunsplit

from pydantic import model_validator

from meetinglog.config import Settings
from meetinglog.db import ApiError
from meetinglog.domain import Contract, Mode
from meetinglog.engines.models import ModelRegistry
from meetinglog.engines.retries import retry
from meetinglog.recordings.storage import atomic_json

T = TypeVar("T")


class StageUnavailable(ApiError):
    pass


class QualityProfile(Contract):
    stage: str
    status: Literal["unverified", "passed", "failed"]
    model_revision: str
    report_id: str | None = None

    @model_validator(mode="after")
    def require_evidence(self):
        if self.status != "unverified" and not self.report_id:
            raise ValueError("실제 평가 보고서가 필요합니다")
        return self


def assert_loopback_endpoint(url: str) -> None:
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError
        addresses = socket.getaddrinfo(
            parsed.hostname, parsed.port or 11434, type=socket.SOCK_STREAM
        )
        if not addresses or any(
            not ipaddress.ip_address(address[4][0]).is_loopback for address in addresses
        ):
            raise ValueError
    except (ValueError, OSError) as error:
        raise ApiError(
            "nonlocal_endpoint", "Ollama는 이 맥북의 로컬 주소만 사용할 수 있습니다", 503
        ) from error


def loopback_url(url: str) -> str:
    assert_loopback_endpoint(url)
    parsed = urlsplit(url)
    host = "[::1]" if parsed.hostname == "::1" else "127.0.0.1"
    return urlunsplit(("http", f"{host}:{parsed.port or 11434}", "", "", ""))


def stage_timeout_seconds(stage: str, duration_ms: int) -> float:
    seconds = duration_ms / 1000
    return max(300, seconds * 0.25) if stage == "analysis" else max(180, seconds * 0.5)


class EnginePolicy:
    def __init__(self, settings: Settings, revisions: dict | None = None, *, event_path=None):
        self.settings = settings
        self.events = []
        self.event_path = event_path
        manifest = ModelRegistry(settings).read().get("models", {})
        speech_revision = hashlib.sha256(
            json.dumps(
                {
                    name: manifest.get(name, {}).get("revision")
                    for name in ("asr", "aligner", "vad", "diarizer")
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        self.revisions = {"speech": speech_revision, **(revisions or {})}

    def record(self, event: dict):
        self.events.append(event)
        if self.event_path is not None:
            from meetinglog.jobs.events import append_event

            append_event(self.event_path, event)

    def profile(self, stage: str) -> QualityProfile | None:
        try:
            data = json.loads((self.settings.data_dir / "quality-profiles.json").read_text())
            profile = QualityProfile.model_validate(data[stage])
            if profile.model_revision != self.revisions.get(stage):
                return None
            if (
                profile.report_id
                and not (
                    self.settings.data_dir / "evaluations" / f"{profile.report_id}.json"
                ).is_file()
            ):
                return None
            return profile
        except (OSError, ValueError, KeyError):
            return None

    def save_profile(self, profile: QualityProfile):
        if profile.status != "unverified":
            report = self.settings.data_dir / "evaluations" / f"{profile.report_id}.json"
            if not report.is_file():
                raise ApiError("missing_evidence", "평가 보고서가 필요합니다")
        path = self.settings.data_dir / "quality-profiles.json"
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        data[profile.stage] = profile.model_dump()
        atomic_json(path, data)

    def execute(
        self,
        stage: Literal["speech", "analysis"],
        mode: Mode,
        duration_ms: int,
        local: Callable[[], T],
        cloud: Callable[[], T],
    ) -> T:
        profile = self.profile(stage)
        quality = profile.status if profile else "unverified"
        reason = None
        if mode != "api" and not (
            mode == "auto" and quality == "failed" and self.settings.openai_api_key
        ):
            try:
                self.record(
                    {
                        "stage": stage,
                        "event": "local_started",
                        "location": "local",
                        "quality": quality,
                    }
                )
                result = local()
                self.record(
                    {
                        "event": "engine_result",
                        "stage": stage,
                        "location": "local",
                        "quality": quality,
                        "fallback_reason": None,
                    }
                )
                return result
            except Exception as error:
                safe = (
                    error
                    if isinstance(error, ApiError)
                    else ApiError(
                        "local_engine_failed",
                        "로컬 처리에 실패했습니다. 모델 준비와 실행 환경을 확인하세요",
                        503,
                    )
                )
                if safe.code == "job_cancelled":
                    raise safe from None
                if mode == "local_only" or not self.settings.openai_api_key:
                    raise StageUnavailable(
                        safe.code, safe.message, safe.status, safe.retryable
                    ) from None
                reason = safe.code
        elif mode == "auto":
            reason = "local_quality_failed"
        if not self.settings.openai_api_key:
            raise StageUnavailable("api_not_configured", "서버에 외부 API 키를 설정하세요", 503)
        attempt_count = 0

        def request_cloud():
            nonlocal attempt_count
            attempt_count += 1
            self.record(
                {
                    "stage": stage,
                    "event": "request_started",
                    "location": "api",
                    "attempt": attempt_count,
                    "fallback_reason": reason,
                    "duplicate_cost_possible": attempt_count > 1,
                }
            )
            return cloud()

        result = retry(
            request_cloud,
            on_retry=lambda attempt, error: self.record(
                {
                    "event": "retry",
                    "stage": stage,
                    "location": "api",
                    "attempt": attempt,
                    "reason": error.code,
                    "duplicate_cost_possible": True,
                }
            ),
        )
        self.record(
            {
                "event": "engine_result",
                "stage": stage,
                "location": "api",
                "quality": "unverified",
                "fallback_reason": reason,
            }
        )
        return result
