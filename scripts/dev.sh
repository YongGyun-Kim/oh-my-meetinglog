#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --no-sync python - <<'PY'
import os
import signal
import subprocess
import time

processes = []
stopping = False
def stop(*_):
    global stopping
    stopping = True
signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
try:
    for command in (["uv", "run", "--no-sync", "meetinglog", "serve"], ["uv", "run", "--no-sync", "meetinglog", "worker"], ["npm", "--prefix", "web", "run", "dev"]):
        processes.append(subprocess.Popen(command, start_new_session=True))
    print("대화록: http://127.0.0.1:5173 — Ctrl+C로 종료", flush=True)
    while not stopping and all(process.poll() is None for process in processes):
        time.sleep(.2)
finally:
    for process in processes:
        if process.poll() is None:
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
    for process in processes:
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait()
if not stopping and any(process.returncode for process in processes):
    raise SystemExit(1)
PY
