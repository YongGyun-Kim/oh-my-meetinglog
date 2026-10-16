from datetime import UTC, datetime
from typing import Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

Mode = Literal["auto", "local_only", "api"]


def now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Recording(Contract):
    id: str
    title: str
    source: Literal["microphone", "file"]
    input_state: Literal["recording", "uploading", "ready", "invalid"]
    duration_ms: int | None = None
    created_at: datetime = Field(default_factory=now)
    generation: int = 0


class Word(Contract):
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class Turn(Contract):
    id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    speaker_id: str | None = None
    text_original: str = Field(min_length=1)
    text_edited: str | None = None
    review_flags: list[str] = Field(default_factory=list)
    words: list[Word] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_time(self) -> Self:
        if self.end_ms <= self.start_ms or not self.text_original.strip():
            raise ValueError("발언의 시간과 원문을 확인하세요")
        return self


class Speaker(Contract):
    id: str
    display_name: str
    role: str | None = None


class Transcript(Contract):
    id: str
    recording_id: str
    parent_id: str | None = None
    turns: list[Turn]
    speakers: list[Speaker]
    created_at: datetime = Field(default_factory=now)

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        if len({turn.id for turn in self.turns}) != len(self.turns):
            raise ValueError("발언 ID가 중복되었습니다")
        if len({speaker.id for speaker in self.speakers}) != len(self.speakers):
            raise ValueError("화자 ID가 중복되었습니다")
        return self


class Fact(Contract):
    text: str
    evidence_turn_ids: list[str] = Field(min_length=1)


class Overview(Contract):
    kind: Literal["interview", "counseling", "conversation", "unknown"]
    summary: Fact
    main_topics: list[Fact]


class Topic(Contract):
    title: str
    start_ms: int
    end_ms: int
    discussion: list[Fact]
    different_views: list[Fact]
    conclusion: Fact | None
    evidence_turn_ids: list[str] = Field(min_length=1)


class QuestionAnswer(Contract):
    question: Fact
    answer: Fact | None


class Action(Contract):
    text: str
    owner_speaker_id: str | None
    due_text: str | None
    evidence_turn_ids: list[str] = Field(min_length=1)


class AnalysisBody(Contract):
    overview: Overview
    topics: list[Topic]
    question_answers: list[QuestionAnswer]
    agreements: list[Fact]
    open_questions: list[Fact]
    actions: list[Action]


class AnalysisVersion(Contract):
    id: str
    transcript_id: str
    body: AnalysisBody
    provider: str
    model: str
    prompt_version: str
    created_at: datetime = Field(default_factory=now)


class Job(Contract):
    id: str
    recording_id: str
    transcript_id: str | None = None
    kind: Literal["process", "analyze"]
    state: str
    stage: str
    generation: int
    mode: Mode
    created_at: datetime = Field(default_factory=now)


class SpeechResult(Contract):
    turns: list[Turn]
    speakers: list[Speaker]
    no_speech: bool = False
    provider: str
    model: str
    raw_artifact: str = ""


class StageRequest(Contract):
    job_id: str
    recording_id: str
    generation: int
    stage: str
    input_path: str
    output_path: str
    mode: Mode


class StageResult(Contract):
    job_id: str
    generation: int
    stage: str
    artifact_path: str
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
