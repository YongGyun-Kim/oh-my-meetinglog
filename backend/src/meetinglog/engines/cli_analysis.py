import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from pydantic import ValidationError

from meetinglog.analysis.prompts import merge_messages, messages
from meetinglog.db import ApiError
from meetinglog.domain import AnalysisSettings, FormAnalysisBody

CLI_TIMEOUT = 300


class CliAnalysis:
    def __init__(self, settings: AnalysisSettings, form="meeting", workspace: Path | None = None):
        self.settings, self.form = settings, form
        self.workspace = workspace
        self.provider, self.model = settings.provider, settings.model or "default"

    def _request(self, input_messages):
        executable = shutil.which(self.provider)
        if not executable:
            raise ApiError("cli_not_installed", "서버에 선택한 분석 도구를 설치해 주세요.", 409)
        with tempfile.TemporaryDirectory(
            prefix="meetinglog-analysis-", dir=self.workspace
        ) as directory:
            root = Path(directory)
            schema = FormAnalysisBody.model_json_schema()

            def strict(value):
                if isinstance(value, dict):
                    value.pop("default", None)
                    if "properties" in value:
                        value["required"] = list(value["properties"])
                    for child in value.values():
                        strict(child)
                elif isinstance(value, list):
                    for child in value:
                        strict(child)

            strict(schema)
            schema_path, output_path = root / "schema.json", root / "result.json"
            schema_path.write_text(json.dumps(schema))
            if self.provider == "codex":
                args = [
                    executable,
                    "exec",
                    "--ignore-user-config",
                    "--ignore-rules",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(output_path),
                    "--color",
                    "never",
                ]
                for override in (
                    'approval_policy="never"',
                    "features.shell_tool=false",
                    "features.multi_agent=false",
                    "features.apps=false",
                    "features.plugins=false",
                    "features.hooks=false",
                    'web_search="disabled"',
                    "project_doc_max_bytes=0",
                    "mcp_servers={}",
                    "tools.view_image=false",
                ):
                    args += ["-c", override]
                if self.settings.reasoning != "default":
                    args += ["-c", f'model_reasoning_effort="{self.settings.reasoning}"']
                args += ["-"]
                prompt = "\n\n".join(item["content"] for item in input_messages)
            else:
                args = [
                    executable,
                    "--print",
                    "--safe-mode",
                    "--tools",
                    "",
                    "--strict-mcp-config",
                    "--mcp-config",
                    '{"mcpServers":{}}',
                    "--disable-slash-commands",
                    "--no-session-persistence",
                    "--output-format",
                    "json",
                    "--json-schema",
                    json.dumps(schema),
                    "--system-prompt",
                    input_messages[0]["content"],
                ]
                if self.settings.reasoning != "default":
                    args += ["--effort", self.settings.reasoning]
                prompt = input_messages[1]["content"]
            if self.settings.model:
                args += ["--model", self.settings.model]
            try:
                # Inherit the stage process group so worker cancellation also reaps this CLI.
                with subprocess.Popen(
                    args,
                    cwd=root,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                ) as process:
                    try:
                        stdout, _ = process.communicate(prompt, timeout=CLI_TIMEOUT)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        raise ApiError(
                            "cli_timeout",
                            "분석 도구의 응답 시간을 초과했어요. 다시 시도해 주세요.",
                            503,
                        ) from None
                    if process.returncode:
                        raise ApiError(
                            "cli_analysis_failed",
                            "분석 도구를 실행하지 못했어요. 로그인·모델·추론 설정과 사용 한도를 확인해 주세요.",
                            503,
                        )
                if self.provider == "codex":
                    return FormAnalysisBody.model_validate_json(output_path.read_text())
                data = json.loads(stdout)
                if data.get("is_error"):
                    raise ValueError("CLI returned an error")
                result = FormAnalysisBody.model_validate(data["structured_output"])
                models = data.get("modelUsage", {})
                if len(models) == 1:
                    self.model = next(iter(models))
                return result
            except (OSError, UnicodeError, ValueError, KeyError, TypeError, ValidationError):
                raise ApiError(
                    "invalid_cli_output",
                    "분석 결과를 읽지 못했어요. 분석 도구의 버전과 설정을 확인해 주세요.",
                    503,
                ) from None

    def generate(self, transcript, feedback=None):
        return self._request(messages(transcript, feedback, self.form))

    def merge(self, bodies, feedback=None):
        return self._request(merge_messages(bodies, self.form, feedback))
