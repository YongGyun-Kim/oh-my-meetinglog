import base64
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from meetinglog.db import ApiError
from meetinglog.domain import new_id
from meetinglog.recordings.media import probe, tool


@dataclass(frozen=True)
class AudioPart:
    path: Path
    offset_ms: int
    overlap_ms: int


def encode(source: Path, destination: Path, start: float = 0, duration: float | None = None):
    command = [
        tool("ffmpeg"),
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-protocol_whitelist",
        "file,pipe",
        "-ss",
        str(start),
        "-i",
        str(source),
    ]
    if duration is not None:
        command += ["-t", str(duration)]
    command += ["-vn", "-ac", "1", "-ar", "16000", "-b:a", "24k", str(destination)]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=180)
    except (subprocess.SubprocessError, OSError) as error:
        raise ApiError("encode_failed", "외부 처리용 음성 변환에 실패했습니다", 503) from error


def prepare_uploads(path: Path, max_bytes: int = 24_000_000) -> list[AudioPart]:
    directory = path.parent / "cloud" / new_id()
    directory.mkdir(parents=True)
    whole = directory / "whole.mp3"
    encode(path, whole)
    if whole.stat().st_size <= max_bytes:
        return [AudioPart(whole, 0, 0)]
    duration = probe(path).duration_ms / 1000
    detection = subprocess.run(
        [
            tool("ffmpeg"),
            "-nostdin",
            "-hide_banner",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(path),
            "-af",
            "silencedetect=noise=-35dB:d=0.3",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        timeout=180,
    )
    boundaries = [
        float(value)
        for value in re.findall(
            r"silence_end: ([0-9.]+)", detection.stderr.decode(errors="replace")
        )
    ]
    nominal = max(0.5, (max_bytes - 1024) / 3000)
    overlap = min(0.8, nominal / 4)
    parts, start = [], 0.0
    while start < duration:
        length = min(nominal, duration - start)
        nearby = [
            boundary for boundary in boundaries if start + length - 1.5 < boundary <= start + length
        ]
        if nearby and max(nearby) - start > overlap + 0.1:
            length = max(nearby) - start
        target = directory / f"part-{len(parts):04d}.mp3"
        while True:
            encode(path, target, start, length)
            if target.stat().st_size <= max_bytes:
                break
            length *= 0.7
            if length <= overlap + 0.05:
                raise ApiError("upload_limit", "외부 처리용 파일 크기를 맞추지 못했습니다", 413)
        parts.append(
            AudioPart(target, round(start * 1000), 0 if not parts else round(overlap * 1000))
        )
        if start + length >= duration - 0.001:
            break
        start += length - overlap
    whole.unlink(missing_ok=True)
    return parts


def reference_data_url(source: Path, start: float, duration: float, target: Path) -> str:
    try:
        subprocess.run(
            [
                tool("ffmpeg"),
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-protocol_whitelist",
                "file,pipe",
                "-ss",
                str(start),
                "-i",
                str(source),
                "-t",
                str(min(duration, 10)),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(target),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as error:
        raise ApiError("reference_failed", "화자 참조 음성을 만들지 못했습니다", 503) from error
    return "data:audio/wav;base64," + base64.b64encode(target.read_bytes()).decode("ascii")
