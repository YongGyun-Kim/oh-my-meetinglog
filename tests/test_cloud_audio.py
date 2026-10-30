from tests.audio_fixtures import write_silence


def test_encoded_parts_respect_size_limit_and_preserve_offsets(tmp_path):
    from meetinglog.recordings.cloud_audio import prepare_uploads

    source = write_silence(tmp_path / "input.wav", seconds=6)
    parts = prepare_uploads(source, max_bytes=6000)
    assert len(parts) > 1
    assert parts[0].offset_ms == 0
    assert all(part.path.stat().st_size <= 6000 for part in parts)
    assert all(
        right.offset_ms > left.offset_ms for left, right in zip(parts, parts[1:], strict=False)
    )
    assert all(part.overlap_ms > 0 for part in parts[1:])


def test_small_audio_stays_in_one_request(tmp_path):
    from meetinglog.recordings.cloud_audio import prepare_uploads

    parts = prepare_uploads(write_silence(tmp_path / "short.wav"))
    assert len(parts) == 1
    assert parts[0].overlap_ms == 0
