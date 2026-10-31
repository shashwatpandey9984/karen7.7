from flask import Flask

from code_debugger.analysis import analyze_python
from code_debugger.api import code_debugger_bp
from code_debugger.correction import generate_correction
from code_debugger.languages import detect_language
from code_debugger.testing import test_execution_status as get_test_execution_status


def make_client():
    app = Flask(__name__)
    app.register_blueprint(code_debugger_bp)
    return app.test_client()


def test_valid_python_has_no_builtin_findings():
    findings = analyze_python("sample.py", "def add(left, right):\n    return left + right\n")
    assert findings == []


def test_syntax_error_has_filename_and_line():
    findings = analyze_python("broken.py", "def add(value)\n    return value\n")
    assert findings[0]["code"] == "PY-SYNTAX"
    assert findings[0]["filename"] == "broken.py"
    assert findings[0]["line"] == 1


def test_undefined_name_is_reported():
    findings = analyze_python("names.py", "def read_value():\n    return missing_value\n")
    undefined = [finding for finding in findings if finding["code"] == "PY-UNDEFINED"]
    assert undefined
    assert undefined[0]["line"] == 2
    assert "missing_value" in undefined[0]["explanation"]


def test_boolean_comparison_quality_finding():
    findings = analyze_python("logic.py", "def is_ready(value):\n    return value == True\n")
    assert any(finding["code"] == "PY-BOOL-COMPARE" for finding in findings)


def test_language_detection_and_unsupported_language_response():
    assert detect_language("main.js", "const value = 1;") == "javascript"
    response = make_client().post(
        "/api/code/analyze",
        json={"filename": "main.js", "source": "const value = 1;"},
    )
    assert response.status_code == 200
    assert response.json["findings"][0]["code"] == "LANG-UNSUPPORTED"


def test_empty_and_oversized_source_are_rejected():
    client = make_client()
    assert client.post("/api/code/analyze", json={"source": " "}).status_code == 400
    response = client.post("/api/code/analyze", json={"source": "x" * 100_001})
    assert response.status_code == 413


def test_fix_is_proposed_only_for_parse_verified_missing_colon():
    source = "if ready\n    print('ready')\n"
    proposal = generate_correction("sample.py", source, attempts=2)
    assert proposal["available"] is True
    assert proposal["fixed_code"] == "if ready:\n    print('ready')\n"
    assert "@@" in proposal["diff"]
    assert generate_correction("sample.py", "value = unknown_name\n")["available"] is False


def test_malicious_source_is_analyzed_as_text_not_executed(tmp_path):
    marker = tmp_path / "must_not_exist.txt"
    payload = f"open({str(marker)!r}, 'w').write('executed')"
    source = f"exec({payload!r})\n"
    findings = analyze_python("malicious.py", source)
    assert isinstance(findings, list)
    assert any(finding["code"] == "PY-DYNAMIC-EXEC" for finding in findings)
    assert not marker.exists()


def test_test_execution_is_disabled_without_a_sandbox():
    status = get_test_execution_status()
    assert status["ran"] is False
    assert "sandbox" in status["message"]
    response = make_client().post(
        "/api/code/tests",
        json={"filename": "test.py", "source": "print('must not run')"},
    )
    assert response.status_code == 409
    assert response.json["ran"] is False


def test_failing_assertion_is_refused_not_executed():
    response = make_client().post(
        "/api/code/tests",
        json={"filename": "failing_test.py", "source": "assert 1 == 2"},
    )
    assert response.status_code == 409
    assert response.json["ran"] is False


def test_behavioral_suspicion_does_not_receive_a_guessed_fix():
    source = "def is_even(value):\n    return value % 2 == 1\n"
    proposal = generate_correction("logic.py", source)
    assert proposal["available"] is False
    assert proposal["fixed_code"] is None


def test_correction_response_does_not_modify_source_file(tmp_path):
    source_file = tmp_path / "user_code.py"
    original = "if ready\n    pass\n"
    source_file.write_text(original, encoding="utf-8")
    generate_correction(source_file.name, original)
    assert source_file.read_text(encoding="utf-8") == original