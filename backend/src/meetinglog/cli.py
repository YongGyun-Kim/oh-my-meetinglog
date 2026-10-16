import argparse

from meetinglog.app import create_app
from meetinglog.config import Settings


def main():
    parser = argparse.ArgumentParser(prog="meetinglog")
    parser.add_argument(
        "command", choices=["serve", "schema", "worker", "prepare-models", "doctor"]
    )
    parser.add_argument("--models", nargs="+", default=["vad", "asr", "aligner", "diarizer"])
    args = parser.parse_args()
    if args.command == "schema":
        import json

        print(json.dumps(create_app().openapi(), ensure_ascii=False))
    elif args.command == "prepare-models":
        from meetinglog.engines.models import ModelRegistry

        ModelRegistry(Settings()).prepare(args.models)
    elif args.command == "doctor":
        import json
        import shutil

        from meetinglog.engines.models import ModelRegistry

        print(
            json.dumps(
                {
                    "ffmpeg": bool(shutil.which("ffmpeg")),
                    "ffprobe": bool(shutil.which("ffprobe")),
                    "models": ModelRegistry(Settings()).readiness(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "worker":
        import signal

        from meetinglog.db import Database
        from meetinglog.jobs.runner import Worker

        settings = Settings()
        db = Database(settings.database_path)
        db.migrate()
        with Worker(settings, db) as worker:
            signal.signal(signal.SIGTERM, lambda *_: worker.stop.set())
            signal.signal(signal.SIGINT, lambda *_: worker.stop.set())
            worker.run()
    else:
        import uvicorn

        uvicorn.run(create_app(Settings()), host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
