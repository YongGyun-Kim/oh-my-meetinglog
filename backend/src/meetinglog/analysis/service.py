import json
from pathlib import Path
from typing import Protocol

from meetinglog.analysis.chunking import chunk_transcript
from meetinglog.analysis.grounding import GroundingError, validate_grounding
from meetinglog.analysis.prompts import PROMPT_VERSION
from meetinglog.config import Settings
from meetinglog.db import ApiError, Database
from meetinglog.domain import (
    AnalysisBody,
    AnalysisVersion,
    Job,
    Mode,
    Overview,
    Transcript,
    new_id,
)
from meetinglog.engines.policy import EnginePolicy
from meetinglog.transcripts.repository import TranscriptRepository, assert_publishable


class AnalysisEngine(Protocol):
    provider: str
    model: str

    def generate(self, transcript: Transcript, feedback: str | None = None) -> AnalysisBody: ...
    def summarize(self, overviews: list[Overview]) -> Overview: ...


def unique(values):
    seen, result = set(), []
    for value in values:
        key = json.dumps(value.model_dump(), sort_keys=True, ensure_ascii=False)
        if key not in seen:
            result.append(value)
            seen.add(key)
    return result


def analyze_with(engine: AnalysisEngine, transcript: Transcript) -> AnalysisBody:
    parts = chunk_transcript(transcript)
    if not parts:
        raise ApiError("no_speech", "분석할 발언이 없습니다", 409)
    bodies = []
    for part in parts:
        feedback = None
        for attempt in range(2):
            body = engine.generate(part, feedback)
            try:
                validate_grounding(body, part)
                break
            except GroundingError as error:
                if attempt:
                    raise
                feedback = error.code
        bodies.append(body)
    overviews = [body.overview for body in bodies]
    while len(overviews) > 1:
        groups, group, size = [], [], 0
        for overview in overviews:
            encoded = len(overview.model_dump_json().encode())
            if encoded > 14000:
                raise ApiError("context_limit", "구간 요약이 입력 한도를 초과했습니다", 503)
            if group and size + encoded > 14000:
                groups.append(group)
                group, size = [], 0
            group.append(overview)
            size += encoded
        if group:
            groups.append(group)
        if all(len(group) == 1 for group in groups):
            raise ApiError("context_limit", "전체 요약을 안전한 입력 크기로 합치지 못했습니다", 503)
        overviews = [engine.summarize(group) if len(group) > 1 else group[0] for group in groups]
    merged = AnalysisBody(
        overview=overviews[0],
        topics=sorted(
            unique([topic for body in bodies for topic in body.topics]),
            key=lambda topic: topic.start_ms,
        ),
        question_answers=unique([item for body in bodies for item in body.question_answers]),
        agreements=unique([item for body in bodies for item in body.agreements]),
        open_questions=unique([item for body in bodies for item in body.open_questions]),
        actions=unique([item for body in bodies for item in body.actions]),
    )
    validate_grounding(merged, transcript)
    return merged


class AnalysisService:
    def __init__(self, db: Database, settings: Settings | None = None, *, event_path=None):
        self.db, self.settings = db, settings or Settings()
        self.events = []
        self.event_path = event_path

    def generate(
        self, transcript_id: str, mode: Mode, producer_job_id: str | None = None
    ) -> AnalysisVersion:
        transcript = TranscriptRepository(self.db).get(transcript_id)
        return self.generate_from(transcript, mode)

    def generate_from(self, transcript: Transcript, mode: Mode) -> AnalysisVersion:
        from meetinglog.engines.cloud_analysis import CloudAnalysis
        from meetinglog.engines.local_analysis import LocalAnalysis

        if not transcript.turns:
            raise ApiError("no_speech", "분석할 발언이 없습니다", 409)
        local_engine, local_error, revisions = None, None, {}
        if mode != "api":
            try:
                local_engine = LocalAnalysis(self.settings)
                digest = local_engine.digest()
                if digest:
                    revisions["analysis"] = digest
            except ApiError as error:
                local_error = error
        policy = EnginePolicy(self.settings, revisions, event_path=self.event_path)
        self.events = policy.events

        def run(engine):
            return AnalysisVersion(
                id=new_id(),
                transcript_id=transcript.id,
                body=analyze_with(engine, transcript),
                provider=engine.provider,
                model=engine.model,
                prompt_version=PROMPT_VERSION,
            )

        def run_local():
            if local_error:
                raise local_error
            return run(local_engine)

        version = policy.execute(
            "analysis",
            mode,
            max(turn.end_ms for turn in transcript.turns),
            run_local,
            lambda: run(CloudAnalysis(self.settings)),
        )
        self.events = policy.events
        return version

    def publish(self, job: Job, path: Path) -> AnalysisVersion:
        version = AnalysisVersion.model_validate_json(path.read_text())
        with self.db.session(immediate=True) as connection:
            assert_publishable(connection, job.recording_id, job.generation, job.id)
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job.id,)).fetchone()
            if row["transcript_id"] != version.transcript_id:
                raise ApiError("version_conflict", "분석의 기준 전사가 달라졌습니다", 409)
            existing = connection.execute(
                "SELECT payload FROM analyses WHERE producer_job_id=?", (job.id,)
            ).fetchone()
            if existing:
                return AnalysisVersion.model_validate_json(existing[0])
            transcript = TranscriptRepository(self.db).read(connection, version.transcript_id)
            validate_grounding(version.body, transcript)
            connection.execute(
                "INSERT INTO analyses VALUES (?,?,?,?,?,?)",
                (
                    version.id,
                    job.recording_id,
                    version.transcript_id,
                    job.id,
                    version.created_at.isoformat(),
                    version.model_dump_json(),
                ),
            )
            connection.execute(
                "UPDATE jobs SET analysis_artifact=?,stage='complete' WHERE id=?",
                (str(path), job.id),
            )
            return version
