from typing import Literal

from fastapi import APIRouter, Request, UploadFile
from pydantic import Field

from meetinglog.db import ApiError
from meetinglog.domain import Contract, Recording
from meetinglog.recordings.service import InputService

router = APIRouter(prefix="/api/recordings", tags=["recordings"])


class DraftInput(Contract):
    title: str = Field(default="새 녹음", max_length=200)
    source: Literal["microphone"] = "microphone"


class FinalizeInput(Contract):
    last_sequence: int = Field(ge=0)


def service(request: Request) -> InputService:
    return InputService(request.app.state.settings, request.app.state.db)


@router.post("", response_model=Recording, status_code=201)
def upload(request: Request, file: UploadFile):
    return service(request).import_file(
        file.filename or "녹음", iter(lambda: file.file.read(1024 * 1024), b"")
    )


@router.post("/drafts", response_model=Recording, status_code=201)
def draft(request: Request, body: DraftInput):
    return service(request).create(body.source, body.title)


@router.put("/{recording_id}/chunks/{sequence}")
async def chunk(request: Request, recording_id: str, sequence: int):
    buffer = bytearray()
    async for body in request.stream():
        buffer.extend(body)
        if len(buffer) > 32 * 1024 * 1024:
            raise ApiError(
                "chunk_too_large",
                "녹음 전송이 지연되었습니다. 녹음을 종료한 뒤 파일로 가져오세요",
                413,
            )
    return {"digest": service(request).append_chunk(recording_id, sequence, bytes(buffer))}


@router.post("/{recording_id}/finalize", response_model=Recording)
def finalize(request: Request, recording_id: str, body: FinalizeInput):
    return service(request).finalize(recording_id, body.last_sequence)
