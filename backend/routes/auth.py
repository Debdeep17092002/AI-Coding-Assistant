from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])   # "/ai", "/code", "/projects" in the others


@router.get("/ping")
def ping():
    return {"status": "ok"}