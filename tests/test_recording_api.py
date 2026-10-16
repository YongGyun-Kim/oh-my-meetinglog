from tests.api_fixtures import populated_client


def test_recording_list_detail_and_audio_range(settings, db, tmp_path):
    client, record_id, transcript = populated_client(settings, db, tmp_path)
    try:
        listed = client.get("/api/recordings").json()
        assert listed["items"][0]["id"] == record_id
        detail = client.get(f"/api/recordings/{record_id}").json()
        assert detail["transcript"]["id"] == transcript.id
        audio = client.get(f"/api/recordings/{record_id}/audio", headers={"range": "bytes=0-9"})
        assert audio.status_code == 206
        assert len(audio.content) == 10
        assert audio.headers["content-range"].startswith("bytes 0-9/")
        assert (
            client.get(
                f"/api/recordings/{record_id}/audio", headers={"range": "bytes=9999999-"}
            ).status_code
            == 416
        )
    finally:
        client.__exit__(None, None, None)


def test_duplicate_finalize_does_not_create_second_initial_job(settings, db, tmp_path):
    from fastapi.testclient import TestClient
    from meetinglog.app import create_app
    from meetinglog.jobs.repository import JobRepository

    from tests.audio_fixtures import write_silence

    with TestClient(create_app(settings), base_url="http://localhost:8765") as client:
        record_id = client.post("/api/recordings/drafts", json={"title": "녹음"}).json()["id"]
        audio = write_silence(tmp_path / "draft.wav").read_bytes()
        assert client.put(f"/api/recordings/{record_id}/chunks/0", content=audio).status_code == 200
        assert (
            client.post(
                f"/api/recordings/{record_id}/finalize", json={"last_sequence": 0}
            ).status_code
            == 200
        )
        repo = JobRepository(db)
        job = repo.claim()
        repo.finish(job.id, "succeeded")
        assert (
            client.post(
                f"/api/recordings/{record_id}/finalize", json={"last_sequence": 0}
            ).status_code
            == 200
        )
        with db.session() as connection:
            assert (
                connection.execute(
                    "SELECT COUNT(*) FROM jobs WHERE recording_id=?", (record_id,)
                ).fetchone()[0]
                == 1
            )


def test_edit_marks_analysis_stale_and_exports_do_not_mix_versions(settings, db, tmp_path):

    from meetinglog.analysis.service import AnalysisService
    from meetinglog.domain import AnalysisVersion, new_id
    from meetinglog.jobs.repository import JobRepository

    from tests.analysis_fixtures import analysis_fixture

    client, record_id, transcript = populated_client(settings, db, tmp_path)
    try:
        response = client.post(
            f"/api/recordings/{record_id}/analyze",
            json={"mode": "local_only", "transcript_id": transcript.id},
        )
        assert response.status_code == 200
        repo = JobRepository(db)
        job = repo.claim()
        version = AnalysisVersion(
            id=new_id(),
            transcript_id=transcript.id,
            body=analysis_fixture(),
            provider="test",
            model="fixed",
            prompt_version="1",
        )
        artifact = tmp_path / "analysis.json"
        artifact.write_text(version.model_dump_json())
        AnalysisService(db).publish(job, artifact)
        repo.finish(job.id, "succeeded")
        edited = client.patch(
            f"/api/recordings/{record_id}/transcript",
            json={
                "base_version_id": transcript.id,
                "changes": [{"turn_id": "t2", "text": "이번 주에 시작합니다."}],
            },
        )
        assert edited.status_code == 200
        assert client.get(f"/api/recordings/{record_id}").json()["analysis_stale"] is True
        assert client.get(f"/api/recordings/{record_id}/export").json()["analysis"] is None
        assert (
            client.get(f"/api/recordings/{record_id}/export?analysis_id={version.id}").status_code
            == 409
        )
    finally:
        client.__exit__(None, None, None)
