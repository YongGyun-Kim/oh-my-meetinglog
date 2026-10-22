import json

from meetinglog.analysis.input import AnalysisInput
from meetinglog.analysis.prompts import messages
from meetinglog.db import ApiError
from meetinglog.domain import AnalysisForm


def chunk_input(
    transcript: AnalysisInput, max_bytes: int = 16000, form: AnalysisForm = "meeting"
) -> list[AnalysisInput]:
    empty = transcript.model_copy(update={"lines": []})

    def size(turns):
        return len(
            json.dumps(
                messages(empty.model_copy(update={"lines": turns}), form=form),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        )

    # 단어별 시각과 원문 이력은 전송하지 않으므로 실제 요청 본문만 계산한다.
    budget = (max_bytes - size([]) - 600) // 3
    if budget < 100:
        raise ApiError("context_limit", "화자 정보가 분석 입력 한도를 초과했습니다", 503)
    atoms = []
    for turn in transcript.lines:
        remaining = turn.text.encode()
        while remaining:
            piece = remaining[:budget].decode("utf-8", errors="ignore")
            remaining = remaining[len(piece.encode()) :]
            atoms.append(turn.model_copy(update={"text": piece}))
    chunks, current = [], []
    for atom in atoms:
        if current and (
            any(item.id == atom.id for item in current) or size([*current, atom]) > max_bytes
        ):
            chunks.append(empty.model_copy(update={"lines": current}))
            current = [item for item in current[-2:] if item.id != atom.id]
        while current and size([*current, atom]) > max_bytes:
            current = current[1:]
        if size([*current, atom]) > max_bytes:
            raise ApiError("context_limit", "한 발언이 분석 입력 한도를 초과했습니다", 503)
        current.append(atom)
    if current:
        chunks.append(empty.model_copy(update={"lines": current}))
    return chunks
