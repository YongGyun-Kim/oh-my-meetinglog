import json

from meetinglog.domain import SpeechResult, Transcript
from meetinglog.transcripts.repository import TranscriptRepository


def test_generated_transcript_groups_speaker_and_keeps_sentence_times(input_service, db):
    record = input_service.create("microphone", "문장 전사")
    speech = SpeechResult.model_validate(
        {
            "provider": "test",
            "model": "fixed",
            "speakers": [{"id": "a", "display_name": "화자 A"}],
            "turns": [
                {
                    "id": "s1",
                    "speaker_id": "a",
                    "start_ms": 0,
                    "end_ms": 1000,
                    "text_original": "초안입니다.",
                    "words": [{"text": "초안입니다.", "start_ms": 0, "end_ms": 1000}],
                },
                {
                    "id": "s2",
                    "speaker_id": "a",
                    "start_ms": 5000,
                    "end_ms": 6500,
                    "text_original": "내일 보냅니다.",
                    "review_flags": ["speaker_boundary"],
                    "words": [
                        {"text": "내일", "start_ms": 5000, "end_ms": 5500},
                        {"text": "보냅니다.", "start_ms": 5600, "end_ms": 6500},
                    ],
                },
                {
                    "id": "s3",
                    "speaker_id": None,
                    "start_ms": 7000,
                    "end_ms": 7500,
                    "text_original": "네",
                },
                {
                    "id": "s4",
                    "speaker_id": "a",
                    "start_ms": 8000,
                    "end_ms": 9000,
                    "text_original": "감사합니다.",
                },
            ],
        }
    )
    transcript = TranscriptRepository(db).save_generated(record.id, speech, 0)
    assert len(transcript.turns) == 3
    assert [sentence.text_original for sentence in transcript.turns[0].sentences] == [
        "초안입니다.",
        "내일 보냅니다.",
    ]
    assert [(sentence.start_ms, sentence.end_ms) for sentence in transcript.turns[0].sentences] == [
        (0, 1000),
        (5000, 6500),
    ]
    assert "speaker_boundary" in transcript.turns[0].sentences[1].review_flags
    assert transcript.turns[0].sentences[0].review_flags == []
    assert transcript.turns[1].speaker_id is None
    with db.session() as connection:
        payload = json.loads(
            connection.execute(
                "SELECT payload FROM transcripts WHERE id=?", (transcript.id,)
            ).fetchone()[0]
        )
    assert set(payload["turns"][0]) == {"id", "speaker_id", "sentences"}
    assert "words" not in payload["turns"][0]["sentences"][0]


def test_legacy_transcript_keeps_citation_ids_and_edits_without_rewriting_input():
    payload = {
        "id": "old",
        "recording_id": "recording",
        "speakers": [{"id": "a", "display_name": "화자 A"}],
        "turns": [
            {
                "id": "t1",
                "speaker_id": "a",
                "start_ms": 0,
                "end_ms": 1000,
                "text_original": "첫 발언",
            },
            {
                "id": "t2",
                "speaker_id": "a",
                "start_ms": 2000,
                "end_ms": 3000,
                "text_original": "자동 전사",
                "text_edited": "수정한 발언",
                "review_flags": ["boundary_review"],
            },
        ],
    }
    transcript = Transcript.model_validate(payload)
    assert len(transcript.turns) == 1
    assert [sentence.id for sentence in transcript.turns[0].sentences] == ["t1", "t2"]
    assert transcript.turns[0].sentences[1].text_edited == "수정한 발언"
    assert "sentences" not in payload["turns"][0]


