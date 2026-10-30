import httpx
from pydantic import Field

from meetinglog.analysis.cli_catalog import ModelOption, cli_models
from meetinglog.config import Settings
from meetinglog.db import ApiError, Database
from meetinglog.domain import AnalysisSettings, Contract
from meetinglog.engines.policy import loopback_url


def saved_analysis_settings(db: Database, connection=None) -> AnalysisSettings | None:
    from contextlib import nullcontext

    with nullcontext(connection) if connection is not None else db.session() as connection:
        row = connection.execute("SELECT value FROM settings WHERE key='analysis'").fetchone()
    return AnalysisSettings.model_validate_json(row[0]) if row else None


def analysis_settings(db: Database, settings: Settings) -> AnalysisSettings:
    saved = saved_analysis_settings(db)
    if saved:
        return saved
    from meetinglog.settings_api import effective_mode

    if effective_mode(db, settings) == "api":
        return AnalysisSettings(provider="openai", model=settings.openai_analysis_model)
    return AnalysisSettings(
        provider="ollama",
        model=settings.ollama_model,
        reasoning="low" if settings.ollama_model.split(":")[0] == "gpt-oss" else "default",
    )


class AnalysisOptions(Contract):
    models: list[str]
    catalog: list[ModelOption] = Field(default_factory=list)
    default_model: str = ""
    reasoning: list[str]
    message: str | None = None


def options(provider: str, model: str, settings: Settings) -> AnalysisOptions:
    if provider in ("codex", "claude"):
        try:
            catalog, default = cli_models(provider)
        except ApiError as error:
            return AnalysisOptions(models=[], reasoning=["default"], message=error.message)
        selected = next(
            (item for item in catalog if (model or default) in [item.id, *item.aliases]), None
        )
        return AnalysisOptions(
            models=[item.id for item in catalog],
            catalog=catalog,
            default_model=default,
            reasoning=["default", *(selected.reasoning if selected else [])],
            message="선택한 모델의 지원 정보를 찾지 못했어요."
            if model and selected is None
            else None,
        )
    if provider == "openai":
        return AnalysisOptions(
            models=[],
            default_model=settings.openai_analysis_model,
            reasoning=["default", "none", "minimal", "low", "medium", "high", "xhigh"],
        )
    models, thinking, message = [], ["default"], None
    try:
        with httpx.Client(
            base_url=loopback_url(settings.ollama_url),
            timeout=2,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            models = [item["name"] for item in response.json().get("models", [])]
            if model in models:
                response = client.post("/api/show", json={"model": model})
                response.raise_for_status()
                data = response.json()
                values = (data.get("thinking") or {}).get("values", [])
                if values:
                    thinking += [
                        ("on" if value else "off") if isinstance(value, bool) else value
                        for value in values
                        if value in (True, False, "low", "medium", "high")
                    ]
                elif "thinking" in data.get("capabilities", []):
                    thinking += (
                        ["low", "medium", "high"]
                        if model.split(":")[0] == "gpt-oss"
                        else ["off", "on"]
                    )
    except (ApiError, httpx.HTTPError, ValueError, KeyError, TypeError):
        message = "Ollama에서 모델 목록을 가져오지 못했어요. 실행 상태를 확인해 주세요."
    if model.split(":")[0] == "gpt-oss":
        thinking = ["default", "low", "medium", "high"]
    return AnalysisOptions(
        models=models, default_model=settings.ollama_model, reasoning=thinking, message=message
    )


def validate_selection(selection: AnalysisSettings, settings: Settings) -> AnalysisSettings:
    if selection.provider not in ("codex", "claude"):
        return selection
    available = options(selection.provider, selection.model, settings)
    if not available.catalog:
        if selection.reasoning != "default":
            raise ApiError(
                "unknown_capabilities",
                "모델 정보를 조회할 수 없어 추론 수준은 기본값만 저장할 수 있어요.",
                422,
            )
        return selection
    model = selection.model or available.default_model
    if model and not any(model in [item.id, *item.aliases] for item in available.catalog):
        raise ApiError("unknown_model", "조회된 목록에서 모델을 선택해 주세요.", 422)
    if selection.reasoning not in available.reasoning:
        raise ApiError(
            "unsupported_reasoning", "선택한 모델이 지원하는 추론 수준을 선택해 주세요.", 422
        )
    return selection.model_copy(update={"model": model})
