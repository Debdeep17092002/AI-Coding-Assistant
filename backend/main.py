from dotenv import load_dotenv

load_dotenv()

import logging
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.database import Base, engine
from database import models  # noqa: F401  (registers the tables)
from routes import auth, ai, code, projects
from services.rate_limiter import RateLimiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Coding Assistant")

origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ai_limit = RateLimiter(int(os.getenv("RATE_LIMIT_AI", "30")))
code_limit = RateLimiter(int(os.getenv("RATE_LIMIT_CODE", "30")))

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(ai.router, dependencies=[Depends(ai_limit)])
app.include_router(code.router, dependencies=[Depends(code_limit)])


@app.get("/")
def root():
    return {"message": "AI Coding Assistant API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}