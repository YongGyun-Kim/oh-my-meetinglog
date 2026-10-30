from pathlib import Path

import pytest
from meetinglog.db import ApiError

from tests.audio_fixtures import write_silence


def test_missing_chunk_does_not_finalize(input_service):
    from meetinglog.recordings.service import InputConflict

    record = input_service.create("microphone", "인터뷰")
    digest = input_service.append_chunk(record.id, 0, b"header")
    assert input_service.append_chunk(record.id, 0, b"header") == digest
    input_service.append_chunk(record.id, 2, b"last")
    with pytest.raises(InputConflict) as error:
        input_service.finalize(record.id, last_sequence=2)
    assert error.value.code == "missing_chunk"


def test_different_duplicate_cannot_overwrite_chunk(input_service):
    from meetinglog.recordings.service import InputConflict

    record = input_service.create("microphone", "인터뷰")
    input_service.append_chunk(record.id, 0, b"first")
    with pytest.raises(InputConflict):
        input_service.append_chunk(record.id, 0, b"changed")
    assert input_service.append_chunk(record.id, 0, b"first")


def test_import_is_persistent_and_filename_cannot_escape(input_service, db, settings, tmp_path):
    audio = write_silence(tmp_path / "input.wav").read_bytes()
    recording = input_service.import_file("../../outside.wav", [audio[:40], audio[40:]])
    assert recording.input_state == "ready"
    assert recording.duration_ms == 1000
    with db.session() as connection:
        row = connection.execute("SELECT * FROM recordings WHERE id=?", (recording.id,)).fetchone()
    source = Path(row["original_path"])
    assert source.is_relative_to(settings.data_dir.resolve() / "recordings" / recording.id)
    assert source.read_bytes() == audio
    assert not (settings.data_dir.parent / "outside.wav").exists()


def test_stream_size_limit_is_enforced(input_service):
    input_service.settings.max_upload_bytes = 5
    with pytest.raises(ApiError) as error:
        input_service.import_file("large.wav", [b"123", b"456"])
    assert error.value.status == 413


def test_valid_chunks_finalize_idempotently(input_service, tmp_path):
    audio = write_silence(tmp_path / "chunk.wav").read_bytes()
    recording = input_service.create("microphone", "녹음")
    input_service.append_chunk(recording.id, 0, audio[:100])
    input_service.append_chunk(recording.id, 1, audio[100:])
    first = input_service.finalize(recording.id, 1)
    assert first.input_state == "ready"
    assert input_service.finalize(recording.id, 1) == first


def test_oversized_duration_is_invalid(input_service, tmp_path):
    input_service.settings.max_duration_ms = 500
    with pytest.raises(ApiError):
        input_service.import_file("long.wav", [write_silence(tmp_path / "long.wav").read_bytes()])


def test_finalize_validation_does_not_block_unrelated_database_writes(
    input_service, db, tmp_path, monkeypatch
):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from meetinglog.jobs.repository import JobRepository
    from meetinglog.recordings.media import probe as real_probe

    record = input_service.create("microphone", "녹음")
    input_service.append_chunk(record.id, 0, write_silence(tmp_path / "probe.wav").read_bytes())
    entered, release = threading.Event(), threading.Event()

    def slow_probe(path):
        entered.set()
        assert release.wait(3)
        return real_probe(path)

    monkeypatch.setattr("meetinglog.recordings.service.probe", slow_probe)
    with ThreadPoolExecutor(2) as pool:
        finalizing = pool.submit(input_service.finalize, record.id, 0)
        assert entered.wait(1)
        try:
            pool.submit(JobRepository(db).heartbeat, "unrelated").result(timeout=0.4)
        finally:
            release.set()
        assert finalizing.result(timeout=2).input_state == "ready"
