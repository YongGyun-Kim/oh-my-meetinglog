import wave
from pathlib import Path


def write_silence(path: Path, seconds: int = 1, rate: int = 16000, channels: int = 1) -> Path:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\0\0" * rate * seconds * channels)
    return path
