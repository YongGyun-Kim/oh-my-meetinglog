from meetinglog.db import ApiError, require_recording
from meetinglog.domain import Transcript, new_id
from meetinglog.transcripts.repository import TranscriptRepository


class VersionConflict(ApiError):
    def __init__(self):
        super().__init__(
            "version_conflict", "다른 화면에서 수정되었습니다. 최신 전사를 확인하세요", 409
        )


class TranscriptService:
    def __init__(self, repository: TranscriptRepository):
        self.repository = repository

    def edit(self, recording_id: str, base_version_id: str, changes: list[dict]) -> Transcript:
        with self.repository.db.session(immediate=True) as connection:
            record = require_recording(connection, recording_id)
            if record["current_transcript_id"] != base_version_id:
                raise VersionConflict()
            original = self.repository.read(connection, base_version_id)
            result = original.model_copy(deep=True)
            result.id, result.parent_id = new_id(), original.id
            from meetinglog.domain import now

            result.created_at = now()
            turns, speakers = (
                {turn.id: turn for turn in result.turns},
                {speaker.id: speaker for speaker in result.speakers},
            )
            if not changes:
                raise ApiError("empty_edit", "수정할 내용을 입력하세요")
            for change in changes:
                if change.get("turn_id"):
                    turn = turns.get(change["turn_id"])
                    if turn is None:
                        raise ApiError("unknown_turn", "이 기록의 발언이 아닙니다")
                    if "text" in change:
                        if change["text"] is None or not change["text"].strip():
                            raise ApiError("empty_text", "발언을 빈 내용으로 저장할 수 없습니다")
                        turn.text_edited = change["text"]
                    if "speaker_id" in change:
                        if (
                            change["speaker_id"] is not None
                            and change["speaker_id"] not in speakers
                        ):
                            raise ApiError("unknown_speaker", "이 기록의 화자가 아닙니다")
                        turn.speaker_id = change["speaker_id"]
                elif change.get("speaker_id") in speakers and "role" in change:
                    speakers[change["speaker_id"]].role = change["role"]
                else:
                    raise ApiError("invalid_edit", "수정할 발언과 화자를 확인하세요")
            self.repository.insert(connection, result)
            return result

    def rename_speaker(self, recording_id: str, speaker_id: str, display_name: str) -> None:
        name = display_name.strip()
        if not name or len(name) > 100:
            raise ApiError("invalid_name", "화자 이름은 1~100자로 입력하세요")
        with self.repository.db.session(immediate=True) as connection:
            require_recording(connection, recording_id)
            if (
                connection.execute(
                    "UPDATE speaker_names SET display_name=? WHERE recording_id=? AND speaker_id=?",
                    (name, recording_id, speaker_id),
                ).rowcount
                != 1
            ):
                raise ApiError("unknown_speaker", "화자를 찾을 수 없습니다", 404)
