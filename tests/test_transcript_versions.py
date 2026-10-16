import pytest
from meetinglog.db import ApiError
from meetinglog.domain import Speaker, SpeechResult, Turn


@pytest.fixture
def versioned(input_service, db):
    from meetinglog.transcripts.repository import TranscriptRepository
    from meetinglog.transcripts.service import TranscriptService

    record = input_service.create("microphone", "인터뷰")
    speech = SpeechResult(
        provider="test",
        model="fixture",
        speakers=[Speaker(id="a", display_name="화자 A"), Speaker(id="b", display_name="화자 B")],
        turns=[
            Turn(id="t1", start_ms=0, end_ms=200, speaker_id="a", text_original="네"),
            Turn(
                id="t2",
                start_ms=300,
                end_ms=1200,
                speaker_id="b",
                text_original="다음 주에 시작합니다",
            ),
        ],
    )
    repository = TranscriptRepository(db)
    original = repository.save_generated(record.id, speech, 0)
    return TranscriptService(repository), original, record


def test_edit_preserves_original_and_rejects_stale_base(versioned):
    from meetinglog.transcripts.service import VersionConflict

    service, original, _ = versioned
    edited = service.edit(
        original.recording_id, original.id, [{"turn_id": "t2", "text": "이번 주에 시작합니다"}]
    )
    assert edited.parent_id == original.id
    assert edited.turns[1].text_original == "다음 주에 시작합니다"
    assert edited.turns[1].text_edited == "이번 주에 시작합니다"
    assert service.repository.get(original.id).turns[1].text_edited is None
    with pytest.raises(VersionConflict):
        service.edit(original.recording_id, original.id, [{"turn_id": "t1", "text": "아니요"}])


def test_unknown_speaker_or_foreign_turn_is_rejected(versioned):
    service, original, _ = versioned
    for change in [
        {"turn_id": "t1", "speaker_id": "foreign"},
        {"turn_id": "foreign", "text": "변경"},
    ]:
        with pytest.raises(ApiError):
            service.edit(original.recording_id, original.id, [change])
    assert service.repository.current(original.recording_id).id == original.id


def test_name_updates_without_version_but_role_creates_version(versioned):
    service, original, _ = versioned
    speaker_id = original.speakers[0].id
    service.rename_speaker(original.recording_id, speaker_id, "인터뷰어")
    current = service.repository.current(original.recording_id)
    assert current.id == original.id
    assert current.speakers[0].display_name == "인터뷰어"
    edited = service.edit(
        original.recording_id, original.id, [{"speaker_id": speaker_id, "role": "질문자"}]
    )
    assert edited.id != original.id
    assert edited.speakers[0].role == "질문자"
    assert service.repository.get(original.id).speakers[0].role is None


def test_generation_guard_prevents_deleted_record_resurrection(versioned, db):
    service, original, record = versioned
    with db.session() as connection:
        connection.execute(
            "UPDATE recordings SET generation=1,deleted_at='deleted' WHERE id=?", (record.id,)
        )
    with pytest.raises(ApiError):
        service.edit(record.id, original.id, [{"turn_id": "t1", "text": "다른 내용"}])
