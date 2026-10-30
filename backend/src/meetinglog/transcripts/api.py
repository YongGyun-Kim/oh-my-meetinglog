from fastapi import APIRouter, Request
from pydantic import Field

from meetinglog.domain import Contract, Transcript
from meetinglog.transcripts.repository import TranscriptRepository
from meetinglog.transcripts.service import TranscriptService

router = APIRouter(prefix="/api/recordings", tags=["transcripts"])


class EditChange(Contract):
    sentence_id: str | None = None
    turn_id: str | None = None
    text: str | None = Field(default=None, max_length=20000)
    speaker_id: str | None = None
    role: str | None = Field(default=None, max_length=200)


class EditRequest(Contract):
    base_version_id: str
    changes: list[EditChange] = Field(min_length=1, max_length=1000)


class SpeakerNameRequest(Contract):
    display_name: str = Field(min_length=1, max_length=100)


def service(request: Request):
    return TranscriptService(TranscriptRepository(request.app.state.db))


@router.patch("/{recording_id}/transcript", response_model=Transcript)
def edit(request: Request, recording_id: str, body: EditRequest):
    return service(request).edit(
        recording_id,
        body.base_version_id,
        [change.model_dump(exclude_unset=True) for change in body.changes],
    )


@router.patch("/{recording_id}/speakers/{speaker_id}")
def rename(request: Request, recording_id: str, speaker_id: str, body: SpeakerNameRequest):
    service(request).rename_speaker(recording_id, speaker_id, body.display_name)
    return {"status": "ok"}
