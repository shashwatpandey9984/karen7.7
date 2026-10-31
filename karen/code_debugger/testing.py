def test_execution_status():
    return {
        "ran": False,
        "safe": False,
        "message": (
            "Submitted code was not executed. This app has no OS-level sandbox for restricting "
            "filesystem, network, CPU, and memory access. Static analysis is available instead."
        ),
    }