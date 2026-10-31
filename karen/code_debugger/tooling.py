import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib.util import find_spec
from pathlib import Path

TOOL_TIMEOUT_SECONDS = 15
MAX_TOOL_OUTPUT_CHARS = 20_000
_TOOL_BATCH_LOCK = threading.BoundedSemaphore(1)


def _safe_filename(filename):
    name = Path(filename or "submitted.py").name
    if not name.endswith(".py"):
        name = "submitted.py"
    return name


def _run(command, cwd):
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
        return result.stdout[:MAX_TOOL_OUTPUT_CHARS], result.stderr[:MAX_TOOL_OUTPUT_CHARS], None
    except subprocess.TimeoutExpired:
        return "", "", "Timed out; no result returned."
    except OSError as error:
        return "", "", f"Could not start analyzer: {error}"


def _tool_finding(filename, line, column, code, message, severity, tool):
    return {
        "filename": filename,
        "line": max(1, int(line or 1)),
        "column": max(1, int(column or 1)),
        "code": str(code or tool.upper()),
        "severity": severity,
        "title": f"{tool}: {message}",
        "explanation": message,
        "source": tool,
    }


def _parse_ruff(output, filename):
    findings = []
    try:
        messages = json.loads(output or "[]")
    except json.JSONDecodeError:
        return findings
    for message in messages:
        location = message.get("location") or {}
        code = message.get("code", "")
        findings.append(
            _tool_finding(
                filename,
                location.get("row"),
                location.get("column"),
                code,
                message.get("message", "Static analysis finding"),
                "error" if code.startswith("F") else "warning",
                "ruff",
            )
        )
    return findings


def _parse_pylint(output, filename):
    findings = []
    try:
        messages = json.loads(output or "[]")
    except json.JSONDecodeError:
        return findings
    for message in messages:
        severity = "error" if message.get("type") == "error" else "warning"
        findings.append(
            _tool_finding(
                filename,
                message.get("line"),
                message.get("column"),
                message.get("message-id"),
                message.get("message", "Static analysis finding"),
                severity,
                "pylint",
            )
        )
    return findings


def _parse_bandit(output, filename):
    findings = []
    try:
        messages = json.loads(output or "{}").get("results", [])
    except json.JSONDecodeError:
        return findings
    for message in messages:
        severity = "error" if message.get("issue_severity") == "HIGH" else "warning"
        findings.append(
            _tool_finding(
                filename,
                message.get("line_number"),
                1,
                message.get("test_id"),
                message.get("issue_text", "Security finding"),
                severity,
                "bandit",
            )
        )
    return findings


def _parse_mypy(output, filename):
    findings = []
    pattern = re.compile(r"^.*?:(\d+)(?::(\d+))?: (error|note): (.*)$")
    for line in output.splitlines():
        match = pattern.match(line)
        if match and match.group(3) == "error":
            findings.append(
                _tool_finding(
                    filename,
                    match.group(1),
                    match.group(2),
                    "MYPY",
                    match.group(4),
                    "error",
                    "mypy",
                )
            )
    return findings


def run_static_tools(filename, source):
    safe_name = _safe_filename(filename)
    tool_specs = (
        ("ruff", ["check", "--output-format", "json"]),
        (
            "pylint",
            [
                "--output-format=json",
                "--reports=n",
                "--score=n",
                "--persistent=n",
                "--disable=all",
                "--enable=E,F,W",
            ],
        ),
        (
            "mypy",
            [
                "--no-site-packages",
                "--follow-imports=skip",
                "--ignore-missing-imports",
                "--no-error-summary",
            ],
        ),
        ("bandit", ["-f", "json", "-q"]),
    )
    parsers = {
        "ruff": _parse_ruff,
        "pylint": _parse_pylint,
        "mypy": _parse_mypy,
        "bandit": _parse_bandit,
    }
    if not _TOOL_BATCH_LOCK.acquire(blocking=False):
        return [], [{"tool": name, "status": "busy"} for name, _ in tool_specs]

    try:
        return _run_tool_batch(filename, source, safe_name, tool_specs, parsers)
    finally:
        _TOOL_BATCH_LOCK.release()


def _run_tool_batch(filename, source, safe_name, tool_specs, parsers):
    findings = []
    statuses = []
    with tempfile.TemporaryDirectory(prefix="karen-static-") as temporary_directory:
        source_path = Path(temporary_directory) / safe_name
        source_path.write_text(source, encoding="utf-8")
        config_path = Path(temporary_directory) / "mypy.ini"
        config_path.write_text("[mypy]\n", encoding="utf-8")

        def execute_tool(tool, arguments):
            if find_spec(tool) is None:
                return tool, "", "", "not_installed"
            command = [sys.executable, "-m", tool, *arguments]
            if tool == "mypy":
                command.extend(["--config-file", str(config_path)])
            command.append(str(source_path))
            stdout, stderr, error = _run(command, temporary_directory)
            return tool, stdout, stderr, error

        with ThreadPoolExecutor(max_workers=len(tool_specs)) as executor:
            jobs = [executor.submit(execute_tool, tool, arguments) for tool, arguments in tool_specs]
            for job in as_completed(jobs):
                tool, stdout, stderr, error = job.result()
                if error == "not_installed":
                    statuses.append({"tool": tool, "status": "not_installed"})
                elif error:
                    statuses.append({"tool": tool, "status": "unavailable", "message": error})
                else:
                    findings.extend(parsers[tool](stdout or stderr, safe_name))
                    statuses.append({"tool": tool, "status": "completed"})

    return findings, statuses