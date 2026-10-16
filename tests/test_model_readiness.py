import json

import pytest
from meetinglog.db import ApiError


def test_missing_model_fails_without_downloading(settings, monkeypatch):
    from meetinglog.engines.models import ModelRegistry

    def forbidden(*args, **kwargs):
        raise AssertionError("processing must never download a model")

    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "snapshot_download", forbidden)
    with pytest.raises(ApiError) as error:
        ModelRegistry(settings).require("asr")
    assert error.value.code == "model_not_ready"
    assert not settings.models_dir.exists()


def test_manifest_detects_missing_or_corrupt_weights(settings):
    from meetinglog.engines.models import ModelRegistry

    directory = settings.models_dir / "asr"
    directory.mkdir(parents=True)
    (directory / "config.json").write_text("{}")
    (directory / "model.safetensors").write_bytes(b"weights")
    manifest = {
        "schema_version": 1,
        "models": {
            "asr": {
                "repo_id": settings.asr_repo,
                "revision": "test-revision",
                "path": "asr",
                "files": {"config.json": 2, "model.safetensors": 7},
            }
        },
    }
    (settings.models_dir / "manifest.json").write_text(json.dumps(manifest))
    assert ModelRegistry(settings).require("asr") == directory.resolve()
    (directory / "model.safetensors").write_bytes(b"")
    with pytest.raises(ApiError):
        ModelRegistry(settings).require("asr")
