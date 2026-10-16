"""Explicit, offline-by-default corpus evaluation; never downloads models."""

import hashlib
import json
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import Field

from meetinglog.config import Settings
from meetinglog.domain import Contract, Mode, SpeechResult, new_id


class CorpusItem(Contract):
    id: str
    audio_path: str
    reference_transcript_path: str | None
    reference_rttm_path: str | None
    split: Literal["quality", "performance"]
    human_review_path: str | None


class Corpus(Contract):
    schema_version: Literal[1]
    items: list[CorpusItem]


class EvaluationReport(Contract):
    id: str = Field(default_factory=new_id)
    status: Literal["insufficient_evidence", "passed", "failed"]
    model_revisions: dict[str, str | None]
    cer: float | None = None
    der: float | None = None
    duration_ms: int = 0
    elapsed_ms: int = 0
    peak_memory_bytes: int | None = None
    human_review: list[dict] = Field(default_factory=list)
    items: list[dict] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def normalize_reference(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFC", text)
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def classify(report: EvaluationReport, quality_ms: int, performance_ms: int) -> str:
    checks = (
        "topics_preserved",
        "qa_preserved",
        "numbers_preserved",
        "negation_preserved",
        "evidence_valid",
        "no_invented_decisions_owners_dates",
    )
    if (
        quality_ms < 1_800_000
        or performance_ms < 3_600_000
        or report.cer is None
        or report.der is None
        or not report.human_review
        or any(
            not review.get("matches_prediction") or not review.get("reviewer")
            for review in report.human_review
        )
        or any(item.get("error") for item in report.items)
    ):
        return "insufficient_evidence"
    human_ok = all(all(review.get(key) is True for key in checks) for review in report.human_review)
    performance = [
        item
        for item in report.items
        if item["split"] == "performance" and item.get("duration_ms", 0) >= 3_600_000
    ]
    if not performance:
        return "insufficient_evidence"
    return (
        "passed"
        if (
            report.cer <= 0.1
            and report.der <= 0.1
            and human_ok
            and all(item["elapsed_ms"] <= item["duration_ms"] * 0.25 for item in performance)
            and not any(item.get("silence_failure") for item in report.items)
        )
        else "failed"
    )


def default_runner(path: Path, mode: Mode, engine: str = "qwen") -> dict:
    from meetinglog.analysis.repository import AnalysisRepository
    from meetinglog.db import ApiError, Database
    from meetinglog.domain import StageRequest
    from meetinglog.jobs.repository import JobRepository
    from meetinglog.jobs.runner import Worker
    from meetinglog.recordings.service import InputService
    from meetinglog.recordings.storage import atomic_json
    from meetinglog.transcripts.repository import TranscriptRepository

    base = Settings()
    with tempfile.TemporaryDirectory(prefix="meetinglog-eval-") as temporary:
        settings = base.model_copy(
            update={"data_dir": Path(temporary), "models_dir": base.models_dir.resolve()}
        )
        db = Database(settings.database_path)
        db.migrate()
        with path.open("rb") as audio:
            recording = InputService(settings, db).import_file(
                path.name, iter(lambda: audio.read(1024 * 1024), b"")
            )
        job = JobRepository(db).enqueue(recording.id, "process", None, mode)

        def command(request: StageRequest):
            request_path = Path(request.output_path).with_suffix(".request.json")
            atomic_json(request_path, request.model_dump())
            module = (
                "meetinglog.evaluation"
                if engine == "whisper" and request.stage == "speech"
                else "meetinglog.engines.local_executor"
            )
            return [sys.executable, "-m", module, str(request_path)]

        started = time.monotonic()
        with Worker(settings, db, stage_command=command if engine == "whisper" else None) as worker:
            worker.run_once()
        elapsed_ms = round((time.monotonic() - started) * 1000)
        finished = JobRepository(db).get(job.id)
        if finished.state != "succeeded":
            raise ApiError(
                finished.error_code or "evaluation_failed",
                finished.error_message or "평가 처리 실패",
                503,
            )
        transcript = TranscriptRepository(db).current(recording.id)
        analysis = AnalysisRepository(db).current(recording.id)
        return {
            "transcript": transcript.model_dump(mode="json"),
            "analysis": analysis.model_dump(mode="json") if analysis else None,
            "elapsed_ms": elapsed_ms,
        }


def prediction_digest(prediction: dict) -> str:
    transcript = prediction["transcript"]
    ids = {turn["id"]: f"turn-{index}" for index, turn in enumerate(transcript["turns"])}
    ids.update(
        {speaker["id"]: f"speaker-{index}" for index, speaker in enumerate(transcript["speakers"])}
    )

    def stable(value):
        if isinstance(value, str):
            return ids.get(value, value)
        if isinstance(value, list):
            return [stable(item) for item in value]
        if isinstance(value, dict):
            return {
                key: stable(item)
                for key, item in value.items()
                if key not in ("created_at", "recording_id", "parent_id")
            }
        return value

    payload = {
        "turns": transcript["turns"],
        "speakers": transcript["speakers"],
        "analysis": (prediction.get("analysis") or {}).get("body"),
    }
    return hashlib.sha256(
        json.dumps(stable(payload), ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def evaluate_manifest(path: Path, mode: Mode, *, runner=None, engine="qwen") -> EvaluationReport:
    from meetinglog.engines.models import ModelRegistry
    from meetinglog.recordings.media import probe

    manifest = Corpus.model_validate_json(path.read_text())
    revisions = {
        name: item.get("revision")
        for name, item in ModelRegistry(Settings()).read().get("models", {}).items()
    }
    report = EvaluationReport(
        status="insufficient_evidence",
        model_revisions=revisions,
        limitations=[
            "메모리 측정 미구현: 워커 자식과 별도 Ollama 프로세스를 포함한 peak_memory_bytes는 null입니다.",
            "모델 준비·파일 업로드 시간은 처리 시간에서 제외합니다. 디코딩·모델 로드·전사·화자 구분·분석은 포함합니다.",
        ],
    )
    references, hypotheses = [], []
    quality_ms = performance_ms = 0
    metric = None
    root = path.resolve().parent
    for item in manifest.items:
        entry = {"id": item.id, "split": item.split}
        report.items.append(entry)
        try:
            audio = (root / item.audio_path).resolve()
            media = probe(audio)
            duration = media.duration_ms
            entry["duration_ms"] = duration
            report.duration_ms += duration
            started = time.monotonic()
            prediction = runner(audio, mode) if runner else default_runner(audio, mode, engine)
            if isinstance(prediction, SpeechResult):
                prediction = {
                    "transcript": {
                        "turns": [turn.model_dump() for turn in prediction.turns],
                        "speakers": [speaker.model_dump() for speaker in prediction.speakers],
                    },
                    "analysis": None,
                }
            entry["elapsed_ms"] = prediction.get(
                "elapsed_ms", round((time.monotonic() - started) * 1000)
            )
            report.elapsed_ms += entry["elapsed_ms"]
            entry["prediction"] = prediction
            entry["prediction_sha256"] = prediction_digest(prediction)
            transcript = prediction["transcript"]
            text = "".join(
                turn.get("text_edited") or turn["text_original"] for turn in transcript["turns"]
            )
            if item.split == "performance":
                performance_ms = max(performance_ms, duration)
            if item.reference_transcript_path:
                reference = normalize_reference((root / item.reference_transcript_path).read_text())
                if reference:
                    references.append(reference)
                    hypotheses.append(normalize_reference(text))
                else:
                    entry["silence_failure"] = bool(text.strip())
            if item.reference_rttm_path:
                from pyannote.core import Annotation, Segment
                from pyannote.database.util import load_rttm
                from pyannote.metrics.diarization import DiarizationErrorRate

                annotations = load_rttm(root / item.reference_rttm_path)
                if len(annotations) != 1:
                    raise ValueError("RTTM must contain one recording")
                reference_diarization = next(iter(annotations.values()))
                hypothesis = Annotation()
                for index, turn in enumerate(transcript["turns"]):
                    if turn.get("speaker_id"):
                        hypothesis[
                            Segment(turn["start_ms"] / 1000, turn["end_ms"] / 1000), index
                        ] = turn["speaker_id"]
                metric = metric or DiarizationErrorRate(collar=0, skip_overlap=False)
                entry["der"] = metric(reference_diarization, hypothesis)
                if item.split == "quality" and item.reference_transcript_path:
                    quality_ms += duration
            review = {"item_id": item.id, "matches_prediction": False}
            if item.human_review_path:
                review.update(json.loads((root / item.human_review_path).read_text()))
                review["matches_prediction"] = (
                    review.get("prediction_sha256") == entry["prediction_sha256"]
                    and prediction.get("analysis") is not None
                )
            report.human_review.append(review)
        except Exception as error:
            entry["error"] = type(error).__name__
            report.limitations.append(
                f"{item.id}: 실행·정답 또는 평가 의존성을 확인하세요 ({type(error).__name__})."
            )
    if references:
        from jiwer import cer

        report.cer = cer(references, hypotheses)
    if metric is not None:
        report.der = abs(metric)
    report.status = classify(report, quality_ms, performance_ms)
    if report.status == "insufficient_evidence":
        report.limitations.append(
            "30분 정답 전사·RTTM, 별도 60분 연속 성능 자료, 현재 결과와 일치하는 사람 검토가 모두 필요합니다."
        )
    return report


def whisper_stage():
    """Evaluation-only speech adapter, with the same alignment/diarization contract."""
    import os
    from types import SimpleNamespace

    from meetinglog.domain import StageRequest
    from meetinglog.engines.cloud_speech import CloudSpeech
    from meetinglog.engines.local_speech import LazyModel, LocalSpeech
    from meetinglog.engines.models import ModelRegistry
    from meetinglog.engines.policy import EnginePolicy
    from meetinglog.recordings.media import normalize
    from meetinglog.recordings.storage import atomic_json

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    settings = Settings()
    registry = ModelRegistry(settings)

    class Whisper:
        def generate(self, path, **kwargs):
            import mlx_whisper

            result = mlx_whisper.transcribe(
                path,
                path_or_hf_repo=str(registry.require("whisper")),
                language="ko",
                condition_on_previous_text=False,
            )
            return SimpleNamespace(text=result["text"])

    request = StageRequest.model_validate_json(Path(sys.argv[1]).read_text())
    normalized = Path(request.output_path).with_suffix(".wav")
    normalize(Path(request.input_path), normalized)

    def local():
        paths = {name: registry.require(name) for name in ("vad", "aligner", "diarizer")}
        return LocalSpeech(
            LazyModel(paths["vad"], "vad"),
            Whisper(),
            LazyModel(paths["aligner"], "stt"),
            LazyModel(paths["diarizer"], "vad"),
        ).transcribe(normalized)

    result = EnginePolicy(settings).execute(
        "speech", request.mode, 0, local, lambda: CloudSpeech(settings).transcribe(normalized)
    )
    atomic_json(Path(request.output_path), result.model_dump(mode="json"))


if __name__ == "__main__":
    whisper_stage()
