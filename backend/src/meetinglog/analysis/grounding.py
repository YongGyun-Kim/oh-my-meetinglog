import json
import re

from meetinglog.analysis.input import AnalysisInput
from meetinglog.db import ApiError
from meetinglog.domain import AnalysisBody, Transcript


class GroundingError(ApiError):
    def __init__(self, code: str, feedback: str | None = None):
        super().__init__(code, "분석의 근거가 전사와 일치하지 않습니다", 503)
        self.feedback = feedback or code


def validate_grounding(body: AnalysisBody, transcript: Transcript | AnalysisInput) -> None:
    turns = (
        {
            sentence.id: sentence.text_edited
            if sentence.text_edited is not None
            else sentence.text_original
            for _, sentence in transcript.entries()
        }
        if isinstance(transcript, Transcript)
        else {line.id: line.text for line in transcript.lines}
    )
    speakers = {speaker.id for speaker in transcript.speakers}

    def visit(value):
        if isinstance(value, dict):
            if "evidence_sentence_ids" in value:
                ids = value["evidence_sentence_ids"]
                if not ids or any(identifier not in turns for identifier in ids):
                    raise GroundingError("unknown_sentence")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(body.model_dump())
    for action in body.actions:
        if action.owner_speaker_id is not None and action.owner_speaker_id not in speakers:
            raise GroundingError("unknown_speaker")
        if action.due_text:
            evidence = "".join(turns[item] for item in action.evidence_sentence_ids)
            if re.sub(r"\s+", "", action.due_text) not in re.sub(r"\s+", "", evidence):
                raise GroundingError(
                    "unspoken_due_date",
                    "unspoken_due_date: "
                    + json.dumps(
                        {
                            "due_text": action.due_text,
                            "evidence_sentence_ids": action.evidence_sentence_ids,
                        },
                        ensure_ascii=False,
                    )
                    + "의 기한은 근거 발언에 없다. 해당 발언의 표현을 그대로 사용하거나 due_text를 null로 둔다.",
                )