def test_sentence_boundaries_preserve_decimal_and_cross_processing_chunks():
    from meetinglog.domain import SpeechSegment
    from meetinglog.transcripts.assembly import assemble

    segments = [
        SpeechSegment.model_validate(
            {
                "id": "a",
                "speaker_id": "speaker",
                "start_ms": 0,
                "end_ms": 1000,
                "text_original": "버전은 1.2입니다. 다음은",
                "words": [
                    {"text": "버전은", "start_ms": 0, "end_ms": 200},
                    {"text": "1.2입니다.", "start_ms": 250, "end_ms": 500},
                    {"text": "다음은", "start_ms": 700, "end_ms": 1000},
                ],
            }
        ),
        SpeechSegment.model_validate(
            {
                "id": "b",
                "speaker_id": "speaker",
                "start_ms": 5000,
                "end_ms": 6000,
                "text_original": "3입니다!",
                "words": [{"text": "3입니다!", "start_ms": 5000, "end_ms": 6000}],
            }
        ),
    ]
    result = assemble(segments)
    assert len(result) == 1
    assert [sentence.text_original for sentence in result[0].sentences] == [
        "버전은 1.2입니다.",
        "다음은 3입니다!",
    ]
    assert [(sentence.start_ms, sentence.end_ms) for sentence in result[0].sentences] == [
        (0, 500),
        (700, 6000),
    ]
    assert segments[0].text_original == "버전은 1.2입니다. 다음은"


def test_incomplete_alignment_does_not_invent_sentence_times():
    from meetinglog.domain import SpeechSegment
    from meetinglog.transcripts.assembly import assemble

    segment = SpeechSegment.model_validate(
        {
            "id": "x",
            "speaker_id": "a",
            "start_ms": 0,
            "end_ms": 2000,
            "text_original": "첫 문장입니다. 다음 문장입니다.",
            "words": [{"text": "첫", "start_ms": 0, "end_ms": 200}],
        }
    )
    sentence = assemble([segment])[0].sentences[0]
    assert sentence.text_original == "첫 문장입니다. 다음 문장입니다."
    assert (sentence.start_ms, sentence.end_ms) == (0, 2000)
    assert "alignment_uncertain" in sentence.review_flags


def test_provider_sentence_times_survive_when_word_alignment_is_absent():
    from meetinglog.domain import SpeechSegment
    from meetinglog.transcripts.assembly import assemble

    result = assemble(
        [
            SpeechSegment(
                id="first", speaker_id="a", start_ms=0, end_ms=1000, text_original="첫 문장입니다."
            ),
            SpeechSegment(
                id="second",
                speaker_id="a",
                start_ms=2000,
                end_ms=3000,
                text_original="둘째 문장입니다.",
            ),
        ]
    )
    assert len(result) == 1
    assert [(sentence.start_ms, sentence.end_ms) for sentence in result[0].sentences] == [
        (0, 1000),
        (2000, 3000),
    ]


def test_editing_one_sentence_reassigns_only_its_speaker(input_service, db):
    from meetinglog.transcripts.service import TranscriptService

    record = input_service.create("microphone", "문장 수정")
    repository = TranscriptRepository(db)
    transcript = Transcript.model_validate(
        {
            "id": "v1",
            "recording_id": record.id,
            "speakers": [{"id": "a", "display_name": "A"}, {"id": "b", "display_name": "B"}],
            "turns": [
                {
                    "id": "one",
                    "speaker_id": "a",
                    "sentences": [
                        {"id": "s1", "start_ms": 0, "end_ms": 1000, "text_original": "첫 문장"},
                        {
                            "id": "s2",
                            "start_ms": 1000,
                            "end_ms": 2000,
                            "text_original": "둘째 문장",
                        },
                    ],
                }
            ],
        }
    )
    with db.session() as connection:
        repository.insert(connection, transcript)
    edited = TranscriptService(repository).edit(
        record.id, "v1", [{"sentence_id": "s2", "text": "수정한 둘째 문장", "speaker_id": "b"}]
    )
    assert [turn.speaker_id for turn in edited.turns] == ["a", "b"]
    assert edited.turns[1].sentences[0].text_original == "둘째 문장"
    assert edited.turns[1].sentences[0].text_edited == "수정한 둘째 문장"
    assert len(repository.get("v1").turns) == 1
