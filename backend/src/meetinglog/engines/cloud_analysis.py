from meetinglog.analysis.input import AnalysisInput
from meetinglog.analysis.prompts import messages, summary_messages
from meetinglog.config import Settings
from meetinglog.db import ApiError
from meetinglog.domain import AnalysisBody, AnalysisForm, Overview


class CloudAnalysis:
    provider = "openai"

    def __init__(self, settings: Settings, client=None, form: AnalysisForm = "meeting"):
        self.form = form
        self.settings, self.model = settings, settings.openai_analysis_model
        if client is None:
            if not settings.openai_api_key:
                raise ApiError("api_not_configured", "서버에 외부 API 키를 설정하세요", 503)
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key, max_retries=0, timeout=300)
        self.client = client

    def _request(self, schema, input_messages):
        from openai import APIConnectionError, APIStatusError

        try:
            response = self.client.responses.parse(
                model=self.model, input=input_messages, text_format=schema, max_output_tokens=4096
            )
            if response.output_parsed is None:
                raise ApiError("invalid_output", "외부 분석 결과를 읽지 못했습니다", 503)
            return response.output_parsed
        except APIStatusError as error:
            raise ApiError(
                f"upstream_{error.status_code}",
                "외부 분석 요청에 실패했습니다. 계정과 요청 한도를 확인하세요",
                503,
                error.status_code == 429 or error.status_code >= 500,
            ) from None
        except APIConnectionError:
            raise ApiError(
                "upstream_network", "외부 분석 서비스에 연결하지 못했습니다", 503, True
            ) from None

    def generate(self, transcript: AnalysisInput, feedback: str | None = None) -> AnalysisBody:
        return self._request(AnalysisBody, messages(transcript, feedback, self.form))

    def summarize(self, overviews: list[Overview]) -> Overview:
        return self._request(Overview, summary_messages(overviews, self.form))
