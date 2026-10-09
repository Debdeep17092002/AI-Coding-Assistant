import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.database import SessionLocal, get_db
from database.models import ChatMessage, Project, User
from routes.auth import get_current_user
from routes.projects import get_owned_project
from services import prompt_manager as pm
from services.ai_service import AIServiceError, ask_ai, stream_ai
from services.embedding_service import EmbeddingError, search_index, sync_index

from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/ai", tags=["ai"])
logger = logging.getLogger(__name__)


# ---------- schemas ----------
class CodeRequest(BaseModel):
    code: str
    language: str = "python"
    error: Optional[str] = None


class GenerateRequest(BaseModel):
    request: str
    language: str = "python"


class ChatRequest(BaseModel):
    project_id: int
    message: str
    code: Optional[str] = None
    language: str = "python"
    use_project: bool = True


class SearchRequest(BaseModel):
    project_id: int
    query: str
    k: int = 4


class AIResponse(BaseModel):
    result: str


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str


class SearchHit(BaseModel):
    filename: str
    start_line: int
    end_line: int
    score: float
    text: str


class IndexOut(BaseModel):
    files: int
    chunks: int
    re_embedded_files: int


# ---------- helpers ----------
def guard_size(*texts: Optional[str]):
    for t in texts:
        if t and len(t) > pm.MAX_CODE_CHARS:
            raise HTTPException(413, f"Input too large (max {pm.MAX_CODE_CHARS} characters)")


def run_ai(prompt_name: str, user_message: str) -> AIResponse:
    try:
        system = pm.load_system_prompt(prompt_name)
        reply = ask_ai(system, [{"role": "user", "content": user_message}])
        return AIResponse(result=reply)
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except AIServiceError as e:
        raise HTTPException(502, str(e))


def project_files(project: Project) -> List[dict]:
    return [{"id": f.id, "filename": f.filename, "content": f.content} for f in project.files]


def project_context(project: Project, query: str) -> str:
    """Find relevant chunks of the project's files. Never breaks the chat if it fails."""
    if not project.files:
        return ""
    try:
        sync_index(project.id, project_files(project))
        return pm.build_context_block(search_index(project.id, query))
    except Exception as e:  # retrieval is optional, so the chat continues without it
        logger.warning("Project context unavailable: %s", e)
        return ""


def load_history(db: Session, project_id: int, limit: int = 10) -> List[dict]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    while rows and rows[0].role != "user":  # conversation must start with a user message
        rows.pop(0)
    return [{"role": r.role, "content": r.content} for r in rows]


def save_exchange(project_id: int, user_text: str, reply: str):
    db = SessionLocal()  # own session: the request's session may be closed while streaming
    try:
        db.add(ChatMessage(project_id=project_id, role="user", content=user_text))
        db.add(ChatMessage(project_id=project_id, role="assistant", content=reply))
        db.commit()
    finally:
        db.close()


# ---------- one-shot tools ----------
@router.post("/explain", response_model=AIResponse)
def explain(data: CodeRequest, user: User = Depends(get_current_user)):
    guard_size(data.code)
    return run_ai("explain_code", pm.build_code_message(data.code, data.language))


@router.post("/debug", response_model=AIResponse)
def debug(data: CodeRequest, user: User = Depends(get_current_user)):
    guard_size(data.code, data.error)
    return run_ai("debug_code", pm.build_code_message(data.code, data.language, data.error))


@router.post("/refactor", response_model=AIResponse)
def refactor(data: CodeRequest, user: User = Depends(get_current_user)):
    guard_size(data.code)
    return run_ai("refactor_code", pm.build_code_message(data.code, data.language))


@router.post("/generate", response_model=AIResponse)
def generate(data: GenerateRequest, user: User = Depends(get_current_user)):
    guard_size(data.request)
    return run_ai("generate_code", pm.build_generate_message(data.request, data.language))


# ---------- chat with memory + project context ----------
@router.post("/chat", response_model=AIResponse)
def chat(
    data: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = get_owned_project(data.project_id, db, user)
    guard_size(data.message, data.code)

    context = project_context(project, data.message) if data.use_project else ""
    messages = load_history(db, project.id) + [
        {
            "role": "user",
            "content": pm.build_chat_message(data.message, data.code, data.language, context),
        }
    ]
    try:
        reply = ask_ai(pm.load_system_prompt("chat"), messages)
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except AIServiceError as e:
        raise HTTPException(502, str(e))

    # save only the plain message (not the retrieved context), and only after success
    db.add(ChatMessage(project_id=project.id, role="user", content=data.message))
    db.add(ChatMessage(project_id=project.id, role="assistant", content=reply))
    db.commit()
    return AIResponse(result=reply)


@router.post("/chat/stream")
def chat_stream(
    data: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = get_owned_project(data.project_id, db, user)
    guard_size(data.message, data.code)

    project_id = project.id
    user_text = data.message
    context = project_context(project, data.message) if data.use_project else ""
    messages = load_history(db, project_id) + [
        {
            "role": "user",
            "content": pm.build_chat_message(data.message, data.code, data.language, context),
        }
    ]
    try:
        system = pm.load_system_prompt("chat")
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))

    def generate_stream():
        parts = []
        try:
            for chunk in stream_ai(system, messages):
                parts.append(chunk)
                yield chunk
        except AIServiceError as e:
            yield f"\n\n[AI error: {e}]"
            return
        save_exchange(project_id, user_text, "".join(parts))

    return StreamingResponse(generate_stream(), media_type="text/plain")


@router.get("/history/{project_id}", response_model=List[HistoryItem])
def history(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = get_owned_project(project_id, db, user)
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.project_id == project.id)
        .order_by(ChatMessage.id)
        .all()
    )


# ---------- project index (RAG) ----------
@router.post("/index/{project_id}", response_model=IndexOut)
def reindex(
    project_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update the project's index. Use force=true to rebuild it from scratch."""
    project = get_owned_project(project_id, db, user)
    try:
        return sync_index(project.id, project_files(project), force=force)
    except EmbeddingError as e:
        raise HTTPException(502, str(e))


@router.post("/search", response_model=List[SearchHit])
def search(
    data: SearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Debug tool: shows which chunks the assistant would retrieve for a question."""
    project = get_owned_project(data.project_id, db, user)
    guard_size(data.query)
    try:
        sync_index(project.id, project_files(project))
        return search_index(project.id, data.query, k=max(1, min(data.k, 10)))
    except EmbeddingError as e:
        raise HTTPException(502, str(e))