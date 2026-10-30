"""Read CLI metadata through the same control channels used by the official clients."""

import json
import os
import select
import shutil
import signal
import subprocess
import tempfile
import time

from pydantic import Field

from meetinglog.cli_auth import CliAuth, CliProvider
from meetinglog.db import ApiError
from meetinglog.domain import Contract
from meetinglog.jobs.process import terminate

CATALOG_TIMEOUT = 10
MAX_OUTPUT_BYTES = 2_000_000


class ModelOption(Contract):
    id: str
    name: str
    reasoning: list[str]
    default_reasoning: str | None = None
    aliases: list[str] = Field(default_factory=list)


def cli_models(provider: CliProvider) -> tuple[list[ModelOption], str]:
    status = CliAuth().status(provider)
    if status.state != "connected":
        raise ApiError(
            "cli_catalog_unavailable",
            "모델 목록을 조회하려면 도구를 설치하고 로그인한 뒤 새로 고침해 주세요.",
            409,
        )
    executable = shutil.which(provider)
    if provider == "codex":
        args = [executable, "app-server", "--stdio"]
        for override in (
            'model_provider="openai"',
            "features.plugins=false",
            "features.hooks=false",
            "features.apps=false",
            "mcp_servers={}",
        ):
            args += ["-c", override]
    else:
        args = [
            executable,
            "--print",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--safe-mode",
            "--tools",
            "",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--no-session-persistence",
        ]
    with tempfile.TemporaryDirectory(prefix="meetinglog-catalog-") as directory:
        process = None
        try:
            process = subprocess.Popen(
                args,
                cwd=directory,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            deadline, buffer, received = time.monotonic() + CATALOG_TIMEOUT, b"", 0

            def send(message):
                process.stdin.write((json.dumps(message) + "\n").encode())
                process.stdin.flush()

            def receive(identifier):
                nonlocal buffer, received
                while time.monotonic() < deadline:
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        data = json.loads(line)
                        if provider == "codex" and data.get("id") == identifier:
                            if "error" in data:
                                raise ValueError("Control request failed")
                            return data["result"]
                        if provider == "claude" and data.get("type") == "control_response":
                            response = data["response"]
                            if response.get("request_id") == identifier:
                                if response.get("subtype") != "success":
                                    raise ValueError("Control request failed")
                                return response["response"]
                    if not select.select([process.stdout], [], [], 0.1)[0]:
                        continue
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        raise ValueError("Control stream closed")
                    received += len(chunk)
                    if received > MAX_OUTPUT_BYTES:
                        raise ValueError("Control output exceeds limit")
                    buffer += chunk
                raise TimeoutError

            if provider == "codex":
                send(
                    {
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "clientInfo": {"name": "meetinglog_catalog", "version": "0.1.0"}
                        },
                    }
                )
                receive(1)
                send({"method": "initialized"})
                rows, cursor, cursors = [], None, set()
                for identifier in range(2, 102):
                    params = {"includeHidden": False, "limit": 100}
                    if cursor:
                        params["cursor"] = cursor
                    send({"id": identifier, "method": "model/list", "params": params})
                    result = receive(identifier)
                    rows.extend(result["data"])
                    cursor = result.get("nextCursor")
                    if not cursor:
                        break
                    if not isinstance(cursor, str) or cursor in cursors:
                        raise ValueError("Invalid cursor")
                    cursors.add(cursor)
                else:
                    raise ValueError("Too many pages")
                catalog = [
                    ModelOption(
                        id=row["model"],
                        name=row["displayName"],
                        reasoning=[
                            item["reasoningEffort"]
                            for item in row.get("supportedReasoningEfforts", [])
                        ],
                        default_reasoning=row.get("defaultReasoningEffort"),
                    )
                    for row in rows
                    if not row.get("hidden")
                ]
                default = next(
                    (
                        row["model"]
                        for row in rows
                        if row.get("isDefault") and not row.get("hidden")
                    ),
                    "",
                )
            else:
                send(
                    {
                        "type": "control_request",
                        "request_id": "catalog",
                        "request": {"subtype": "initialize", "hooks": {}, "sdkMcpServers": []},
                    }
                )
                # Official SDK Query.supportedModels() returns this initialization field.
                rows = receive("catalog")["models"]
                catalog = [
                    ModelOption(
                        id=row["value"],
                        name=row["displayName"],
                        aliases=[row["resolvedModel"]] if row.get("resolvedModel") else [],
                        reasoning=[]
                        if row.get("supportsEffort") is False
                        else row.get("supportedEffortLevels", []),
                    )
                    for row in rows
                ]
                default = "default" if any(row.id == "default" for row in catalog) else ""
            if not catalog:
                raise ValueError("Empty catalog")
            return catalog, default
        except (
            OSError,
            UnicodeError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            TimeoutError,
        ):
            raise ApiError(
                "cli_catalog_unavailable",
                "모델 목록을 가져오지 못했어요. 도구 버전과 연결 상태를 확인한 뒤 새로 고침해 주세요.",
                503,
            ) from None
        finally:
            if process:
                terminate(process)
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                for pipe in (process.stdin, process.stdout):
                    try:
                        pipe.close()
                    except OSError:
                        pass
