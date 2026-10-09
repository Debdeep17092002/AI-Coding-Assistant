import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Dict, List

import httpx
import numpy as np
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# backend/services/embedding_service.py -> project root is two levels up
EMBED_DIR = Path(__file__).resolve().parents[2] / "ai" / "embeddings"

CHUNK_LINES = 40
CHUNK_OVERLAP = 5
MAX_CHUNK_CHARS = 2000
MAX_FILE_CHARS = 50000
BATCH_SIZE = 16
TOP_K = 4
MIN_SCORE = 0.3  # ignore weak matches; tune this if results seem too strict or too loose
TIMEOUT = 120

_locks: Dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


class EmbeddingError(Exception):
    """Raised when embeddings cannot be created."""


def _lock_for(project_id: int) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(project_id, threading.Lock())


def _index_path(project_id: int) -> Path:
    return EMBED_DIR / f"project_{project_id}.json"


def _load(project_id: int) -> dict:
    path = _index_path(project_id)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # an index made with a different model is useless, so start over
            if data.get("model") == EMBED_MODEL:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"model": EMBED_MODEL, "files": {}, "chunks": []}


def _save(project_id: int, data: dict) -> None:
    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    path = _index_path(project_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)  # atomic swap, so a crash never leaves a half-written index


def _hash(filename: str, content: str) -> str:
    return hashlib.sha256(f"{filename}\0{content}".encode("utf-8")).hexdigest()


def chunk_text(filename: str, content: str) -> List[dict]:
    lines = content.splitlines()
    chunks = []
    step = CHUNK_LINES - CHUNK_OVERLAP
    for start in range(0, len(lines), step):
        window = lines[start : start + CHUNK_LINES]
        text = "\n".join(window).strip()
        if text:
            chunks.append(
                {
                    "filename": filename,
                    "start_line": start + 1,
                    "end_line": start + len(window),
                    "text": text[:MAX_CHUNK_CHARS],
                }
            )
        if start + CHUNK_LINES >= len(lines):
            break
    return chunks


def _embed(texts: List[str], prefix: str) -> List[List[float]]:
    vectors: List[List[float]] = []
    try:
        for i in range(0, len(texts), BATCH_SIZE):
            batch = [prefix + t for t in texts[i : i + BATCH_SIZE]]
            r = httpx.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": batch},
                timeout=TIMEOUT,
            )
            if r.status_code == 404:
                raise EmbeddingError(
                    f"Embedding model not found. Run: ollama pull {EMBED_MODEL} "
                    "(if it still fails, update Ollama to the latest version)."
                )
            r.raise_for_status()
            vectors.extend(r.json()["embeddings"])
    except httpx.ConnectError:
        raise EmbeddingError("Cannot reach Ollama. Is it installed and running?")
    except EmbeddingError:
        raise
    except Exception as e:
        raise EmbeddingError(f"Embedding request failed: {e}")
    return vectors


def sync_index(project_id: int, files: List[dict], force: bool = False) -> dict:
    """Bring the project's index up to date. Only changed files are re-embedded."""
    with _lock_for(project_id):
        data = _load(project_id)
        current_ids = {str(f["id"]) for f in files}

        # forget files that were deleted
        data["chunks"] = [c for c in data["chunks"] if str(c["file_id"]) in current_ids]
        data["files"] = {k: v for k, v in data["files"].items() if k in current_ids}

        changed = []
        for f in files:
            content = f["content"][:MAX_FILE_CHARS]
            h = _hash(f["filename"], content)
            meta = data["files"].get(str(f["id"]))
            if force or meta is None or meta["hash"] != h:
                changed.append((f, content, h))

        if changed:
            changed_ids = {str(f["id"]) for f, _, _ in changed}
            data["chunks"] = [c for c in data["chunks"] if str(c["file_id"]) not in changed_ids]

            new_chunks = []
            for f, content, _ in changed:
                for ch in chunk_text(f["filename"], content):
                    ch["file_id"] = f["id"]
                    new_chunks.append(ch)

            if new_chunks:
                vectors = _embed([c["text"] for c in new_chunks], "search_document: ")
                for ch, vec in zip(new_chunks, vectors):
                    ch["embedding"] = vec
                data["chunks"].extend(new_chunks)

            for f, _, h in changed:
                data["files"][str(f["id"])] = {"hash": h, "filename": f["filename"]}

        # save when something changed or when the index file doesn't exist yet
        if changed or not _index_path(project_id).exists():
            _save(project_id, data)

        return {
            "files": len(files),
            "chunks": len(data["chunks"]),
            "re_embedded_files": len(changed),
        }


def search_index(project_id: int, query: str, k: int = TOP_K) -> List[dict]:
    data = _load(project_id)
    chunks = data["chunks"]
    if not chunks or not query.strip():
        return []

    q = np.array(_embed([query[:MAX_CHUNK_CHARS]], "search_query: ")[0], dtype=np.float32)
    m = np.array([c["embedding"] for c in chunks], dtype=np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-9
    q /= np.linalg.norm(q) + 1e-9
    scores = m @ q

    hits = []
    for i in np.argsort(scores)[::-1][:k]:
        if scores[i] < MIN_SCORE:
            break
        c = chunks[i]
        hits.append(
            {
                "filename": c["filename"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "text": c["text"],
                "score": round(float(scores[i]), 3),
            }
        )
    return hits