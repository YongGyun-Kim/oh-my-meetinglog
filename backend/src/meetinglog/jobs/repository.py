import json
from contextlib import nullcontext

from meetinglog.db import ApiError, Database, require_recording
from meetinglog.domain import Job, Mode, StageResult, new_id, now


def as_job(row) -> Job:
    return Job.model_validate({name: row[name] for name in Job.model_fields if name in row.keys()})


class JobRepository:
    def __init__(self, db: Database):
        self.db = db

    def enqueue(
        self, recording_id: str, kind: str, transcript_id: str | None, mode: Mode, connection=None
    ) -> Job:
        with (
            nullcontext(connection) if connection is not None else self.db.session(immediate=True)
        ) as connection:
            record = require_recording(connection, recording_id)
            if record["input_state"] != "ready":
                raise ApiError("input_not_ready", "녹음 저장이 완료된 뒤 처리할 수 있습니다", 409)
            if kind == "analyze":
                if (
                    not transcript_id
                    or not connection.execute(
                        "SELECT 1 FROM transcripts WHERE id=? AND recording_id=?",
                        (transcript_id, recording_id),
                    ).fetchone()
                ):
                    raise ApiError("unknown_transcript", "분석할 전사를 확인하세요", 422)
            existing = connection.execute(
                "SELECT * FROM jobs WHERE recording_id=? AND state IN ('queued','running','interrupted')",
                (recording_id,),
            ).fetchone()
            if existing:
                if (
                    existing["kind"] == kind
                    and existing["mode"] == mode
                    and existing["transcript_id"] == transcript_id
                ):
                    return as_job(existing)
                raise ApiError("job_active", "이 기록은 이미 처리 중입니다", 409)
            stamp, job_id = now().isoformat(), new_id()
            connection.execute(
                "INSERT INTO jobs(id,recording_id,transcript_id,kind,state,stage,generation,mode,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    job_id,
                    recording_id,
                    transcript_id,
                    kind,
                    "queued",
                    "speech" if kind == "process" else "analysis",
                    record["generation"],
                    mode,
                    stamp,
                    stamp,
                ),
            )
            return as_job(connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def ensure_initial(self, recording_id: str, mode: Mode) -> Job:
        with self.db.session(immediate=True) as connection:
            record = require_recording(connection, recording_id)
            if record["initial_job_id"]:
                row = connection.execute(
                    "SELECT * FROM jobs WHERE id=?", (record["initial_job_id"],)
                ).fetchone()
                if row:
                    return as_job(row)
            job = self.enqueue(recording_id, "process", None, mode, connection=connection)
            connection.execute(
                "UPDATE recordings SET initial_job_id=? WHERE id=?", (job.id, recording_id)
            )
            return job

    def get(self, job_id: str) -> Job:
        with self.db.session() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise ApiError("not_found", "작업을 찾을 수 없습니다", 404)
            require_recording(connection, row["recording_id"])
            return as_job(row)

    def raw(self, job_id: str):
        with self.db.session() as connection:
            return connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()

    def recover(self):
        with self.db.session(immediate=True) as connection:
            connection.execute(
                "UPDATE jobs SET state='interrupted',updated_at=? WHERE state='running' AND cancel_requested=0",
                (now().isoformat(),),
            )
            connection.execute(
                "UPDATE jobs SET state='cancelled' WHERE cancel_requested=1 AND state IN ('queued','running','interrupted')"
            )

    def claim(self) -> Job | None:
        with self.db.session(immediate=True) as connection:
            row = connection.execute(
                "SELECT j.* FROM jobs j JOIN recordings r ON r.id=j.recording_id WHERE j.state IN ('queued','interrupted') AND j.cancel_requested=0 AND r.deleted_at IS NULL AND r.generation=j.generation ORDER BY j.created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE jobs SET state='running',attempts=attempts+1,updated_at=?,heartbeat=? WHERE id=?",
                (now().isoformat(), now().isoformat(), row["id"]),
            )
            return as_job(
                connection.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
            )

    def cancelled(self, job_id: str) -> bool:
        with self.db.session() as connection:
            row = connection.execute(
                "SELECT j.state,j.cancel_requested,j.generation,r.generation AS current_generation,r.deleted_at FROM jobs j LEFT JOIN recordings r ON r.id=j.recording_id WHERE j.id=?",
                (job_id,),
            ).fetchone()
            return (
                row is None
                or row["state"] != "running"
                or bool(row["cancel_requested"])
                or row["deleted_at"] is not None
                or row["generation"] != row["current_generation"]
            )

    def cancel(self, job_id: str):
        with self.db.session(immediate=True) as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise ApiError("not_found", "작업을 찾을 수 없습니다", 404)
            require_recording(connection, row["recording_id"])
            connection.execute(
                "UPDATE jobs SET cancel_requested=1,state='cancelled',updated_at=? WHERE id=? AND state IN ('queued','running','interrupted')",
                (now().isoformat(), job_id),
            )

    def heartbeat(self, job_id: str):
        with self.db.session() as connection:
            connection.execute(
                "UPDATE jobs SET heartbeat=? WHERE id=? AND state='running'",
                (now().isoformat(), job_id),
            )

    def event(
        self, job_id: str, stage: str, event: str, metadata: dict, source_key: str | None = None
    ):
        with self.db.session() as connection:
            if connection.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
                connection.execute(
                    "INSERT OR IGNORE INTO job_events(job_id,created_at,stage,event,metadata,source_key) VALUES (?,?,?,?,?,?)",
                    (
                        job_id,
                        now().isoformat(),
                        stage,
                        event,
                        json.dumps(metadata, ensure_ascii=False),
                        source_key,
                    ),
                )

    def commit_stage(self, result: StageResult) -> bool:
        with self.db.session(immediate=True) as connection:
            row = connection.execute(
                "SELECT j.*,r.generation AS current_generation,r.deleted_at FROM jobs j JOIN recordings r ON r.id=j.recording_id WHERE j.id=?",
                (result.job_id,),
            ).fetchone()
            if (
                row is None
                or row["state"] != "running"
                or row["cancel_requested"]
                or row["deleted_at"] is not None
                or row["generation"] != result.generation
                or row["current_generation"] != result.generation
            ):
                return False
            if row["stage"] != result.stage:
                return False
            column = "speech_artifact" if result.stage == "speech" else "analysis_artifact"
            stage = "analysis" if result.stage == "speech" else "complete"
            connection.execute(
                f"UPDATE jobs SET {column}=?,stage=?,updated_at=? WHERE id=?",
                (result.artifact_path, stage, now().isoformat(), result.job_id),
            )
            connection.execute(
                "INSERT INTO job_events(job_id,created_at,stage,event,metadata) VALUES (?,?,?,?,?)",
                (
                    result.job_id,
                    now().isoformat(),
                    result.stage,
                    "stage_completed",
                    json.dumps(result.metadata, ensure_ascii=False),
                ),
            )
            return True

    def finish(
        self, job_id: str, state: str, error: ApiError | None = None, stage: str | None = None
    ):
        with self.db.session() as connection:
            connection.execute(
                "UPDATE jobs SET state=?,error_code=?,error_message=?,updated_at=?,stage=COALESCE(?,stage) WHERE id=? AND state='running' AND cancel_requested=0",
                (
                    state,
                    error.code if error else None,
                    error.message if error else None,
                    now().isoformat(),
                    stage,
                    job_id,
                ),
            )
