import os
import sys
from pathlib import Path

from meetinglog.config import Settings
from meetinglog.db import ApiError
from meetinglog.domain import StageRequest
from meetinglog.engines.policy import EnginePolicy
from meetinglog.recordings.media import normalize
from meetinglog.recordings.storage import atomic_json


def execute(request: StageRequest, settings: Settings):
    if request.stage == "speech":
        from meetinglog.engines.cloud_speech import CloudSpeech
        from meetinglog.engines.local_speech import prepared_speech

        policy = EnginePolicy(
            settings, event_path=Path(request.output_path).with_suffix(".events.jsonl")
        )

        def progress(phase, completed=0, total=None):
            policy.record(
                {
                    "stage": "speech",
                    "event": "speech_progress",
                    "phase": phase,
                    "completed": completed,
                    "total": total,
                }
            )

        normalized = Path(request.output_path).with_suffix(".wav")
        progress("normalize")
        normalize(Path(request.input_path), normalized)
        speech = policy.execute(
            "speech",
            request.mode,
            0,
            lambda: prepared_speech(settings).transcribe(normalized, progress=progress),
            lambda: CloudSpeech(settings).transcribe(normalized),
        )
        atomic_json(
            Path(request.output_path).with_suffix(".events.json"), {"events": policy.events}
        )
        return speech.model_dump(mode="json")
    if request.stage == "analysis":
        from meetinglog.analysis.service import AnalysisService
        from meetinglog.db import Database
        from meetinglog.domain import Transcript

        transcript = Transcript.model_validate_json(Path(request.input_path).read_text())
        service = AnalysisService(
            Database(settings.database_path),
            settings,
            event_path=Path(request.output_path).with_suffix(".events.jsonl"),
            workspace=Path(request.output_path).with_suffix(".workspace"),
        )
        version = service.generate_from(
            transcript,
            request.mode,
            request.form,
            analysis_settings=request.analysis_settings,
            settings_fixed=True,
        )
        atomic_json(
            Path(request.output_path).with_suffix(".events.json"), {"events": service.events}
        )
        return version.model_dump(mode="json")
    raise ApiError("unsupported_stage", "지원하지 않는 처리 단계입니다", 503)


def main():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    request = StageRequest.model_validate_json(Path(sys.argv[1]).read_text())
    try:
        atomic_json(Path(request.output_path), execute(request, Settings()))
    except ApiError as error:
        atomic_json(
            Path(request.output_path).with_suffix(".error.json"),
            {"code": error.code, "message": error.message, "retryable": error.retryable},
        )
        raise SystemExit(1) from None
    except Exception as error:
        print(f"Engine error: {type(error).__name__}", file=sys.stderr)
        atomic_json(
            Path(request.output_path).with_suffix(".error.json"),
            {
                "code": "engine_failed",
                "message": "처리 엔진 실행에 실패했습니다. 모델과 실행 환경을 확인하세요",
                "retryable": False,
            },
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
