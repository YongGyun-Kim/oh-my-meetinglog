import time
from collections.abc import Callable

from meetinglog.db import ApiError


def retry[T](
    operation: Callable[[], T],
    sleep=time.sleep,
    cancelled: Callable[[], bool] = lambda: False,
    on_retry: Callable | None = None,
) -> T:
    for attempt in range(3):
        if cancelled():
            raise ApiError("job_cancelled", "작업이 취소되었습니다", 409)
        try:
            return operation()
        except ApiError as error:
            if not error.retryable or attempt == 2:
                raise
            if on_retry:
                on_retry(attempt + 1, error)
            delay = max(0.0, float(getattr(error, "retry_after", 2**attempt)))
            while delay > 0:
                if cancelled():
                    raise ApiError("job_cancelled", "작업이 취소되었습니다", 409) from None
                step = min(delay, 0.1)
                sleep(step)
                delay -= step
    raise RuntimeError("retry loop exhausted")
