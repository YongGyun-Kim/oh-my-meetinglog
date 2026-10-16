from types import SimpleNamespace

import pytest
from meetinglog.db import ApiError

from tests.audio_fixtures import write_silence


def test_reference_speakers_survive_order_change_and_unmatched_voice_is_unknown(
    settings, tmp_path, monkeypatch
):
    from meetinglog.engines.cloud_speech import CloudSpeech
    from meetinglog.recordings.cloud_audio import AudioPart

    source = write_silence(tmp_path / "conversation.wav", seconds=15)
    monkeypatch.setattr(
        "meetinglog.engines.cloud_speech.prepare_uploads",
        lambda path: [AudioPart(source, 0, 0), AudioPart(source, 5000, 1000)],
    )
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        assert kwargs["response_format"] == "diarized_json"
        assert kwargs["chunking_strategy"] == "auto"
        assert "prompt" not in kwargs and "timestamp_granularities" not in kwargs
        if len(calls) == 1:
            segments = [
                {"id": "0", "start": 0, "end": 2.5, "speaker": "A", "text": "첫 화자"},
                {"id": "1", "start": 3, "end": 5.5, "speaker": "B", "text": "둘째 화자"},
            ]
        else:
            names = kwargs["known_speaker_names"]
            assert len(names) == 2
            assert all(
                ref.startswith("data:audio/wav;base64,")
                for ref in kwargs["known_speaker_references"]
            )
            segments = [
                {"id": "0", "start": 1, "end": 2, "speaker": names[1], "text": "둘째 계속"},
                {"id": "1", "start": 3, "end": 4, "speaker": names[0], "text": "첫째 계속"},
                {"id": "2", "start": 5, "end": 6, "speaker": "C", "text": "추가 발언"},
            ]
        return {
            "task": "transcribe",
            "duration": 15,
            "text": " ".join(s["text"] for s in segments),
            "segments": segments,
        }

    client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    result = CloudSpeech(settings, client).transcribe(source)
    by_text = {turn.text_original: turn for turn in result.turns}
    assert by_text["둘째 계속"].speaker_id == by_text["둘째 화자"].speaker_id
    assert by_text["첫째 계속"].speaker_id == by_text["첫 화자"].speaker_id
    assert by_text["둘째 계속"].start_ms == 6000
    assert by_text["추가 발언"].speaker_id is None
    assert "unknown_speaker" in by_text["추가 발언"].review_flags


def test_oversized_part_never_reaches_external_client(settings, tmp_path, monkeypatch):
    from meetinglog.engines.cloud_speech import CloudSpeech
    from meetinglog.recordings.cloud_audio import AudioPart

    source = tmp_path / "large.mp3"
    with source.open("wb") as audio:
        audio.truncate(25_000_001)
    monkeypatch.setattr(
        "meetinglog.engines.cloud_speech.prepare_uploads", lambda path: [AudioPart(source, 0, 0)]
    )

    def forbidden(**kwargs):
        raise AssertionError("oversized request must not be transmitted")

    client = SimpleNamespace(
        audio=SimpleNamespace(transcriptions=SimpleNamespace(create=forbidden))
    )
    with pytest.raises(ApiError):
        CloudSpeech(settings, client).transcribe(source)
