from dataclasses import dataclass

from meetinglog.domain import Turn, Word, new_id


@dataclass(frozen=True)
class SpeakerSpan:
    speaker_id: str
    start_ms: int
    end_ms: int


def intersection(start, end, other_start, other_end):
    return max(0, min(end, other_end) - max(start, other_start))


def assign_speaker(start: int, end: int, spans: list[SpeakerSpan]):
    active = [span for span in spans if intersection(start, end, span.start_ms, span.end_ms)]
    if not active:
        return None, ["unknown_speaker"]
    for index, left in enumerate(active):
        if any(
            left.speaker_id != right.speaker_id
            and max(start, left.start_ms, right.start_ms) < min(end, left.end_ms, right.end_ms)
            for right in active[index + 1 :]
        ):
            return None, ["overlap", "unknown_speaker"]
    scores = {}
    for span in active:
        scores[span.speaker_id] = scores.get(span.speaker_id, 0) + intersection(
            start, end, span.start_ms, span.end_ms
        )
    best = max(scores, key=scores.get)
    if scores[best] < (end - start) * 0.5:
        return None, ["unknown_speaker"]
    return best, ["speaker_boundary"] if len(scores) > 1 else []


def duplicate_word(word: Word, earlier: list[Word]) -> bool:
    return any(
        other.text == word.text
        and abs(other.start_ms - word.start_ms) < 250
        and intersection(word.start_ms, word.end_ms, other.start_ms, other.end_ms)
        >= min(word.end_ms - word.start_ms, other.end_ms - other.start_ms) * 0.7
        for other in earlier[-100:]
    )


def deduplicate_words(words: list[Word]) -> list[Word]:
    result = []
    for word in sorted(words, key=lambda item: item.start_ms):
        if not duplicate_word(word, result):
            result.append(word)
    return result


def align_turns(
    text: str, words: list[Word], speakers: list[SpeakerSpan], offset_ms: int
) -> list[Turn]:
    if not text.strip():
        return []
    absolute = [
        word.model_copy(
            update={
                "start_ms": word.start_ms + offset_ms,
                "end_ms": max(word.end_ms, word.start_ms + 1) + offset_ms,
            }
        )
        for word in words
    ]
    cursor, pieces = 0, []
    for word in words:
        position = text.find(word.text, cursor)
        if position < 0:
            pieces = []
            break
        end = position + len(word.text)
        pieces.append(text[cursor:end])
        cursor = end
    if not pieces:
        start, end = (
            (absolute[0].start_ms, absolute[-1].end_ms) if absolute else (offset_ms, offset_ms + 1)
        )
        speaker, flags = assign_speaker(start, end, speakers)
        return [
            Turn(
                id=new_id(),
                start_ms=start,
                end_ms=max(start + 1, end),
                speaker_id=speaker,
                text_original=text,
                review_flags=[*flags, "alignment_uncertain"],
                words=absolute,
            )
        ]
    pieces[-1] += text[cursor:]
    turns = []
    for word, piece in zip(absolute, pieces, strict=True):
        speaker, flags = assign_speaker(word.start_ms, word.end_ms, speakers)
        if (
            turns
            and turns[-1].speaker_id == speaker
            and turns[-1].review_flags == flags
            and word.start_ms - turns[-1].end_ms < 1200
        ):
            turns[-1].text_original += piece
            turns[-1].end_ms = max(turns[-1].end_ms, word.end_ms)
            turns[-1].words.append(word)
        else:
            turns.append(
                Turn(
                    id=new_id(),
                    start_ms=word.start_ms,
                    end_ms=word.end_ms,
                    speaker_id=speaker,
                    text_original=piece,
                    review_flags=flags,
                    words=[word],
                )
            )
    for turn in turns:
        turn.text_original = turn.text_original.strip()
    return turns
