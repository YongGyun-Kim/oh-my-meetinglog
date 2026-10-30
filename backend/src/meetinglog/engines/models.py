import json
from pathlib import Path

from meetinglog.config import Settings
from meetinglog.db import ApiError
from meetinglog.recordings.storage import atomic_json


class ModelRegistry:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.models_dir.resolve()
        self.manifest = self.root / "manifest.json"
        self.repositories = {
            "asr": settings.asr_repo,
            "aligner": settings.aligner_repo,
            "vad": settings.vad_repo,
            "diarizer": settings.diarizer_repo,
            "whisper": "mlx-community/whisper-large-v3-mlx",
        }

    def read(self) -> dict:
        try:
            return json.loads(self.manifest.read_text())
        except (OSError, ValueError):
            return {"schema_version": 1, "models": {}}

    def require(self, name: str) -> Path:
        try:
            entry = self.read()["models"][name]
            path = (self.root / entry["path"]).resolve()
            if (
                entry["repo_id"] != self.repositories[name]
                or not entry["revision"]
                or not path.is_relative_to(self.root)
            ):
                raise ValueError
            files = entry["files"]
            if "config.json" not in files or not any(
                key.endswith((".safetensors", ".npz")) for key in files
            ):
                raise ValueError
            for filename, size in files.items():
                target = (path / filename).resolve()
                if not target.is_relative_to(path) or size <= 0 or target.stat().st_size != size:
                    raise ValueError
            return path
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ApiError(
                "model_not_ready",
                f"{name} 모델이 준비되지 않았습니다. 터미널에서 meetinglog prepare-models를 실행하세요",
                503,
            ) from error

    def prepare(self, names: list[str]) -> None:
        from huggingface_hub import HfApi, snapshot_download

        self.root.mkdir(parents=True, exist_ok=True)
        manifest = self.read()
        for name in names:
            if name not in self.repositories:
                raise ApiError("unknown_model", "지원하지 않는 모델 이름입니다")
            repo = self.repositories[name]
            revision = HfApi().model_info(repo).sha
            path = self.root / name
            print(f"Preparing {name}: {repo} @ {revision}", flush=True)
            snapshot_download(
                repo,
                revision=revision,
                local_dir=path,
                allow_patterns=[
                    "*.json",
                    "*.safetensors",
                    "*.txt",
                    "*.model",
                    "*.tiktoken",
                    "*.npz",
                    "README.md",
                    "LICENSE*",
                ],
            )
            files = {
                str(item.relative_to(path)): item.stat().st_size
                for item in path.rglob("*")
                if item.is_file() and ".cache" not in item.parts and item.name != ".gitignore"
            }
            manifest["models"][name] = {
                "repo_id": repo,
                "revision": revision,
                "path": name,
                "files": files,
            }
            atomic_json(self.manifest, manifest)
            self.require(name)

    def readiness(self) -> list[dict]:
        result = []
        manifest = self.read()
        for name in ("asr", "aligner", "vad", "diarizer"):
            try:
                self.require(name)
                ready = True
            except ApiError:
                ready = False
            result.append(
                {
                    "name": name,
                    "repo_id": self.repositories[name],
                    "ready": ready,
                    "revision": manifest.get("models", {}).get(name, {}).get("revision"),
                    "quality": "unverified",
                }
            )
        return result
