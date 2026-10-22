from types import SimpleNamespace

from tests.audio_fixtures import write_silence


def test_silence_never_invokes_asr_or_diarization(tmp_path):
    from meetinglog.engines.local_speech import LocalSpeech

    class Forbidden:
        def generate(self, *args, **kwargs):
            raise AssertionError("silence must not invoke speech models")

    vad = SimpleNamespace(get_speech_timestamps=lambda *args, **kwargs: [])
    result = LocalSpeech(vad, Forbidden(), Forbidden(), Forbidden()).transcribe(
        write_silence(tmp_path / "silence.wav")
    )
    assert result.no_speech is True
    assert result.turns == []


def test_local_speech_keeps_short_response_and_global_speaker(tmp_path):
    from meetinglog.engines.local_speech import LocalSpeech

    vad = SimpleNamespace(
        get_speech_timestamps=lambda *args, **kwargs: [{"start": 0.0, "end": 0.3}]
    )
    asr = SimpleNamespace(generate=lambda *args, **kwargs: SimpleNamespace(text="네"))
    aligner = SimpleNamespace(
        generate=lambda *args, **kwargs: [
            SimpleNamespace(text="네", start_time=0.05, end_time=0.25)
        ]
    )
    diarizer = SimpleNamespace(
        generate=lambda *args, **kwargs: SimpleNamespace(
            segments=[SimpleNamespace(start=0, end=0.3, speaker="speaker_0")]
        )
    )
    result = LocalSpeech(vad, asr, aligner, diarizer).transcribe(
        write_silence(tmp_path / "input.wav")
    )
    assert result.no_speech is False
    assert len(result.turns) == 1
    assert result.turns[0].text_original == "네"
    assert result.turns[0].end_ms - result.turns[0].start_ms == 200
    assert result.turns[0].speaker_id == result.speakers[0].id


def test_deduplicated_chunk_boundary_marks_only_the_affected_sentence(tmp_path, monkeypatch):
    from meetinglog.engines.local_speech import LocalSpeech
    from meetinglog.transcripts.assembly import assemble

    monkeypatch.setattr(
        "meetinglog.engines.local_speech.speech_windows", lambda *_: [(0, 1), (0, 1)]
    )
    texts = iter(["첫 문장입니다.", "첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다."])
    vad = SimpleNamespace(get_speech_timestamps=lambda *a, **k: [{"start": 0, "end": 1}])
    asr = SimpleNamespace(generate=lambda *a, **k: SimpleNamespace(text=next(texts)))
    aligner = SimpleNamespace(
        generate=lambda *a, **k: [
            SimpleNamespace(text=text, start_time=start, end_time=end)
            for text, start, end in [
                ("첫 문장입니다.", 0.1, 0.2),
                ("둘째 문장입니다.", 0.3, 0.4),
                ("셋째 문장입니다.", 0.5, 0.6),
            ]
            if text in k["text"]
        ]
    )
    diarizer = SimpleNamespace(
        generate=lambda *a, **k: SimpleNamespace(
            segments=[SimpleNamespace(start=0, end=1, speaker="a")]
        )
    )
    speech = LocalSpeech(vad, asr, aligner, diarizer).transcribe(
        write_silence(tmp_path / "input.wav")
    )
    turns = assemble(speech.turns)
    assert len(turns) == 1
    assert [s.text_original for s in turns[0].sentences] == [
        "첫 문장입니다.",
        "둘째 문장입니다.",
        "셋째 문장입니다.",
    ]
    assert [s.review_flags for s in turns[0].sentences] == [[], ["boundary_review"], []]
