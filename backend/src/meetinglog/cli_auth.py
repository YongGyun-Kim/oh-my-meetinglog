import json
import shutil
import subprocess
from threading import Lock, Thread
from typing import Literal

from meetinglog.db import ApiError
from meetinglog.domain import Contract
from meetinglog.jobs.process import terminate

CliProvider = Literal["codex", "claude"]
STATUS_TIMEOUT = 5
LOGIN_TIMEOUT = 300


class CliConnection(Contract):
    provider: CliProvider
    state: Literal["not_installed", "logged_out", "connected", "logging_in", "error"]
    auth_method: Literal["account", "api_key", "external"] | None = None
    message: str | None = None


class CliAuth:
    def __init__(self):
        self._lock = Lock()
        self._pending: dict[CliProvider, subprocess.Popen] = {}
        self._errors: dict[CliProvider, str] = {}
        self._closed = False

    def _probe(self, provider: CliProvider) -> CliConnection:
        executable = shutil.which(provider)
        if not executable:
            return CliConnection(provider=provider, state="not_installed")
        args = ["login", "status"] if provider == "codex" else ["auth", "status", "--json"]
        failed = CliConnection(
            provider=provider,
            state="error",
            message="로그인 상태를 확인하지 못했어요. 터미널에서 도구가 실행되는지 확인해 주세요.",
        )
        try:
            with subprocess.Popen(
                [executable, *args],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            ) as process:
                try:
                    stdout, stderr = process.communicate(timeout=STATUS_TIMEOUT)
                except subprocess.TimeoutExpired:
                    terminate(process)
                    return failed
                code = process.returncode
        except (OSError, UnicodeError):
            return failed
        # 인증 출력에는 키·계정 정보가 포함될 수 있어 정해진 상태만 반환한다.
        method = None
        if provider == "claude":
            try:
                data = json.loads(stdout)
                logged_in = data["loggedIn"]
                if not isinstance(logged_in, bool):
                    return failed
                value = data.get("authMethod")
            except (ValueError, KeyError, TypeError):
                return failed
            if logged_in and code == 0:
                if value in ("claude.ai", "oauth_token"):
                    method = "account"
                elif value in ("api_key", "api_key_helper"):
                    method = "api_key"
                elif value == "third_party":
                    method = "external"
            elif not (not logged_in and code == 1):
                return failed
        else:
            output = (stdout + stderr).lower()
            logged_in = code == 0
            if logged_in:
                method = "account" if "chatgpt" in output else None
                if "api key" in output:
                    method = "api_key"
            elif code != 1 or "not logged in" not in output:
                return failed
        return CliConnection(
            provider=provider,
            state="connected" if logged_in else "logged_out",
            auth_method=method,
        )

    def status(self, provider: CliProvider) -> CliConnection:
        with self._lock:
            if provider in self._pending:
                return CliConnection(provider=provider, state="logging_in")
            error = self._errors.get(provider)
        result = self._probe(provider)
        if error and result.state == "logged_out":
            return CliConnection(provider=provider, state="error", message=error)
        return result

    def connections(self) -> list[CliConnection]:
        return [self.status("codex"), self.status("claude")]

    def start(self, provider: CliProvider) -> CliConnection:
        with self._lock:
            if provider in self._pending:
                return CliConnection(provider=provider, state="logging_in")
        current = self._probe(provider)
        if current.state == "connected":
            return current
        if current.state != "logged_out":
            raise ApiError(
                "cli_unavailable",
                "도구 설치와 로그인 상태를 먼저 확인해 주세요.",
                status=409,
            )
        args = ["login"] if provider == "codex" else ["auth", "login", "--claudeai"]
        with self._lock:
            if self._closed:
                raise ApiError("server_stopping", "서버가 종료 중이에요.", status=503)
            if provider in self._pending:
                return CliConnection(provider=provider, state="logging_in")
            try:
                process = subprocess.Popen(
                    [shutil.which(provider) or provider, *args],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except OSError:
                raise ApiError(
                    "cli_login_failed",
                    "로그인을 시작하지 못했어요. 도구 설치를 확인해 주세요.",
                    status=409,
                ) from None
            self._errors.pop(provider, None)
            self._pending[provider] = process
            Thread(target=self._wait, args=(provider, process), daemon=True).start()
        return CliConnection(provider=provider, state="logging_in")

    def _wait(self, provider: CliProvider, process: subprocess.Popen):
        error = None
        try:
            if process.wait(timeout=LOGIN_TIMEOUT) != 0:
                error = "로그인을 완료하지 못했어요. 다시 로그인하거나 터미널에서 확인해 주세요."
        except subprocess.TimeoutExpired:
            terminate(process)
            error = "로그인 시간이 지났어요. 다시 시작해 주세요."
        finally:
            with self._lock:
                if self._pending.get(provider) is process:
                    self._pending.pop(provider)
                    if error:
                        self._errors[provider] = error

    def cancel(self, provider: CliProvider) -> CliConnection:
        with self._lock:
            process = self._pending.pop(provider, None)
            if process is not None:
                terminate(process)
            self._errors.pop(provider, None)
        return self.status(provider)

    def close(self):
        with self._lock:
            self._closed = True
            pending = list(self._pending.values())
            self._pending.clear()
        for process in pending:
            terminate(process)
