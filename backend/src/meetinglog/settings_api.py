import json
import shutil

import httpx
from fastapi import APIRouter, Request

from meetinglog.cli_auth import CliConnection, CliProvider
from meetinglog.config import Settings
from meetinglog.db import ApiError, Database
from meetinglog.domain import Contract, Mode
from meetinglog.engines.models import ModelRegistry
from meetinglog.engines.policy import loopback_url

router = APIRouter(prefix="/api/settings", tags=["settings"])


class EngineReadiness(Contract):
    name: str
    repo_id: str
    ready: bool
    revision: str | None = None
    quality: str = "unverified"


class Readiness(Contract):
    mode: Mode
    engines: list[EngineReadiness]
    api_configured: bool
    media_tools_ready: bool


class ModeInput(Contract):
    mode: Mode


class CliLoginInput(Contract):
    pass


def effective_mode(db: Database, settings: Settings) -> Mode:
    with db.session() as connection:
        row = connection.execute("SELECT value FROM settings WHERE key='mode'").fetchone()
        return ModeInput(mode=json.loads(row[0])).mode if row else settings.mode


def readiness(db: Database, settings: Settings) -> Readiness:
    engines = [EngineReadiness(**item) for item in ModelRegistry(settings).readiness()]
    available, digest = False, None
    try:
        with httpx.Client(
            base_url=loopback_url(settings.ollama_url),
            timeout=1,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            item = next(
                (
                    item
                    for item in response.json().get("models", [])
                    if item.get("name") == settings.ollama_model
                ),
                None,
            )
            available, digest = item is not None, item.get("digest") if item else None
    except (ApiError, httpx.HTTPError, ValueError):
        pass
    engines.append(
        EngineReadiness(
            name="analysis", repo_id=settings.ollama_model, ready=available, revision=digest
        )
    )
    return Readiness(
        mode=effective_mode(db, settings),
        engines=engines,
        api_configured=bool(settings.openai_api_key),
        media_tools_ready=bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
    )


@router.get("", response_model=Readiness)
def get(request: Request):
    return readiness(request.app.state.db, request.app.state.settings)


@router.patch("", response_model=Readiness)
def update(request: Request, body: ModeInput):
    with request.app.state.db.session(immediate=True) as connection:
        connection.execute(
            "INSERT INTO settings(key,value) VALUES('mode',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(body.mode),),
        )
    return readiness(request.app.state.db, request.app.state.settings)


@router.get("/cli-connections", response_model=list[CliConnection])
def cli_connections(request: Request):
    return request.app.state.cli_auth.connections()


@router.post("/cli-connections/{provider}/login", response_model=CliConnection)
def cli_login(provider: CliProvider, body: CliLoginInput, request: Request):
    if request.headers.get("origin") not in request.app.state.settings.allowed_origins:
        raise ApiError("invalid_origin", "설정 화면에서 로그인을 시작해 주세요.", status=403)
    return request.app.state.cli_auth.start(provider)


@router.post("/cli-connections/{provider}/cancel", response_model=CliConnection)
def cancel_cli_login(provider: CliProvider, body: CliLoginInput, request: Request):
    if request.headers.get("origin") not in request.app.state.settings.allowed_origins:
        raise ApiError("invalid_origin", "설정 화면에서 로그인을 취소해 주세요.", status=403)
    return request.app.state.cli_auth.cancel(provider)
