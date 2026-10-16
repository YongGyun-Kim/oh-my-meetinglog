import os
import sys
from pathlib import Path

from meetinglog.config import Settings
from meetinglog.db import ApiError
from meetinglog.domain import StageRequest
from meetinglog.recordings.media import normalize
from meetinglog.recordings.storage import atomic_json


def execute(request: StageRequest, settings: Settings):
    if request.stage == "speech":
        from meetinglog.engines.local_speech import prepared_speech

        normalized = Path(request.output_path).with_suffix(".wav")
        normalize(Path(request.input_path), normalized)
        return prepared_speech(settings).transcribe(normalized).model_dump(mode="json")
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
