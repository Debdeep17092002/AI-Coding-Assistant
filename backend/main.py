from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.database import Base, engine
from database import models  # noqa: F401  (registers the tables)
from routes import auth, ai, code, projects

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Coding Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, ai.router, code.router, projects.router):
    app.include_router(r)


@app.get("/")
def root():
    return {"message": "AI Coding Assistant API is running"}