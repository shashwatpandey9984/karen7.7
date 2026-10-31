import difflib


def unified_code_diff(filename, original, proposed):
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            proposed.splitlines(keepends=True),
            fromfile=f"original/{filename}",
            tofile=f"proposed/{filename}",
        )
    )