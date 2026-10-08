from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import CodeFile, Project, User
from routes.auth import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------- schemas ----------
class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


class FileCreate(BaseModel):
    filename: str
    language: str = "python"
    content: str = ""


class FileUpdate(BaseModel):
    filename: Optional[str] = None
    language: Optional[str] = None
    content: Optional[str] = None


class FileOut(BaseModel):
    id: int
    project_id: int
    filename: str
    language: str
    content: str
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- helpers ----------
def get_owned_project(project_id: int, db: Session, user: User) -> Project:
    """Return the project only if it belongs to the user, else 404."""
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(404, "Project not found")
    return project


def get_project_file(file_id: int, project: Project, db: Session) -> CodeFile:
    code_file = db.get(CodeFile, file_id)
    if code_file is None or code_file.project_id != project.id:
        raise HTTPException(404, "File not found")
    return code_file


# ---------- project endpoints ----------
@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not data.name.strip():
        raise HTTPException(400, "Project name cannot be empty")
    project = Project(name=data.name.strip(), description=data.description, owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    projects = (
        db.query(Project)
        .filter(Project.owner_id == user.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return projects