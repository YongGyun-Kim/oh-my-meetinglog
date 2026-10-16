from pathlib import Path

from meetinglog.config import Settings
from meetinglog.db import ApiError
from meetinglog.domain import Speaker, SpeechResult, Turn, new_id
from meetinglog.recordings.cloud_audio import prepare_uploads, reference_data_url
from meetinglog.recordings.storage import atomic_json


class CloudSpeech:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        if client is None:
            if not settings.openai_api_key:
                raise ApiError("api_not_configured", "서버에 외부 API 키를 설정하세요", 503)
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key, max_retries=0, timeout=600)
        self.client = client

    def transcribe(self, path: Path) -> SpeechResult:
        from openai import APIConnectionError, APIStatusError

        parts = prepare_uploads(path)
        turns, speakers, references, names, raw = [], [], [], [], []
        mapping = {}
        for index, part in enumerate(parts):
            if part.path.stat().st_size > 24_000_000:
                raise ApiError("upload_limit", "외부 요청의 파일 크기 제한을 초과했습니다", 413)
            kwargs = {
                "model": self.settings.openai_speech_model,
                "response_format": "diarized_json",
                "chunking_strategy": "auto",
            }
            if references:
                kwargs.update(known_speaker_names=names, known_speaker_references=references)
            try:
                with part.path.open("rb") as audio:
                    response = self.client.audio.transcriptions.create(file=audio, **kwargs)
            except APIStatusError as error:
                raise ApiError(
                    f"upstream_{error.status_code}",
                    "외부 음성 요청에 실패했습니다. 계정 설정과 요청 한도를 확인하세요",
                    503,
                    error.status_code == 429 or error.status_code >= 500,
                ) from None
            except APIConnectionError:
                raise ApiError(
                    "upstream_network", "외부 음성 서비스에 연결하지 못했습니다", 503, True
                ) from None
            data = response if isinstance(response, dict) else response.model_dump()
            raw.append(data)
            segments = data.get("segments")
            if not isinstance(segments, list):
                raise ApiError("invalid_output", "화자 구분 전사 형식이 올바르지 않습니다", 503)
            for segment in segments:
                text = str(segment.get("text", "")).strip()
                if not text:
                    continue
                try:
                    start = round(float(segment["start"]) * 1000) + part.offset_ms
                    end = round(float(segment["end"]) * 1000) + part.offset_ms
                    if start < 0 or end <= start:
                        raise ValueError
                except (KeyError, ValueError, TypeError):
                    raise ApiError(
                        "invalid_output", "외부 전사의 시간 정보가 올바르지 않습니다", 503
                    ) from None
                label = segment.get("speaker")
                if index == 0 and label is not None and label not in mapping:
                    mapping[label] = new_id()
                    speakers.append(
                        Speaker(
                            id=mapping[label], display_name=f"화자 {chr(64 + len(speakers) + 1)}"
                        )
                    )
                speaker_id = mapping.get(label) if index == 0 else label if label in names else None
                if any(
                    turn.text_original == text
                    and abs(turn.start_ms - start) < 200
                    and min(turn.end_ms, end) > max(turn.start_ms, start)
                    for turn in turns[-30:]
                ):
                    continue
                turns.append(
                    Turn(
                        id=new_id(),
                        start_ms=start,
                        end_ms=end,
                        speaker_id=speaker_id,
                        text_original=text,
                        review_flags=[] if speaker_id else ["unknown_speaker"],
                    )
                )
            if index == 0 and len(parts) > 1:
                for segment in segments:
                    label = segment.get("speaker")
                    if label not in mapping or mapping[label] in names or len(names) >= 4:
                        continue
                    start, end = float(segment["start"]), float(segment["end"])
                    if end - start < 2 or any(
                        other.get("speaker") != label
                        and max(start, float(other["start"])) < min(end, float(other["end"]))
                        for other in segments
                    ):
                        continue
                    target = part.path.parent / f"reference-{len(names)}.wav"
                    references.append(
                        reference_data_url(path, start + part.offset_ms / 1000, end - start, target)
                    )
                    names.append(mapping[label])
        artifact = parts[0].path.parent / "response.json"
        atomic_json(artifact, {"responses": raw})
        return SpeechResult(
            turns=turns,
            speakers=speakers,
            no_speech=not turns,
            provider="openai",
            model=self.settings.openai_speech_model,
            raw_artifact=str(artifact),
        )
