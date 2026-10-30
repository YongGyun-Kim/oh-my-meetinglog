from meetinglog.domain import Contract, Speaker, Transcript


class InputLine(Contract):
    id: str
    speaker_id: str | None
    text: str


class AnalysisInput(Contract):
    speakers: list[Speaker]
    lines: list[InputLine]


def prepare_input(transcript: Transcript):
    references = {}
    speakers = {f"s{index}": speaker.id for index, speaker in enumerate(transcript.speakers, 1)}
    aliases = {original: alias for alias, original in speakers.items()}
    lines = []
    for index, (speaker_id, sentence) in enumerate(transcript.entries(), 1):
        identifier = f"t{index}"
        references[identifier] = sentence.id
        lines.append(
            InputLine(
                id=identifier,
                speaker_id=aliases[speaker_id] if speaker_id else None,
                text=sentence.text_edited
                if sentence.text_edited is not None
                else sentence.text_original,
            )
        )
    return (
        AnalysisInput(
            speakers=[
                speaker.model_copy(update={"id": aliases[speaker.id]})
                for speaker in transcript.speakers
            ],
            lines=lines,
        ),
        references,
        speakers,
    )
