import ast
import re

from .ai_review import review_configuration
from .comparison import unified_code_diff

COLON_LINE = re.compile(
    r"^(?P<statement>\s*(?:if|elif|for|while|def|class|with|try|except|else|finally)\b[^#]*?)(?P<comment>\s+#.*)?$"
)


def _add_expected_colon(source, filename):
    try:
        ast.parse(source, filename=filename)
        return None
    except SyntaxError as error:
        if "expected ':'" not in error.msg or not error.lineno:
            return None
        error_line = error.lineno

    lines = source.splitlines(keepends=True)
    index = error_line - 1
    if index < 0 or index >= len(lines):
        return None

    line = lines[index]
    newline = "\n" if line.endswith("\n") else ""
    content = line[:-1] if newline else line
    match = COLON_LINE.match(content)
    if not match or match.group("statement").rstrip().endswith(":"):
        return None

    lines[index] = f"{match.group('statement').rstrip()}:{match.group('comment') or ''}{newline}"
    candidate = "".join(lines)
    try:
        ast.parse(candidate, filename=filename)
    except SyntaxError:
        return None
    return candidate


def generate_correction(filename, source, attempts=1):
    max_attempts = min(max(int(attempts), 1), 3)
    candidate = source
    changes = []
    for _ in range(max_attempts):
        revised = _add_expected_colon(candidate, filename)
        if revised is None:
            break
        candidate = revised
        changes.append("Added a missing Python block colon; the proposed code parses successfully.")
        try:
            ast.parse(candidate, filename=filename)
            break
        except SyntaxError:
            continue

    diff = unified_code_diff(filename, source, candidate)
    available = bool(changes) and candidate != source
    return {
        "available": available,
        "fixed_code": candidate if available else None,
        "diff": diff,
        "changes": changes,
        "attempts": max_attempts,
        "message": (
            "Review this syntax-only proposal. It has not been applied."
            if available
            else "No safe automatic correction is available for these findings."
        ),
        "ai_review": review_configuration(),
    }