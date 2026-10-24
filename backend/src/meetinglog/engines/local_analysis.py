import httpx
from pydantic import BaseModel, ValidationError

from meetinglog.analysis.input import AnalysisInput
from meetinglog.analysis.prompts import merge_messages, messages
from meetinglog.config import Settings
from meetinglog.db import ApiError
from meetinglog.domain import AnalysisForm, FormAnalysisBody
from meetinglog.engines.policy import loopback_url


def unload_ollama(settings: Settings):
    try:
        with httpx.Client(
            base_url=loopback_url(settings.ollama_url),
            timeout=2,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            client.post("/api/generate", json={"model": settings.ollama_model, "keep_alive": 0})
    except (httpx.HTTPError, ApiError):
        pass


class LocalAnalysis:
    provider = "ollama"

    def __init__(self, settings: Settings, client=None, form: AnalysisForm = "meeting"):
        self.form = form
        self.settings, self.model = settings, settings.ollama_model
        self.client = client or httpx.Client(
            base_url=loopback_url(settings.ollama_url),
            timeout=300,
            follow_redirects=False,
            trust_env=False,
        )

    def _request(self, schema: type[BaseModel], input_messages: list[dict]):
        # Validate even when a caller supplies a client with a custom transport.
        loopback_url(self.settings.ollama_url)
        try:
            for attempt in range(2):
                response = self.client.post(
                    "/api/chat",
                    json={
                        "model": self.model,
                        "messages": input_messages,
                        "format": schema.model_json_schema(),
                        "stream": False,
                        "keep_alive": "5m",
                        "options": {"num_ctx": 32768, "temperature": 0, "num_predict": 4096},
                    },
                )
                response.raise_for_status()
                try:
                    return schema.model_validate_json(response.json()["message"]["content"])
                except (ValidationError, ValueError, KeyError):
                    if attempt:
                        raise ApiError(
                            "invalid_output", "로컬 분석 결과의 형식을 확인하지 못했습니다", 503
                        ) from None
                    input_messages = [
                        *input_messages,
                        {
                            "role": "user",
                            "content": "이전 응답 형식이 올바르지 않다. 모든 필수 필드를 포함한 JSON만 출력한다.",
                        },
                    ]
        except httpx.HTTPError:
            raise ApiError(
                "ollama_unavailable", "Ollama와 gpt-oss:20b 실행 상태를 확인하세요", 503
            ) from None

    def generate(self, transcript: AnalysisInput, feedback: str | None = None) -> FormAnalysisBody:
        return self._request(FormAnalysisBody, messages(transcript, feedback, self.form))

    def merge(
        self, bodies: list[FormAnalysisBody], feedback: str | None = None
    ) -> FormAnalysisBody:
        return self._request(FormAnalysisBody, merge_messages(bodies, self.form, feedback))

    def digest(self) -> str | None:
        try:
            response = self.client.get("/api/tags", timeout=3)
            response.raise_for_status()
            return next(
                (
                    item["digest"]
                    for item in response.json().get("models", [])
                    if item.get("name") == self.model
                ),
                None,
            )
        except (httpx.HTTPError, ValueError):
            return None
