import hashlib

import pytest
from meetinglog.db import ApiError

from tests.audio_fixtures import write_silence


def test_normalize_preserves_original_and_changes_only_derived_format(tmp_path):
    from meetinglog.recordings.media import normalize, probe

    source = write_silence(tmp_path / "stereo.wav", rate=44100, channels=2)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    assert probe(source).duration_ms == 1000
    target = tmp_path / "normalized.wav"
    info = normalize(source, target)
    assert (info.duration_ms, info.sample_rate, info.channels) == (1000, 16000, 1)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash


def test_invalid_container_is_rejected(tmp_path):
    from meetinglog.recordings.media import probe

    source = tmp_path / "bad.wav"
    source.write_text("not audio")
    with pytest.raises(ApiError) as error:
        probe(source)
    assert error.value.code == "invalid_audio"


def test_browser_style_webm_without_header_duration_is_accepted():
    from pathlib import Path

    from meetinglog.recordings.media import probe

    # Captured with Chromium's fake microphone, not a private recording.
    path = Path(__file__).parent / "fixtures" / "browser-fake-mic.webm"
    assert 1000 <= probe(path).duration_ms <= 1500
