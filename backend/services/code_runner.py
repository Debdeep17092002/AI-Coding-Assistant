import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Tuple

RUN_TIMEOUT = 10  # seconds
MAX_OUTPUT_BYTES = 20000
_slots = threading.BoundedSemaphore(2)  # at most 2 programs at once


class RunnerError(Exception):
    """The code could not be run (unsupported language, missing Node, ...)."""


class RunnerBusy(Exception):
    """Too many programs are already running."""


def _interpreter(language: str) -> Tuple[List[str], str]:
    if language == "python":
        # -I isolated mode, -X utf8 for consistent text encoding
        return [sys.executable, "-I", "-X", "utf8"], ".py"
    if language == "javascript":
        node = shutil.which("node")
        if not node:
            raise RunnerError("Node.js is not installed, so JavaScript cannot be run.")
        return [node], ".js"
    raise RunnerError(f"Unsupported language: {language}")


def _safe_env() -> Dict[str, str]:
    """Give the child process only what it needs, so it never sees your .env secrets."""
    keep = ["PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT"]
    return {k: os.environ[k] for k in keep if k in os.environ}


def _read_capped(path: Path) -> str:
    with open(path, "rb") as f:
        data = f.read(MAX_OUTPUT_BYTES + 1)
    text = data[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    if len(data) > MAX_OUTPUT_BYTES:
        text += "\n[output truncated]"
    return text


def run_code(code: str, language: str, timeout: int = RUN_TIMEOUT) -> Dict[str, object]:
    prefix, ext = _interpreter(language)

    if not _slots.acquire(blocking=False):
        raise RunnerBusy("Too many programs are running right now. Try again in a moment.")
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            src = Path(tmp) / f"main{ext}"
            src.write_text(code, encoding="utf-8")
            out_path = Path(tmp) / "stdout.txt"
            err_path = Path(tmp) / "stderr.txt"

            timed_out = False
            exit_code = 0
            start = time.monotonic()
            with open(out_path, "wb") as out, open(err_path, "wb") as err:
                try:
                    proc = subprocess.run(
                        prefix + [str(src)],
                        cwd=tmp,
                        env=_safe_env(),
                        stdin=subprocess.DEVNULL,  # input() fails fast instead of hanging
                        stdout=out,
                        stderr=err,
                        timeout=timeout,
                    )
                    exit_code = proc.returncode
                except subprocess.TimeoutExpired:
                    timed_out = True
                    exit_code = -1
            duration_ms = int((time.monotonic() - start) * 1000)

            stdout = _read_capped(out_path)
            stderr = _read_capped(err_path).replace(str(src), f"main{ext}")

        if timed_out:
            stderr = (stderr + f"\nTimed out after {timeout} seconds.").strip()

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "duration_ms": duration_ms,
        }
    finally:
        _slots.release()