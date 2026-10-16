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
