import json
from pathlib import Path

from tests.audio_fixtures import write_silence


def test_missing_reference_cannot_verify_local_quality(tmp_path):
    from meetinglog.evaluation import evaluate_manifest

    manifest = tmp_path / "corpus.json"
    manifest.write_text('{"schema_version":1,"items":[]}', encoding="utf-8")
    report = evaluate_manifest(manifest, mode="local_only")
    assert report.status == "insufficient_evidence"
    assert report.cer is None
    assert report.der is None


def test_normalization_keeps_numbers_and_negation():
    from meetinglog.evaluation import normalize_reference

    assert normalize_reference(" 10월 16일, 20명은 아닙니다. ") == "10월16일20명은아닙니다"
    assert normalize_reference("합니다") != normalize_reference("안 합니다")


def test_automated_scores_cannot_replace_human_review(tmp_path):
    from meetinglog.evaluation import EvaluationReport, classify

    report = EvaluationReport(
        status="insufficient_evidence",
        cer=0.01,
        der=0.01,
        duration_ms=5_400_000,
        elapsed_ms=10,
        peak_memory_bytes=None,
        human_review=[],
        model_revisions={},
    )
    assert (
        classify(report, quality_ms=1_800_000, performance_ms=3_600_000) == "insufficient_evidence"
    )


def test_runner_uses_real_paths_and_reports_silence_separately(tmp_path):
    from meetinglog.domain import SpeechResult
    from meetinglog.evaluation import evaluate_manifest

    write_silence(tmp_path / "silence.wav")
    (tmp_path / "reference.txt").write_text("")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "items": [
                    {
                        "id": "silence",
                        "audio_path": "silence.wav",
                        "reference_transcript_path": "reference.txt",
                        "reference_rttm_path": None,
                        "human_review_path": None,
                        "split": "quality",
                    }
                ],
            }
        )
    )

    def runner(path: Path, mode):
        assert path.is_file() and mode == "local_only"
        return SpeechResult(turns=[], speakers=[], no_speech=True, provider="test", model="fixed")

    report = evaluate_manifest(manifest, mode="local_only", runner=runner)
    assert report.status == "insufficient_evidence"
    assert report.cer is None
    assert report.items[0]["silence_failure"] is False
    assert report.peak_memory_bytes is None
