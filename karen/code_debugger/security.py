def security_report(findings, tool_statuses):
    return {
        "findings": [finding for finding in findings if finding["source"] == "bandit"],
        "tools": [status for status in tool_statuses if status["tool"] == "bandit"],
        "scope": "Static security checks only; no submitted code is executed.",
    }