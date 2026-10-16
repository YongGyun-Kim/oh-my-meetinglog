from meetinglog.db import ApiError
from meetinglog.domain import Transcript


def chunk_transcript(transcript: Transcript, max_bytes: int = 16000) -> list[Transcript]:
    empty = transcript.model_copy(update={"turns": []})
    budget = (max_bytes - len(empty.model_dump_json().encode()) - 600) // 3
    if budget < 100:
        raise ApiError("context_limit", "화자 정보가 분석 입력 한도를 초과했습니다", 503)
    atoms = []
    for turn in transcript.turns:
        remaining = (turn.text_edited or turn.text_original).encode()
        while remaining:
            piece = remaining[:budget].decode("utf-8", errors="ignore")
            remaining = remaining[len(piece.encode()) :]
            atoms.append(turn.model_copy(update={"text_original": piece, "text_edited": None}))
    chunks, current = [], []
    for atom in atoms:
        candidate = empty.model_copy(update={"turns": [*current, atom]})
        if current and (
            any(item.id == atom.id for item in current)
            or len(candidate.model_dump_json().encode()) > max_bytes
        ):
            chunks.append(empty.model_copy(update={"turns": current}))
            current = [item for item in current[-2:] if item.id != atom.id]
        while (
            current
            and len(empty.model_copy(update={"turns": [*current, atom]}).model_dump_json().encode())
            > max_bytes
        ):
            current = current[1:]
        if (
            len(empty.model_copy(update={"turns": [*current, atom]}).model_dump_json().encode())
            > max_bytes
        ):
            raise ApiError("context_limit", "한 발언이 분석 입력 한도를 초과했습니다", 503)
        current.append(atom)
    if current:
        chunks.append(empty.model_copy(update={"turns": current}))
    return chunks
