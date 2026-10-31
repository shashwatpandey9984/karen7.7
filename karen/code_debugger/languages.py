from pathlib import Path

EXTENSIONS = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
}


def detect_language(filename, source, hint=None):
    if hint:
        normalized_hint = hint.strip().lower()
        if normalized_hint in set(EXTENSIONS.values()) | {"unknown"}:
            return normalized_hint

    extension = Path(filename or "").suffix.lower()
    if extension in EXTENSIONS:
        return EXTENSIONS[extension]

    sample = source.lstrip()
    if sample.startswith(("def ", "class ", "from ", "import ", "async def ")):
        return "python"
    if any(token in sample for token in ("const ", "let ", "function ", "=>")):
        return "javascript"
    return "unknown"