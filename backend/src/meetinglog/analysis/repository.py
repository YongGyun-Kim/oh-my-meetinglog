from meetinglog.db import Database, require_recording
from meetinglog.domain import AnalysisVersion


class AnalysisRepository:
    def __init__(self, db: Database):
        self.db = db

    def current(self, recording_id: str) -> AnalysisVersion | None:
        with self.db.session() as connection:
            require_recording(connection, recording_id)
            row = connection.execute(
                "SELECT payload FROM analyses WHERE recording_id=? ORDER BY created_at DESC LIMIT 1",
                (recording_id,),
            ).fetchone()
            return AnalysisVersion.model_validate_json(row[0]) if row else None
