from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.models import User
from routes.auth import get_current_user
from services import prompt_manager as pm
from services.ai_service import AIServiceError, ask_ai
from services.code_analyzer import analyze_code, format_issues
from services.code_runner import RUN_TIMEOUT, RunnerBusy, RunnerError, run_code

router = APIRouter(prefix="/code", tags=["code"])

SUPPORTED = {"python", "javascript"}
ALIASES = {"py": "python", "python3": "python", "js": "javascript", "node": "javascript"}


# ---------- schemas ----------
class CodeInput(BaseModel):
    code: str
    language: str = "python"


class Issue(BaseModel):
    line: Optional[int] = None
    column: Optional[int] = None
    severity: str
    message: str


class AnalysisOut(BaseModel):
    language: str
    ok: bool
    issues: List[Issue]
    checked_with: List[str]


class RunOut(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    duration_ms: int


class RunDebugOut(BaseModel):
    analysis: AnalysisOut
    run: RunOut
    ai_suggestion: Optional[str] = None
    ai_error: Optional[str] = None


# ---------- helpers ----------
def prepare(data: CodeInput) -> str:
    language = ALIASES.get(data.language.lower().strip(), data.language.lower().strip())
    if language not in SUPPORTED:
        raise HTTPException(400, f"Unsupported language. Use one of: {', '.join(sorted(SUPPORTED))}")
    if not data.code.strip():
        raise HTTPException(400, "Code is empty")
    if len(data.code) > pm.MAX_CODE_CHARS:
        raise HTTPException(413, f"Code too large (max {pm.MAX_CODE_CHARS} characters)")
    return language


def do_run(code: str, language: str) -> dict:
    try:
        return run_code(code, language)
    except RunnerBusy as e:
        raise HTTPException(429, str(e))
    except RunnerError as e:
        raise HTTPException(400, str(e))


# ---------- endpoints ----------
@router.post("/analyze", response_model=AnalysisOut)
def analyze(data: CodeInput, user: User = Depends(get_current_user)):
    language = prepare(data)
    return analyze_code(data.code, language)


@router.post("/run", response_model=RunOut)
def run(data: CodeInput, user: User = Depends(get_current_user)):
    language = prepare(data)
    return do_run(data.code, language)


@router.post("/run-and-debug", response_model=RunDebugOut)
def run_and_debug(data: CodeInput, user: User = Depends(get_current_user)):
    language = prepare(data)
    analysis = analyze_code(data.code, language)
    result = do_run(data.code, language)

    failed = (not analysis["ok"]) or result["exit_code"] != 0 or result["timed_out"]
    response = {"analysis": analysis, "run": result, "ai_suggestion": None, "ai_error": None}
    if not failed:
        return response

    # Collect real evidence for the AI
    parts = []
    if analysis["issues"]:
        parts.append("Static analysis:\n" + format_issues(analysis["issues"]))
    if result["timed_out"]:
        parts.append(f"The program timed out after {RUN_TIMEOUT} seconds (possible infinite loop).")
    if result["stderr"]:
        parts.append("Runtime error output:\n" + result["stderr"])
    error_text = "\n\n".join(parts)

    try:
        system = pm.load_system_prompt("debug_code")
        message = pm.build_code_message(data.code, language, error_text)
        response["ai_suggestion"] = ask_ai(system, [{"role": "user", "content": message}])
    except (AIServiceError, FileNotFoundError) as e:
        # the run result is still useful even if the AI is unavailable
        response["ai_error"] = str(e)
    return response