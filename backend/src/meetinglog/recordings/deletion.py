import shutil

from meetinglog.config import Settings
from meetinglog.db import Database, require_recording
from meetinglog.domain import now
from meetinglog.recordings.storage import Storage


class DeletionService:
    def __init__(self, settings: Settings, db: Database):
        self.settings, self.db = settings, db

    def request(self, recording_id: str) -> None:
        with self.db.session(immediate=True) as connection:
            require_recording(connection, recording_id)
            connection.execute(
                "UPDATE recordings SET deleted_at=?,generation=generation+1 WHERE id=?",
                (now().isoformat(), recording_id),
            )
            connection.execute(
                "UPDATE jobs SET cancel_requested=1,state='cancelled' WHERE recording_id=? AND state IN ('queued','running','interrupted')",
                (recording_id,),
            )

    def cleanup_pending(self) -> int:
        # Sole worker only; its active child must already have exited.
        with self.db.session() as connection:
            pending = [
                row[0]
                for row in connection.execute(
                    "SELECT id FROM recordings WHERE deleted_at IS NOT NULL"
                )
            ]
        count = 0
        for identifier in pending:
            storage = Storage(self.settings.data_dir)
            with storage.input_lock(identifier, blocking=False) as acquired:
                if not acquired:
                    continue
                try:
                    shutil.rmtree(storage.directory(identifier))
                except FileNotFoundError:
                    pass
                except OSError:
                    continue
                with self.db.session(immediate=True) as connection:
                    count += connection.execute(
                        "DELETE FROM recordings WHERE id=? AND deleted_at IS NOT NULL",
                        (identifier,),
                    ).rowcount
        return count
