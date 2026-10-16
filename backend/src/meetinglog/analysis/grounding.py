import re

from meetinglog.db import ApiError
from meetinglog.domain import AnalysisBody, Transcript


class GroundingError(ApiError):
    def __init__(self, code: str):
        super().__init__(code, "분석의 근거가 전사와 일치하지 않습니다", 503)


def validate_grounding(body: AnalysisBody, transcript: Transcript) -> None:
    turns = {turn.id: turn for turn in transcript.turns}
    speakers = {speaker.id for speaker in transcript.speakers}

    def visit(value):
        if isinstance(value, dict):
            if "evidence_turn_ids" in value:
                ids = value["evidence_turn_ids"]
                if not ids or any(identifier not in turns for identifier in ids):
                    raise GroundingError("unknown_turn")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(body.model_dump())
    end = max((turn.end_ms for turn in transcript.turns), default=0)
    for topic in body.topics:
        if not 0 <= topic.start_ms < topic.end_ms <= end:
            raise GroundingError("invalid_topic_time")
    for action in body.actions:
        if action.owner_speaker_id is not None and action.owner_speaker_id not in speakers:
            raise GroundingError("unknown_speaker")
        if action.due_text:
            evidence = "".join(
                turns[item].text_edited or turns[item].text_original
                for item in action.evidence_turn_ids
            )
            if re.sub(r"\s+", "", action.due_text) not in re.sub(r"\s+", "", evidence):
                raise GroundingError("unspoken_due_date")
