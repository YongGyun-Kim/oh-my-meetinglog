from fastapi.testclient import TestClient
from meetinglog.app import create_app
from meetinglog.jobs.repository import JobRepository
from meetinglog.transcripts.repository import TranscriptRepository

from tests.analysis_fixtures import as_speech, transcript_fixture
from tests.audio_fixtures import write_silence


def populated_client(settings, db, tmp_path):
    settings.openai_api_key = "canary-secret-never-expose"
    settings.ollama_url = "http://127.0.0.1:1"
    client = TestClient(create_app(settings), base_url="http://localhost:8765")
    client.__enter__()
    audio = write_silence(tmp_path / "api.wav", seconds=6)
    response = client.post(
        "/api/recordings", files={"file": ("인터뷰.wav", audio.read_bytes(), "audio/wav")}
    )
    assert response.status_code == 201
    record_id = response.json()["id"]
    jobs = JobRepository(db)
    job = jobs.claim()
    source = transcript_fixture(record_id)
    transcript = TranscriptRepository(db).save_generated(
        record_id,
        as_speech(source),
        0,
        job.id,
    )
    jobs.finish(job.id, "succeeded")
    return client, record_id, transcript
