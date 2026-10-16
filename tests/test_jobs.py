import pytest
from meetinglog.db import ApiError
from meetinglog.domain import StageResult

from tests.audio_fixtures import write_silence


@pytest.fixture
def jobs(input_service, db, tmp_path):
    from meetinglog.jobs.repository import JobRepository

    record = input_service.import_file(
        "ready.wav", [write_silence(tmp_path / "ready.wav").read_bytes()]
    )
    return JobRepository(db), record


def test_cancelled_job_cannot_publish_and_active_enqueue_is_idempotent(jobs):
    repository, recording = jobs
    job = repository.enqueue(recording.id, "process", None, "local_only")
    assert repository.enqueue(recording.id, "process", None, "local_only").id == job.id
    assert repository.claim().id == job.id
    repository.cancel(job.id)
    result = StageResult(
        job_id=job.id, generation=job.generation, stage="speech", artifact_path="speech.json"
    )
    assert repository.commit_stage(result) is False


def test_recovery_retains_completed_checkpoint(jobs):
    repository, recording = jobs
    job = repository.enqueue(recording.id, "process", None, "local_only")
    repository.claim()
    assert repository.commit_stage(
        StageResult(job_id=job.id, generation=0, stage="speech", artifact_path="speech.json")
    )
    repository.recover()
    recovered = repository.claim()
    assert recovered.id == job.id
    assert recovered.stage == "analysis"


def test_second_worker_cannot_modify_running_job(jobs, settings):
    from meetinglog.jobs.runner import Worker

    repository, recording = jobs
    repository.enqueue(recording.id, "process", None, "local_only")
    with Worker(settings, repository.db):
        running = repository.claim()
        with pytest.raises(ApiError) as error:
            with Worker(settings, repository.db):
                pass
        assert error.value.code == "worker_running"
        assert repository.get(running.id).state == "running"


def test_deleted_generation_rejects_late_stage(jobs):
    repository, recording = jobs
    job = repository.enqueue(recording.id, "process", None, "local_only")
    repository.claim()
    with repository.db.session() as connection:
        connection.execute(
            "UPDATE recordings SET generation=1,deleted_at='deleted' WHERE id=?", (recording.id,)
        )
    assert not repository.commit_stage(
        StageResult(job_id=job.id, generation=0, stage="speech", artifact_path="late.json")
    )


def test_worker_restart_publishes_completed_speech_without_rerunning(jobs, settings, tmp_path):
    import json

    from meetinglog.jobs.runner import Worker
    from meetinglog.transcripts.repository import TranscriptRepository

    repository, recording = jobs
    job = repository.enqueue(recording.id, "process", None, "local_only")
    with Worker(settings, repository.db):
        repository.claim()
        artifact = tmp_path / "completed-speech.json"
        artifact.write_text(
            json.dumps(
                {
                    "turns": [],
                    "speakers": [],
                    "no_speech": True,
                    "provider": "test",
                    "model": "silence",
                }
            )
        )
        assert repository.commit_stage(
            StageResult(job_id=job.id, generation=0, stage="speech", artifact_path=str(artifact))
        )

    def forbidden_command(_):
        raise AssertionError("completed speech must not be inferred twice")

    with Worker(settings, repository.db, stage_command=forbidden_command) as worker:
        assert worker.run_once()
    completed = repository.get(job.id)
    assert completed.state == "succeeded"
    assert completed.stage == "no_speech"
    assert TranscriptRepository(repository.db).current(recording.id).turns == []
