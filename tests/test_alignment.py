from meetinglog.domain import Word


def test_short_response_and_source_offset_are_preserved():
    from meetinglog.recordings.alignment import SpeakerSpan, align_turns

    turns = align_turns(
        "네", [Word(text="네", start_ms=0, end_ms=200)], [SpeakerSpan("a", 1000, 1300)], 1000
    )
    assert len(turns) == 1
    assert (turns[0].start_ms, turns[0].end_ms, turns[0].speaker_id) == (1000, 1200, "a")


def test_overlapping_speakers_are_not_forced_to_one_person():
    from meetinglog.recordings.alignment import SpeakerSpan, align_turns

    turns = align_turns(
        "동의합니다",
        [Word(text="동의합니다", start_ms=100, end_ms=300)],
        [SpeakerSpan("a", 0, 250), SpeakerSpan("b", 150, 400)],
        0,
    )
    assert turns[0].speaker_id is None
    assert "overlap" in turns[0].review_flags


def test_unknown_speaker_is_marked_and_source_text_is_not_rewritten():
    from meetinglog.recordings.alignment import align_turns

    text = "아니요, 15만 원입니다."
    turns = align_turns(text, [Word(text="다른 단어", start_ms=0, end_ms=500)], [], 0)
    assert turns[0].text_original == text
    assert turns[0].speaker_id is None
    assert "alignment_uncertain" in turns[0].review_flags


def test_boundary_deduplication_keeps_distinct_short_responses():
    from meetinglog.recordings.alignment import deduplicate_words

    words = [
        Word(text="네", start_ms=0, end_ms=200),
        Word(text="네", start_ms=20, end_ms=210),
        Word(text="네", start_ms=300, end_ms=500),
    ]
    assert [(word.start_ms, word.end_ms) for word in deduplicate_words(words)] == [
        (0, 200),
        (300, 500),
    ]


def test_word_review_locations_survive_without_splitting_a_speaker_turn():
    from meetinglog.recordings.alignment import SpeakerSpan, align_turns
    from meetinglog.transcripts.assembly import assemble

    segments = align_turns(
        "처음입니다. 경계입니다. 다음입니다.",
        [
            Word(text="처음입니다.", start_ms=0, end_ms=500),
            Word(text="경계입니다.", start_ms=1500, end_ms=1700),
            Word(text="다음입니다.", start_ms=1800, end_ms=2200),
        ],
        [SpeakerSpan("a", 0, 1600), SpeakerSpan("b", 1600, 3000)],
        0,
    )
    assert segments[0].words[0].review_flags == []
    assert segments[0].words[1].review_flags == ["speaker_boundary"]
    turns = assemble(segments)
    assert len(turns) == 2
    assert [sentence.text_original for sentence in turns[0].sentences] == [
        "처음입니다.",
        "경계입니다.",
    ]
    assert [sentence.review_flags for turn in turns for sentence in turn.sentences] == [
        [],
        ["speaker_boundary"],
        [],
    ]
