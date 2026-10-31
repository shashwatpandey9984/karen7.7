from flask import Blueprint, jsonify, request

from . import MAX_SOURCE_CHARS
from .ai_review import review_configuration
from .analysis import analyze_python
from .correction import generate_correction
from .languages import detect_language
from .security import security_report
from .testing import test_execution_status
from .tooling import run_static_tools

code_debugger_bp = Blueprint("code_debugger", __name__)


def _read_source():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, None, None, (jsonify({"error": "Expected a JSON object."}), 400)

    source = payload.get("source")
    if not isinstance(source, str) or not source.strip():
        return None, None, None, (jsonify({"error": "Source code cannot be empty."}), 400)
    if len(source) > MAX_SOURCE_CHARS:
        return None, None, None, (
            jsonify({"error": f"Source is too large; maximum is {MAX_SOURCE_CHARS} characters."}),
            413,
        )

    filename = str(payload.get("filename") or "submitted.py")[:128]
    hint = payload.get("language")
    language = detect_language(filename, source, hint if isinstance(hint, str) else None)
    return source, filename, language, None


def _analyze(source, filename, language, include_tools=True):
    if language != "python":
        return {
            "language": language,
            "findings": [
                {
                    "filename": filename,
                    "line": 1,
                    "column": 1,
                    "code": "LANG-UNSUPPORTED",
                    "severity": "info",
                    "title": f"{language.title()} identified; analyzer unavailable",
                    "explanation": (
                        "This version detects this language but only provides Python static analysis. "
                        "The source was not executed."
                    ),
                    "source": "language-detector",
                }
            ],
            "tools": [],
            "security": security_report([], []),
            "ai_review": review_configuration(),
            "limitations": [
                "Intended behavior and logical correctness require a specification or trusted tests; submitted code is never executed."
            ],
        }

    findings = analyze_python(filename, source)
    statuses = []
    syntax_invalid = any(item["code"] in {"PY-SYNTAX", "PY-COMPILE"} for item in findings)
    if include_tools and not syntax_invalid:
        tool_findings, statuses = run_static_tools(filename, source)
        findings.extend(tool_findings)
    elif include_tools:
        statuses = [{"tool": name, "status": "skipped_invalid_syntax"} for name in ("ruff", "pylint", "mypy", "bandit")]

    findings.sort(key=lambda item: (item["line"], item["column"], item["severity"], item["code"]))
    return {
        "language": language,
        "findings": findings,
        "tools": statuses,
        "security": security_report(findings, statuses),
        "ai_review": review_configuration(),
        "limitations": [
            "Intended behavior and logical correctness require a specification or trusted tests; submitted code is never executed."
        ],
    }


@code_debugger_bp.post("/api/code/analyze")
def analyze_code():
    source, filename, language, error = _read_source()
    if error:
        return error
    result = _analyze(source, filename, language)
    result["summary"] = f"Analysis complete: {len(result['findings'])} finding(s)."
    return jsonify(result)


@code_debugger_bp.post("/api/code/fix")
def propose_fix():
    source, filename, language, error = _read_source()
    if error:
        return error
    if language != "python":
        return jsonify({"error": "Automatic proposals are currently limited to Python syntax."}), 422

    payload = request.get_json(silent=True) or {}
    try:
        attempts = int(payload.get("attempts", 1))
    except (TypeError, ValueError):
        attempts = 1
    return jsonify(generate_correction(filename, source, attempts))


@code_debugger_bp.post("/api/code/tests")
def run_code_tests():
    _, filename, language, error = _read_source()
    if error:
        return error
    status = test_execution_status()
    status.update({"filename": filename, "language": language})
    return jsonify(status), 409