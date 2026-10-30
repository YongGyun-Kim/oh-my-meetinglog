import pytest
from meetinglog.db import ApiError

from tests.api_fixtures import populated_client


def test_deleted_record_immediately_disappears_then_worker_cleans_files(settings, db, tmp_path):
    from meetinglog.recordings.deletion import DeletionService
    from meetinglog.recordings.storage import Storage
    from meetinglog.transcripts.repository import TranscriptRepository
    from meetinglog.transcripts.service import TranscriptService

    client, record_id, transcript = populated_client(settings, db, tmp_path)
    try:
        directory = Storage(settings.data_dir).directory(record_id)
        assert directory.exists()
        assert client.delete(f"/api/recordings/{record_id}").status_code == 202
        assert client.get(f"/api/recordings/{record_id}").status_code == 404
        assert client.get(f"/api/recordings/{record_id}/audio").status_code == 404
        with pytest.raises(ApiError):
            TranscriptService(TranscriptRepository(db)).edit(
                record_id, transcript.id, [{"turn_id": "t1", "text": "뒤늦은 수정"}]
            )
        assert DeletionService(settings, db).cleanup_pending() == 1
        assert not directory.exists()
        with db.session() as connection:
            assert (
                connection.execute(
                    "SELECT COUNT(*) FROM transcripts WHERE recording_id=?", (record_id,)
                ).fetchone()[0]
                == 0
            )
    finally:
        client.__exit__(None, None, None)


def test_deletion_stops_active_child_before_removing_recording(
    settings, db, input_service, tmp_path
):
    import sys
    import threading
    import time

    from meetinglog.jobs.repository import JobRepository
    from meetinglog.jobs.runner import Worker
    from meetinglog.recordings.deletion import DeletionService
    from meetinglog.recordings.storage import Storage

    from tests.audio_fixtures import write_silence

    record = input_service.import_file(
        "delete.wav", [write_silence(tmp_path / "delete.wav").read_bytes()]
    )
    repository = JobRepository(db)
    repository.enqueue(record.id, "process", None, "local_only")
    directory = Storage(settings.data_dir).directory(record.id)
    marker = directory / "child-started"

    def command(request):
        script = 'from pathlib import Path;import sys,time;Path(sys.argv[1]).write_text("started");time.sleep(30);Path(sys.argv[2]).write_text("late")'
        return [sys.executable, "-c", script, str(marker), request.output_path]

    with Worker(settings, db, stage_command=command) as worker:
        thread = threading.Thread(target=worker.run_once)
        thread.start()
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists()
        DeletionService(settings, db).request(record.id)
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert worker.run_once() is False
    assert not directory.exists()
