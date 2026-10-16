import argparse

from meetinglog.app import create_app
from meetinglog.config import Settings


def main():
    parser = argparse.ArgumentParser(prog="meetinglog")
    parser.add_argument("command", choices=["serve", "schema", "worker"])
    args = parser.parse_args()
    if args.command == "schema":
        import json

        print(json.dumps(create_app().openapi(), ensure_ascii=False))
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
