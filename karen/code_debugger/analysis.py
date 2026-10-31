import ast
import builtins
import symtable

SPECIAL_GLOBALS = {
    "__annotations__",
    "__builtins__",
    "__doc__",
    "__file__",
    "__name__",
    "__package__",
}


def _finding(filename, line, code, severity, title, explanation, source="builtin"):
    return {
        "filename": filename,
        "line": line,
        "column": 1,
        "code": code,
        "severity": severity,
        "title": title,
        "explanation": explanation,
        "source": source,
    }


def _scope_children(scope):
    yield scope
    for child in scope.get_children():
        yield from _scope_children(child)


def _undefined_names(filename, source, tree):
    findings = []
    try:
        root = symtable.symtable(source, filename, "exec")
    except (SyntaxError, ValueError):
        return findings

    module_symbols = {symbol.get_name(): symbol for symbol in root.get_symbols()}
    module_bindings = {
        name
        for name, symbol in module_symbols.items()
        if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()
    }
    builtin_names = set(dir(builtins)) | SPECIAL_GLOBALS
    load_lines = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            load_lines.setdefault(node.id, node.lineno)

    reported = set()
    for scope in _scope_children(root):
        for symbol in scope.get_symbols():
            name = symbol.get_name()
            if (
                not symbol.is_referenced()
                or not symbol.is_global()
                or symbol.is_assigned()
                or name in builtin_names
                or name in module_bindings
                or name in reported
            ):
                continue

            reported.add(name)
            findings.append(
                _finding(
                    filename,
                    load_lines.get(name, 1),
                    "PY-UNDEFINED",
                    "error",
                    f"Possibly undefined name: {name}",
                    f"'{name}' is read but is not defined, imported, or provided as a built-in.",
                )
            )
    return findings


def _quality_findings(filename, tree):
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            compared_to_boolean = any(
                isinstance(value, ast.Constant) and isinstance(value.value, bool)
                for value in node.comparators
            )
            if compared_to_boolean:
                findings.append(
                    _finding(
                        filename,
                        node.lineno,
                        "PY-BOOL-COMPARE",
                        "warning",
                        "Direct comparison with a boolean",
                        "Comparing a value to True or False is often unnecessary; check the condition's intended meaning.",
                    )
                )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec"}
        ):
            findings.append(
                _finding(
                    filename,
                    node.lineno,
                    "PY-DYNAMIC-EXEC",
                    "warning",
                    f"Dynamic {node.func.id} call",
                    "Dynamic code execution can run untrusted input. Prefer a safe parser or explicit operation mapping.",
                )
            )
    return findings


def analyze_python(filename, source):
    try:
        tree = ast.parse(source, filename=filename)
        compile(source, filename, "exec", dont_inherit=True)
    except SyntaxError as error:
        return [
            _finding(
                filename,
                error.lineno or 1,
                "PY-SYNTAX",
                "error",
                "Python syntax error",
                error.msg,
            )
        ]
    except (ValueError, OverflowError) as error:
        return [
            _finding(
                filename,
                1,
                "PY-COMPILE",
                "error",
                "Python compile check failed",
                str(error),
            )
        ]

    return _undefined_names(filename, source, tree) + _quality_findings(filename, tree)