import json
import os
from typing import Dict, Generator, List

import httpx
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("AI_PROVIDER", "ollama").lower()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
MAX_TOKENS = 1500
TIMEOUT = 180  # local models can be slow

Message = Dict[str, str]


class AIServiceError(Exception):
    """Raised for any problem talking to the AI provider."""


def _anthropic_client():
    from anthropic import Anthropic

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key or key == "your-key-here":
        raise AIServiceError("ANTHROPIC_API_KEY is not set in .env")
    return Anthropic(api_key=key)


def _ollama_payload(system_prompt: str, messages: List[Message], stream: bool) -> dict:
    return {
        "model": OLLAMA_MODEL,
        "stream": stream,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "options": {"num_predict": MAX_TOKENS},
    }


def ask_ai(system_prompt: str, messages: List[Message]) -> str:
    """Send a conversation and return the full reply as text."""
    if PROVIDER == "anthropic":
        try:
            resp = _anthropic_client().messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=messages,
            )
            return "".join(b.text for b in resp.content if b.type == "text")
        except AIServiceError:
            raise
        except Exception as e:
            raise AIServiceError(f"Anthropic request failed: {e}")

    if PROVIDER == "ollama":
        try:
            r = httpx.post(
                f"{OLLAMA_URL}/api/chat",
                json=_ollama_payload(system_prompt, messages, stream=False),
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            return r.json()["message"]["content"]
        except httpx.ConnectError:
            raise AIServiceError("Cannot reach Ollama. Is it installed and running?")
        except Exception as e:
            raise AIServiceError(f"Ollama request failed: {e}")

    raise AIServiceError(f"Unknown AI_PROVIDER: {PROVIDER}")


def stream_ai(system_prompt: str, messages: List[Message]) -> Generator[str, None, None]:
    """Yield the reply in small chunks as the model produces them."""
    if PROVIDER == "anthropic":
        try:
            with _anthropic_client().messages.stream(
                model=ANTHROPIC_MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text
            return
        except AIServiceError:
            raise
        except Exception as e:
            raise AIServiceError(f"Anthropic request failed: {e}")

    if PROVIDER == "ollama":
        try:
            with httpx.stream(
                "POST",
                f"{OLLAMA_URL}/api/chat",
                json=_ollama_payload(system_prompt, messages, stream=True),
                timeout=TIMEOUT,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break
            return
        except httpx.ConnectError:
            raise AIServiceError("Cannot reach Ollama. Is it installed and running?")
        except Exception as e:
            raise AIServiceError(f"Ollama request failed: {e}")

    raise AIServiceError(f"Unknown AI_PROVIDER: {PROVIDER}")