"""Browser integration fixture. Fixed engines exist only in this test module."""

import sys
import tempfile
import threading
from pathlib import Path

from meetinglog.config import Settings
from meetinglog.db import Database
from meetinglog.domain import AnalysisVersion, StageRequest, Transcript, new_id
from meetinglog.recordings.storage import atomic_json

from tests.analysis_fixtures import analysis_fixture, as_speech, transcript_fixture


def stage(path: str):
    request = StageRequest.model_validate_json(Path(path).read_text())
    if request.stage == "speech":
        from meetinglog.recordings.media import normalize

        normalize(Path(request.input_path), Path(request.output_path).with_suffix(".wav"))
        transcript = transcript_fixture(request.recording_id)
        result = as_speech(transcript)
    else:
        transcript = Transcript.model_validate_json(Path(request.input_path).read_text())
        result = AnalysisVersion(
            id=new_id(),
            transcript_id=transcript.id,
            body=analysis_fixture(),
            provider="test",
            model="fixed-browser-fixture",
            prompt_version="test-v1",
            form=request.form,
        )
    atomic_json(Path(request.output_path), result.model_dump(mode="json"))


def main():
    import uvicorn
    from meetinglog.app import create_app
    from meetinglog.jobs.runner import Worker

    class BrowserSettings(Settings):
        @property
        def allowed_origins(self):
            return ["http://127.0.0.1:5174", "http://127.0.0.1:8766"]

    with tempfile.TemporaryDirectory(prefix="meetinglog-browser-") as directory:
        settings = BrowserSettings(
            data_dir=Path(directory),
            models_dir=Path(directory) / "models",
            ollama_url="http://127.0.0.1:1",
            openai_api_key=None,
        )
        db = Database(settings.database_path)
        db.migrate()

        def command(request):
            path = Path(request.output_path).with_suffix(".request.json")
            atomic_json(path, request.model_dump())
            return [sys.executable, "-m", "tests.e2e_server", "--stage", str(path)]

        with Worker(settings, db, stage_command=command) as worker:
            thread = threading.Thread(target=worker.run, daemon=True)
            thread.start()
            try:
                uvicorn.run(create_app(settings), host="127.0.0.1", port=8766)
            finally:
                worker.stop.set()
                thread.join(5)


if __name__ == "__main__":
    stage(sys.argv[2]) if len(sys.argv) > 1 and sys.argv[1] == "--stage" else main()
