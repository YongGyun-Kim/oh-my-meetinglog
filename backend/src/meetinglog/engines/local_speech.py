import gc
import tempfile
from pathlib import Path

import soundfile as sf

from meetinglog.domain import Speaker, SpeechResult, Word, new_id
from meetinglog.domain import SpeechSegment as Turn
from meetinglog.recordings.alignment import SpeakerSpan, align_turns, duplicate_word
from meetinglog.recordings.storage import atomic_json


class LazyModel:
    def __init__(self, path: Path, kind: str):
        self.path, self.kind, self.model = path, kind, None

    def load(self):
        if self.model is None:
            if self.kind == "stt":
                from mlx_audio.stt import load
            else:
                from mlx_audio.vad import load
            self.model = load(str(self.path), strict=True)
        return self.model

    def generate(self, *args, **kwargs):
        return self.load().generate(*args, **kwargs)

    def get_speech_timestamps(self, *args, **kwargs):
        return self.load().get_speech_timestamps(*args, **kwargs)

    def unload(self):
        self.model = None
        gc.collect()
        import mlx.core as mx

        mx.clear_cache()


def unload(model):
    if hasattr(model, "unload"):
        model.unload()


def speech_windows(regions: list[dict], duration: float):
    merged = []
    for region in regions:
        start, end = max(0.0, float(region["start"])), min(duration, float(region["end"]))
        if end <= start:
            continue
        if merged and start <= merged[-1][1] + 0.4:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    for start, end in merged:
        while start < end:
            stop = min(start + 30, end)
            yield start, stop
            if stop == end:
                break
            start = stop - 0.8


class LocalSpeech:
    def __init__(self, vad, asr, aligner, diarizer):
        self.vad, self.asr, self.aligner, self.diarizer = vad, asr, aligner, diarizer

    def transcribe(self, path: Path) -> SpeechResult:
        regions = self.vad.get_speech_timestamps(
            str(path), min_speech_duration_ms=100, speech_pad_ms=200, return_seconds=True
        )
        unload(self.vad)
        if not regions:
            return SpeechResult(
                turns=[], speakers=[], no_speech=True, provider="local", model="qwen3-asr+nemotron3"
            )
        audio, rate = sf.read(path, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        chunks, raw = [], {"asr": [], "alignment": [], "diarization": []}
        with tempfile.TemporaryDirectory(prefix="speech-", dir=path.parent) as temporary:
            for index, (start, end) in enumerate(speech_windows(regions, len(audio) / rate)):
                chunk_path = Path(temporary) / f"{index}.wav"
                sf.write(chunk_path, audio[int(start * rate) : int(end * rate)], rate)
                text = self.asr.generate(str(chunk_path), language="Korean").text.strip()
                raw["asr"].append({"start": start, "end": end, "text": text})
                chunks.append(
                    {"path": chunk_path, "start": start, "end": end, "text": text, "words": []}
                )
            unload(self.asr)
            for chunk in chunks:
                if not chunk["text"]:
                    continue
                try:
                    aligned = self.aligner.generate(
                        audio=str(chunk["path"]), text=chunk["text"], language="Korean"
                    )
                    chunk["words"] = [
                        Word(
                            text=item.text,
                            start_ms=max(0, round(item.start_time * 1000)),
                            end_ms=max(1, round(item.end_time * 1000)),
                        )
                        for item in aligned
                        if item.text.strip()
                    ]
                except (ValueError, RuntimeError):
                    chunk["words"] = []
                raw["alignment"].append(
                    {
                        "start": chunk["start"],
                        "words": [word.model_dump() for word in chunk["words"]],
                    }
                )
            unload(self.aligner)
        diarized = self.diarizer.generate(str(path), min_duration=0.0, merge_gap=0.0)
        spans = [
            SpeakerSpan(
                str(segment.speaker),
                max(0, round(segment.start * 1000)),
                max(1, round(segment.end * 1000)),
            )
            for segment in diarized.segments
        ]
        raw["diarization"] = [
            {"speaker": span.speaker_id, "start_ms": span.start_ms, "end_ms": span.end_ms}
            for span in spans
        ]
        unload(self.diarizer)
        ids = list(
            dict.fromkeys(span.speaker_id for span in sorted(spans, key=lambda item: item.start_ms))
        )
        mapping = {speaker: new_id() for speaker in ids}
        speakers = [
            Speaker(id=mapping[speaker], display_name=f"화자 {chr(65 + index)}")
            for index, speaker in enumerate(ids)
        ]
        kept_words, turns = [], []
        for chunk in chunks:
            if not chunk["text"]:
                continue
            offset = round(chunk["start"] * 1000)
            if chunk["words"]:
                candidates = align_turns(chunk["text"], chunk["words"], spans, offset)
            else:
                candidates = [
                    Turn(
                        id=new_id(),
                        start_ms=offset,
                        end_ms=max(offset + 1, round(chunk["end"] * 1000)),
                        text_original=chunk["text"],
                        review_flags=["alignment_uncertain", "unknown_speaker"],
                    )
                ]
            for turn in candidates:
                fresh = [word for word in turn.words if not duplicate_word(word, kept_words)]
                if turn.words and not fresh:
                    continue
                if fresh and len(fresh) != len(turn.words):
                    position = turn.text_original.find(fresh[0].text)
                    if position >= 0:
                        turn.text_original = turn.text_original[position:]
                        turn.start_ms = fresh[0].start_ms
                    turn.review_flags.append("boundary_review")
                    word_flags = fresh[0].review_flags
                    if word_flags is None:
                        word_flags = turn.review_flags
                    fresh[0].review_flags = list(dict.fromkeys([*word_flags, "boundary_review"]))
                    turn.words = fresh
                kept_words.extend(fresh)
                turn.speaker_id = mapping.get(turn.speaker_id)
                turns.append(turn)
        raw_path = path.with_suffix(".speech-raw.json")
        atomic_json(raw_path, raw)
        return SpeechResult(
            turns=turns,
            speakers=speakers,
            no_speech=not turns,
            provider="local",
            model="qwen3-asr+nemotron3",
            raw_artifact=str(raw_path),
        )


def prepared_speech(settings):
    from meetinglog.engines.models import ModelRegistry

    registry = ModelRegistry(settings)
    paths = {name: registry.require(name) for name in ("vad", "asr", "aligner", "diarizer")}
    return LocalSpeech(
        LazyModel(paths["vad"], "vad"),
        LazyModel(paths["asr"], "stt"),
        LazyModel(paths["aligner"], "stt"),
        LazyModel(paths["diarizer"], "vad"),
    )
