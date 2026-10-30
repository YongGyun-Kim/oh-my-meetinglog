import json
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from meetinglog.db import ApiError


@dataclass(frozen=True)
class MediaInfo:
    duration_ms: int
    sample_rate: int
    channels: int
    codec: str


def tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ApiError("media_tools_missing", "FFmpeg를 설치한 뒤 다시 시도하세요", 503)
    return path


def probe(path: Path) -> MediaInfo:
    try:
        result = subprocess.run(
            [
                tool("ffprobe"),
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        audio = next(stream for stream in data["streams"] if stream["codec_type"] == "audio")
        duration = float(data.get("format", {}).get("duration", audio.get("duration", 0)))
        rate, channels = int(audio["sample_rate"]), int(audio["channels"])
        if duration <= 0 or not math.isfinite(duration):
            # MediaRecorder WebM is a stream: its header may omit duration.
            # Decode to a null sink and read the final audio clock, preserving the original.
            decoded = subprocess.run(
                [
                    tool("ffmpeg"),
                    "-nostdin",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-i",
                    str(path),
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-progress",
                    "pipe:1",
                    "-nostats",
                    "-f",
                    "null",
                    "-",
                ],
                check=True,
                capture_output=True,
                timeout=180,
            )
            timestamps = [
                int(line.split("=", 1)[1])
                for line in decoded.stdout.decode().splitlines()
                if line.startswith("out_time_us=") and line.split("=", 1)[1].lstrip("-").isdigit()
            ]
            duration = max(timestamps, default=0) / 1_000_000
        if not math.isfinite(duration) or duration <= 0 or rate <= 0 or channels <= 0:
            raise ValueError
        return MediaInfo(round(duration * 1000), rate, channels, audio["codec_name"])
    except (subprocess.SubprocessError, ValueError, KeyError, StopIteration, OSError) as error:
        raise ApiError(
            "invalid_audio", "읽을 수 있는 음성이 없습니다. 다른 파일을 선택하세요"
        ) from error


def normalize(source: Path, destination: Path) -> MediaInfo:
    destination.parent.mkdir(parents=True, exist_ok=True)
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
                "-i",
                str(source),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(destination),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
    except (subprocess.SubprocessError, OSError) as error:
        raise ApiError("decode_failed", "음성 변환에 실패했습니다") from error
    return probe(destination)


def prepare_playback(source: Path, destination: Path) -> None:
    try:
        with tempfile.TemporaryDirectory(prefix="playback-", dir=destination.parent) as temporary:
            output = Path(temporary) / f"audio{destination.suffix}"
            subprocess.run(
                [
                    tool("ffmpeg"),
                    "-nostdin",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-i",
                    str(source),
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-c:a",
                    "copy" if destination.suffix == ".webm" else "pcm_s16le",
                    str(output),
                ],
                check=True,
                capture_output=True,
                timeout=180,
            )
            output.replace(destination)
    except (subprocess.SubprocessError, OSError) as error:
        raise ApiError(
            "playback_failed", "재생용 음성을 준비하지 못했어요. 다시 시도해 주세요.", 503
        ) from error
