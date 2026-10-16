import argparse

from meetinglog.app import create_app
from meetinglog.config import Settings


def main():
    parser = argparse.ArgumentParser(prog="meetinglog")
    parser.add_argument("command", choices=["serve", "schema"])
    args = parser.parse_args()
    if args.command == "schema":
        import json

        print(json.dumps(create_app().openapi(), ensure_ascii=False))
    else:
        import uvicorn

        uvicorn.run(create_app(Settings()), host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
