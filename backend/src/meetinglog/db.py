import fcntl
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def session(self, immediate: bool = False):
        connection = self.connect()
        try:
            if immediate:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(".schema.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.session() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
            with self.session(immediate=True) as connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)"
                )
                for migration in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
                    if connection.execute(
                        "SELECT 1 FROM schema_migrations WHERE version=?", (migration.name,)
                    ).fetchone():
                        continue
                    statement = ""
                    for line in migration.read_text().splitlines(keepends=True):
                        statement += line
                        if sqlite3.complete_statement(statement):
                            connection.execute(statement)
                            statement = ""
                    if statement.strip():
                        raise ValueError(f"Incomplete migration: {migration.name}")
                    connection.execute(
                        "INSERT INTO schema_migrations VALUES (?)", (migration.name,)
                    )


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 422, retryable: bool = False):
        self.code, self.message, self.status, self.retryable = code, message, status, retryable
        super().__init__(message)


def require_recording(connection, recording_id: str):
    row = connection.execute(
        "SELECT * FROM recordings WHERE id=? AND deleted_at IS NULL", (recording_id,)
    ).fetchone()
    if row is None:
        raise ApiError("not_found", "기록을 찾을 수 없습니다", 404)
    return row
