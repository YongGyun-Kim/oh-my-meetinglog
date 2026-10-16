import sys
import time

import pytest
from meetinglog.db import ApiError
from meetinglog.domain import StageRequest


def test_timeout_terminates_sleeping_inference_process(tmp_path):
    from meetinglog.jobs.process import ProcessRunner

    request = StageRequest(
        job_id="j",
        recording_id="r",
        generation=0,
        stage="speech",
        input_path="in",
        output_path=str(tmp_path / "out.json"),
        mode="local_only",
    )
    runner = ProcessRunner(lambda request: [sys.executable, "-c", "import time;time.sleep(30)"])
    started = time.monotonic()
    with pytest.raises(ApiError) as error:
        runner.run(request, timeout_s=0.1)
    assert error.value.code == "stage_timeout"
    assert time.monotonic() - started < 2


def test_cancel_signal_terminates_sleeping_inference_process(tmp_path):
    from meetinglog.jobs.process import ProcessRunner

    started = time.monotonic()
    request = StageRequest(
        job_id="j",
        recording_id="r",
        generation=0,
        stage="speech",
        input_path="in",
        output_path=str(tmp_path / "out.json"),
        mode="local_only",
    )
    runner = ProcessRunner(
        lambda request: [sys.executable, "-c", "import time;time.sleep(30)"],
        cancelled=lambda: time.monotonic() - started > 0.1,
    )
    with pytest.raises(ApiError) as error:
        runner.run(request, timeout_s=30)
    assert error.value.code == "job_cancelled"
    assert time.monotonic() - started < 2


def test_abrupt_worker_exit_cleans_owned_child_before_recovery(settings, db, tmp_path):
    import os
    import signal
    import subprocess

    from meetinglog.jobs.runner import Worker

    marker = tmp_path / "child.pid"
    code = """
import sys
from pathlib import Path
from meetinglog.jobs.process import ProcessRunner
from meetinglog.domain import StageRequest
child = "import os,sys,signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(30)"
request = StageRequest(job_id='j',recording_id='r',generation=0,stage='speech',input_path='in',output_path=sys.argv[2],mode='local_only')
ProcessRunner(lambda _: [sys.executable,'-c',child,sys.argv[1]],env={'MEETINGLOG_DATA_DIR':sys.argv[3]}).run(request,60)
"""
    parent = subprocess.Popen(
        [
            sys.executable,
            "-c",
            code,
            str(marker),
            str(tmp_path / "out.json"),
            str(settings.data_dir),
        ]
    )
    child_pid = None
    try:
        deadline = time.monotonic() + 4
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists()
        child_pid = int(marker.read_text())
        parent.kill()
        parent.wait(timeout=2)
        with Worker(settings, db):
            deadline = time.monotonic() + 1.5
            while time.monotonic() < deadline:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.02)
            else:
                raise AssertionError("orphan inference child survived recovery")
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait()
        if child_pid:
            try:
                os.killpg(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
