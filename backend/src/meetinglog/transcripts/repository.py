from contextlib import nullcontext

from meetinglog.db import ApiError, Database, require_recording
from meetinglog.domain import SpeechResult, Transcript, new_id
from meetinglog.transcripts.assembly import assemble


def assert_publishable(connection, recording_id: str, generation: int, job_id: str | None = None):
    record = require_recording(connection, recording_id)
    if record["generation"] != generation:
        raise ApiError("stale_generation", "기록이 변경되어 결과를 저장할 수 없습니다", 409)
    if job_id:
        job = connection.execute(
            "SELECT * FROM jobs WHERE id=? AND recording_id=?", (job_id, recording_id)
        ).fetchone()
        if job is None or job["state"] != "running" or job["cancel_requested"]:
            raise ApiError("job_cancelled", "취소되거나 종료된 작업입니다", 409)
    return record


class TranscriptRepository:
    def __init__(self, db: Database):
        self.db = db

    def read(self, connection, transcript_id: str) -> Transcript:
        row = connection.execute(
            "SELECT * FROM transcripts WHERE id=?", (transcript_id,)
        ).fetchone()
        if row is None:
            raise ApiError("not_found", "전사 버전을 찾을 수 없습니다", 404)
        require_recording(connection, row["recording_id"])
        transcript = Transcript.model_validate_json(row["payload"])
        names = {
            item["speaker_id"]: item["display_name"]
            for item in connection.execute(
                "SELECT * FROM speaker_names WHERE recording_id=?", (transcript.recording_id,)
            )
        }
        for speaker in transcript.speakers:
            speaker.display_name = names.get(speaker.id, speaker.display_name)
        return transcript

    def get(self, transcript_id: str) -> Transcript:
        with self.db.session() as connection:
            return self.read(connection, transcript_id)

    def current(self, recording_id: str) -> Transcript | None:
        with self.db.session() as connection:
            record = require_recording(connection, recording_id)
            return (
                self.read(connection, record["current_transcript_id"])
                if record["current_transcript_id"]
                else None
            )

    def insert(self, connection, transcript: Transcript, producer_job_id: str | None = None):
        connection.execute(
            "INSERT INTO transcripts VALUES (?,?,?,?,?,?)",
            (
                transcript.id,
                transcript.recording_id,
                transcript.parent_id,
                producer_job_id,
                transcript.created_at.isoformat(),
                transcript.model_dump_json(),
            ),
        )
        for speaker in transcript.speakers:
            connection.execute(
                "INSERT OR IGNORE INTO speaker_names VALUES (?,?,?)",
                (transcript.recording_id, speaker.id, speaker.display_name),
            )
        connection.execute(
            "UPDATE recordings SET current_transcript_id=? WHERE id=?",
            (transcript.id, transcript.recording_id),
        )

    def save_generated(
        self,
        recording_id: str,
        speech: SpeechResult,
        expected_generation: int,
        producer_job_id: str | None = None,
        connection=None,
    ) -> Transcript:
        with (
            nullcontext(connection) if connection is not None else self.db.session(immediate=True)
        ) as connection:
            record = assert_publishable(
                connection, recording_id, expected_generation, producer_job_id
            )
            if producer_job_id:
                previous = connection.execute(
                    "SELECT id FROM transcripts WHERE producer_job_id=?", (producer_job_id,)
                ).fetchone()
                if previous:
                    return self.read(connection, previous[0])
            # A new inference run does not establish a match to previous anonymous voices.
            mapping = {speaker.id: new_id() for speaker in speech.speakers}
            speakers = [
                speaker.model_copy(update={"id": mapping[speaker.id]})
                for speaker in speech.speakers
            ]
            turns = []
            for turn in speech.turns:
                if turn.speaker_id is not None and turn.speaker_id not in mapping:
                    raise ApiError(
                        "invalid_speech_output", "음성 엔진의 화자 결과가 올바르지 않습니다", 503
                    )
                turns.append(turn.model_copy(update={"speaker_id": mapping.get(turn.speaker_id)}))
            transcript = Transcript(
                id=new_id(),
                recording_id=recording_id,
                parent_id=record["current_transcript_id"],
                turns=assemble(turns),
                speakers=speakers,
            )
            self.insert(connection, transcript, producer_job_id)
            return transcript
