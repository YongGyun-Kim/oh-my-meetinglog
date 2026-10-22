import json
import sys

from meetinglog.domain import AnalysisVersion, new_id

from tests.analysis_fixtures import analysis_fixture, as_speech, transcript_fixture
from tests.audio_fixtures import write_silence


def test_analysis_failure_preserves_generated_transcript(
    input_service, db, settings, tmp_path, monkeypatch
):
    from meetinglog.jobs.repository import JobRepository
    from meetinglog.jobs.runner import Worker
    from meetinglog.transcripts.repository import TranscriptRepository

    def forbidden_unload(_):
        raise AssertionError("ordinary job completion must not touch a shared model")

    monkeypatch.setattr("meetinglog.engines.local_analysis.unload_ollama", forbidden_unload)

    record = input_service.import_file(
        "conversation.wav", [write_silence(tmp_path / "in.wav").read_bytes()]
    )
    repository = JobRepository(db)
    job = repository.enqueue(record.id, "process", None, "local_only")

    def command(request):
        if request.stage == "analysis":
            return [sys.executable, "-c", "raise SystemExit(1)"]
        transcript = transcript_fixture(record.id)
        payload = {
            "turns": [t.model_dump() for t in as_speech(transcript).turns],
            "speakers": [s.model_dump() for s in transcript.speakers],
            "provider": "test",
            "model": "fixed",
        }
        return [
            sys.executable,
            "-c",
            "from pathlib import Path;import sys;Path(sys.argv[1]).write_text(sys.argv[2])",
            request.output_path,
            json.dumps(payload),
        ]

    with Worker(settings, db, stage_command=command) as worker:
        worker.run_once()
    assert repository.get(job.id).state == "succeeded"
    assert repository.get(job.id).stage == "transcribed"
    transcript = TranscriptRepository(db).current(record.id)
    analysis_job = repository.enqueue(record.id, "analyze", transcript.id, "local_only")
    with Worker(settings, db, stage_command=command) as worker:
        worker.run_once()
    assert repository.get(analysis_job.id).state == "failed"
    assert transcript.turns[1].sentences[0].text_original == "다음 주에 시작하겠습니다."


def test_analysis_publication_is_idempotent_and_keeps_pinned_version(input_service, db, tmp_path):
    from meetinglog.analysis.service import AnalysisService
    from meetinglog.jobs.repository import JobRepository
    from meetinglog.transcripts.repository import TranscriptRepository
    from meetinglog.transcripts.service import TranscriptService

    record = input_service.import_file(
        "conversation.wav", [write_silence(tmp_path / "in.wav").read_bytes()]
    )
    source = transcript_fixture(record.id)
    trans = TranscriptRepository(db)
    original = trans.save_generated(
        record.id,
        as_speech(source),
        0,
    )
    repo = JobRepository(db)
    job = repo.enqueue(record.id, "analyze", original.id, "local_only")
    repo.claim()
    changed = TranscriptService(trans).edit(
        record.id, original.id, [{"turn_id": "t1", "text": "바뀐 질문"}]
    )
    artifact = tmp_path / "analysis.json"
    version = AnalysisVersion(
        id=new_id(),
        transcript_id=original.id,
        body=analysis_fixture(),
        provider="test",
        model="fixed",
        prompt_version="1",
    )
    artifact.write_text(version.model_dump_json())
    service = AnalysisService(db)
    first = service.publish(job, artifact)
    second = service.publish(job, artifact)
    assert first.id == second.id
    assert first.transcript_id == original.id
    assert trans.current(record.id).id == changed.id
