from pathlib import Path
from typing import Protocol

from meetinglog.analysis.chunking import chunk_input
from meetinglog.analysis.forms import canonicalize
from meetinglog.analysis.grounding import GroundingError, validate_grounding
from meetinglog.analysis.input import AnalysisInput, prepare_input
from meetinglog.analysis.prompts import PROMPT_VERSION
from meetinglog.config import Settings
from meetinglog.db import ApiError, Database
from meetinglog.domain import (
    AnalysisForm,
    AnalysisVersion,
    FormAnalysisBody,
    Job,
    Mode,
    Transcript,
    new_id,
)
from meetinglog.engines.policy import EnginePolicy
from meetinglog.transcripts.repository import TranscriptRepository, assert_publishable


class AnalysisEngine(Protocol):
    provider: str
    model: str

    def generate(
        self, transcript: AnalysisInput, feedback: str | None = None
    ) -> FormAnalysisBody: ...
    def merge(
        self, bodies: list[FormAnalysisBody], feedback: str | None = None
    ) -> FormAnalysisBody: ...


def analyze_with(
    engine: AnalysisEngine, transcript: Transcript, progress=None, form: AnalysisForm = "meeting"
) -> FormAnalysisBody:
    source = transcript
    transcript, sentence_ids, speaker_ids = prepare_input(source)
    parts = chunk_input(transcript, form=form)
    if not parts:
        raise ApiError("no_speech", "분석할 발언이 없습니다", 409)

    def checked(produce, evidence):
        feedback = None
        for attempt in range(2):
            body = produce(feedback)
            try:
                body = canonicalize(body, form, final=False)
                validate_grounding(body, evidence)
                return body
            except GroundingError as error:
                if attempt:
                    raise
                feedback = error.feedback

    bodies = []
    completed, total = 0, 2 * len(parts) - 1
    for part in parts:
        bodies.append(checked(lambda feedback, part=part: engine.generate(part, feedback), part))
        completed += 1
        if progress:
            progress(completed, total)
    while len(bodies) > 1:
        merged = []
        for index in range(0, len(bodies), 2):
            pair = bodies[index : index + 2]
            if len(pair) == 1:
                merged.append(pair[0])
                continue
            references = {
                identifier
                for body in pair
                for section in body.sections
                for fact in [
                    *[fact for group in section.groups for fact in group.paragraphs],
                    *[fact for choice in section.comparisons for fact in choice.points],
                    *section.actions,
                ]
                for identifier in fact.evidence_sentence_ids
            }
            evidence = transcript.model_copy(
                update={"lines": [line for line in transcript.lines if line.id in references]}
            )
            merged.append(
                checked(lambda feedback, pair=pair: engine.merge(pair, feedback), evidence)
            )
            completed += 1
            if progress:
                progress(completed, total)
        bodies = merged
    result = canonicalize(bodies[0], form)

    def restore(value):
        if isinstance(value, dict):
            if "evidence_sentence_ids" in value:
                value["evidence_sentence_ids"] = [
                    sentence_ids[identifier] for identifier in value["evidence_sentence_ids"]
                ]
            if value.get("owner_speaker_id") is not None:
                value["owner_speaker_id"] = speaker_ids[value["owner_speaker_id"]]
            for child in value.values():
                restore(child)
        elif isinstance(value, list):
            for child in value:
                restore(child)

    data = result.model_dump()
    restore(data)
    result = FormAnalysisBody.model_validate(data)
    validate_grounding(result, source)
    return result


class AnalysisService:
    def __init__(self, db: Database, settings: Settings | None = None, *, event_path=None):
        self.db, self.settings = db, settings or Settings()
        self.events = []
        self.event_path = event_path

    def generate(
        self,
        transcript_id: str,
        mode: Mode,
        producer_job_id: str | None = None,
        form: AnalysisForm = "meeting",
    ) -> AnalysisVersion:
        transcript = TranscriptRepository(self.db).get(transcript_id)
        return self.generate_from(transcript, mode, form)

    def generate_from(
        self, transcript: Transcript, mode: Mode, form: AnalysisForm = "meeting"
    ) -> AnalysisVersion:
        from meetinglog.engines.cloud_analysis import CloudAnalysis
        from meetinglog.engines.local_analysis import LocalAnalysis, unload_ollama

        if not transcript.turns:
            raise ApiError("no_speech", "분석할 발언이 없습니다", 409)
        local_engine, local_error, revisions = None, None, {}
        if mode != "api":
            try:
                local_engine = LocalAnalysis(self.settings, form=form)
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
                body=analyze_with(
                    engine,
                    transcript,
                    form=form,
                    progress=lambda completed, total: policy.record(
                        {
                            "stage": "analysis",
                            "event": "analysis_progress",
                            "completed": completed,
                            "total": total,
                        }
                    ),
                ),
                provider=engine.provider,
                model=engine.model,
                prompt_version=PROMPT_VERSION,
                form=form,
            )

        def run_local():
            if local_error:
                raise local_error
            return run(local_engine)

        try:
            version = policy.execute(
                "analysis",
                mode,
                max(sentence.end_ms for _, sentence in transcript.entries()),
                run_local,
                lambda: run(CloudAnalysis(self.settings, form=form)),
            )
        finally:
            if local_engine:
                local_engine.client.close()
                unload_ollama(self.settings)
        self.events = policy.events
        return version

    def publish(self, job: Job, path: Path) -> AnalysisVersion:
        version = AnalysisVersion.model_validate_json(path.read_text())
        with self.db.session(immediate=True) as connection:
            assert_publishable(connection, job.recording_id, job.generation, job.id)
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job.id,)).fetchone()
            if row["transcript_id"] != version.transcript_id or job.form != version.form:
                raise ApiError("version_conflict", "분석의 기준 전사가 달라졌습니다", 409)
            existing = connection.execute(
                "SELECT payload FROM analyses WHERE producer_job_id=?", (job.id,)
            ).fetchone()
            if existing:
                return AnalysisVersion.model_validate_json(existing[0])
            transcript = TranscriptRepository(self.db).read(connection, version.transcript_id)
            if isinstance(version.body, FormAnalysisBody):
                version.body = canonicalize(version.body, version.form)
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
