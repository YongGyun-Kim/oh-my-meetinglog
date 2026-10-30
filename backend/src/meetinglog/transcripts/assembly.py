import re

from meetinglog.domain import Sentence, SpeechSegment, group_sentences, new_id


def assemble(segments: list[SpeechSegment]):
    merged = []
    for source in segments:
        segment = source.model_copy(deep=True)
        for word in segment.words:
            # 구버전은 단어별 판정이 없으므로 원래 구간의 검토 정보를 보존한다.
            if word.review_flags is None:
                word.review_flags = list(segment.review_flags)
        if (
            segment.speaker_id is not None
            and merged
            and merged[-1].speaker_id == segment.speaker_id
            and segment.words
            and merged[-1].words
            and segment.text_edited is None
            and merged[-1].text_edited is None
        ):
            previous = merged[-1]
            previous.text_original = (
                previous.text_original.rstrip() + " " + segment.text_original.lstrip()
            )
            previous.end_ms = max(previous.end_ms, segment.end_ms)
            previous.words.extend(segment.words)
            previous.review_flags = list(
                dict.fromkeys([*previous.review_flags, *segment.review_flags])
            )
        else:
            merged.append(segment)
    entries = []
    for segment in merged:
        text = segment.text_original
        boundaries = [
            match.end() for match in re.finditer(r"""[.!?。！？]+["'”’」』)\]]*(?=\s|$)""", text)
        ]
        if not boundaries or boundaries[-1] != len(text):
            boundaries.append(len(text))
        spans, cursor = [], 0
        for word in segment.words:
            start = text.find(word.text, cursor)
            if start < 0:
                spans = []
                break
            cursor = start + len(word.text)
            spans.append((start, cursor, word))
        cursor = 0
        covered = bool(spans)
        for start, end, _ in spans:
            if any(character.isalnum() for character in text[cursor:start]):
                covered = False
            cursor = end
        covered = covered and not any(character.isalnum() for character in text[cursor:])
        aligned = (
            covered
            and segment.text_edited is None
            and not any(
                start < boundary < end for boundary in boundaries for start, end, _ in spans
            )
        )
        # 정렬이 없으면 문장별 시각을 추측하지 않고 원래 구간을 보존한다.
        if not aligned:
            boundaries = [len(text)]
        offset = 0
        for index, boundary in enumerate(boundaries):
            piece = text[offset:boundary].strip()
            words = [word for start, end, word in spans if start < boundary and end > offset]
            offset = boundary
            if not piece:
                continue
            flags = (
                list(dict.fromkeys(flag for word in words for flag in word.review_flags or []))
                if aligned
                else list(segment.review_flags)
            )
            if not aligned:
                flags = list(dict.fromkeys([*flags, "alignment_uncertain"]))
            sentence = Sentence(
                id=segment.id if index == 0 else new_id(),
                start_ms=words[0].start_ms if aligned and words else segment.start_ms,
                end_ms=words[-1].end_ms if aligned and words else segment.end_ms,
                text_original=piece,
                text_edited=segment.text_edited,
                review_flags=flags,
            )
            entries.append((segment.speaker_id, sentence))
    return group_sentences(entries)
