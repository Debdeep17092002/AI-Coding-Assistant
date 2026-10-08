import ast
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

try:
    from pyflakes.api import check as _pyflakes_check

    HAVE_PYFLAKES = True
except ImportError:
    HAVE_PYFLAKES = False

Issue = Dict[str, object]


class _Collector:
    """Receives findings from pyflakes."""

    def __init__(self):
        self.issues: List[Issue] = []

    def unexpectedError(self, filename, msg):
        self.issues.append(
            {"line": None, "column": None, "severity": "warning", "message": str(msg)}
        )

    def syntaxError(self, filename, msg, lineno, offset, text):
        self.issues.append(
            {"line": lineno, "column": offset, "severity": "error", "message": str(msg)}
        )

    def flake(self, message):
        text = message.message % message.message_args
        severity = "error" if "undefined name" in text else "warning"
        self.issues.append(
            {
                "line": message.lineno,
                "column": getattr(message, "col", None),
                "severity": severity,
                "message": text,
            }
        )


def _analyze_python(code: str) -> Dict[str, object]:
    checked = ["ast"]
    try:
        ast.parse(code)
    except SyntaxError as e:
        issue = {
            "line": e.lineno,
            "column": e.offset,
            "severity": "error",
            "message": f"SyntaxError: {e.msg}",
        }
        return {"issues": [issue], "checked_with": checked}

    issues: List[Issue] = []
    if HAVE_PYFLAKES:
        collector = _Collector()
        _pyflakes_check(code, "main.py", collector)
        issues = collector.issues
        checked.append("pyflakes")
    return {"issues": issues, "checked_with": checked}


def _analyze_javascript(code: str) -> Dict[str, object]:
    node = shutil.which("node")
    if not node:
        issue = {
            "line": None,
            "column": None,
            "severity": "warning",
            "message": "Node.js is not installed, so JavaScript could not be checked.",
        }
        return {"issues": [issue], "checked_with": []}

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        src = Path(tmp) / "main.js"
        src.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [node, "--check", str(src)],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            return {"issues": [], "checked_with": []}

    if proc.returncode == 0:
        return {"issues": [], "checked_with": ["node --check"]}

    lines = proc.stderr.strip().splitlines()
    line_no = None
    if lines:
        m = re.search(r":(\d+)$", lines[0].strip())
        if m:
            line_no = int(m.group(1))
    message = next((l for l in lines if "Error" in l), proc.stderr.strip()[:300])
    issue = {"line": line_no, "column": None, "severity": "error", "message": message}
    return {"issues": [issue], "checked_with": ["node --check"]}


def analyze_code(code: str, language: str) -> Dict[str, object]:
    if language == "python":
        result = _analyze_python(code)
    elif language == "javascript":
        result = _analyze_javascript(code)
    else:
        raise ValueError(f"Unsupported language: {language}")

    result["language"] = language
    result["ok"] = not any(i["severity"] == "error" for i in result["issues"])
    return result


def format_issues(issues: List[Issue]) -> str:
    """Turn issues into plain text that can be given to the AI."""
    lines = []
    for i in issues:
        where = f"line {i['line']}" if i.get("line") else "unknown line"
        lines.append(f"- [{i['severity']}] {where}: {i['message']}")
    return "\n".join(lines)