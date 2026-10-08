from pathlib import Path
from typing import Optional

# backend/services/prompt_manager.py -> project root is two levels up
PROMPTS_DIR = Path(__file__).resolve().parents[2] / "ai" / "prompts"

MAX_CODE_CHARS = 20000


def load_system_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _fence(code: str, language: str) -> str:
    return f"```{language}\n{code}\n```"


def build_code_message(code: str, language: str, error: Optional[str] = None) -> str:
    parts = [f"Language: {language}", "Code:", _fence(code, language)]
    if error and error.strip():
        parts += ["Error message:", f"```\n{error.strip()}\n```"]
    return "\n".join(parts)


def build_generate_message(request: str, language: str) -> str:
    return f"Language: {language}\nRequest: {request.strip()}"


def build_chat_message(message: str, code: Optional[str] = None, language: str = "python") -> str:
    if code and code.strip():
        return f"{message.strip()}\n\nMy current code ({language}):\n{_fence(code, language)}"
    return message.strip()