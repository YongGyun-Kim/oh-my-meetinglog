import json
import re

from meetinglog.analysis.input import AnalysisInput
from meetinglog.db import ApiError
from meetinglog.domain import AnalysisBody, FormAnalysisBody, Transcript


class GroundingError(ApiError):
    def __init__(self, code: str, feedback: str | None = None):
        if code == "empty_analysis":
            message = "분석 결과에 내용이 없어요. 다시 분석해 주세요."
        elif code in ("invalid_section", "invalid_comparison", "invalid_actions", "empty_action"):
            message = "분석 결과가 선택한 양식과 맞지 않아요. 다시 분석해 주세요."
        else:
            message = "분석의 근거가 전사와 일치하지 않아요. 다시 분석해 주세요."
        super().__init__(code, message, 503)
        self.feedback = feedback or code


def validate_grounding(
    body: AnalysisBody | FormAnalysisBody, transcript: Transcript | AnalysisInput
) -> None:
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
                    raise GroundingError(
                        "unknown_sentence",
                        "unknown_sentence: "
                        + json.dumps(value, ensure_ascii=False)
                        + "의 근거 ID는 입력에 없다. 실제 입력 문장 ID로 수정한다.",
                    )
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(body.model_dump())
    errors = []
    for action in body.actions:
        if isinstance(body, FormAnalysisBody) and not action.text.strip():
            errors.append(
                GroundingError(
                    "empty_action",
                    "actions의 text에는 수행할 행동을 반드시 적는다. owner_text에는 담당자 이름·역할만 적는다.",
                )
            )
        if action.owner_speaker_id is not None and action.owner_speaker_id not in speakers:
            errors.append(
                GroundingError(
                    "unknown_speaker",
                    "unknown_speaker: "
                    + action.model_dump_json()
                    + "의 담당자 ID는 화자 목록에 없다. 불명확하면 null로 둔다.",
                )
            )
        owner = getattr(action, "owner_text", None)
        if owner is not None:
            if action.owner_speaker_id is not None:
                errors.append(
                    GroundingError(
                        "ambiguous_owner",
                        "ambiguous_owner: "
                        + action.model_dump_json()
                        + "의 담당자는 owner_text 또는 owner_speaker_id 중 하나로만 기록한다. "
                        "화자 목록의 ID·표시 이름을 owner_text에 복사하지 않는다. 불명확하면 두 필드를 null로 두고 행동은 유지한다.",
                    )
                )
            evidence = "".join(turns[item] for item in action.evidence_sentence_ids)
            if not owner.strip() or re.sub(r"\s+", "", owner) not in re.sub(r"\s+", "", evidence):
                errors.append(
                    GroundingError(
                        "unspoken_owner",
                        "unspoken_owner: "
                        + action.model_dump_json()
                        + "의 owner_text는 근거 발언에 없는 담당자다. "
                        "화자 목록의 ID·표시 이름은 담당자 이름의 근거가 아니다. "
                        "발언에 직접 나온 담당자 표현만 쓰고 불명확하면 null로 두되 행동은 유지한다.",
                    )
                )
        if action.due_text:
            evidence = "".join(turns[item] for item in action.evidence_sentence_ids)
            if re.sub(r"\s+", "", action.due_text) not in re.sub(r"\s+", "", evidence):
                errors.append(
                    GroundingError(
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
                )
    if errors:
        errors[0].feedback = "\n".join(error.feedback for error in errors)
        raise errors[0]
