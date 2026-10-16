import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from meetinglog.db import ApiError


def atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as target:
            target.write(body)
            target.flush()
            os.fsync(target.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, body: dict) -> None:
    atomic_write(path, json.dumps(body, ensure_ascii=False).encode())


class Storage:
    def __init__(self, data_dir: Path):
        self.root = (data_dir / "recordings").resolve()

    def directory(self, recording_id: str) -> Path:
        try:
            if str(UUID(recording_id)) != recording_id:
                raise ValueError
        except ValueError as error:
            raise ApiError("not_found", "기록을 찾을 수 없습니다", 404) from error
        return self.root / recording_id

    @contextmanager
    def input_lock(self, recording_id: str, *, blocking: bool = True):
        self.directory(recording_id)  # Validate before forming the lock filename.
        path = self.root.parent / "input-locks" / f"{recording_id}.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
