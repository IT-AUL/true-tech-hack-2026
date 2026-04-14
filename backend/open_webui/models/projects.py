"""
Project DB Schema
-----------------
A Project groups chats together and provides a shared long-term memory
space backed by Mem0 / Neo4j graph store.
"""

import time
import uuid
from typing import Optional

from open_webui.internal.db import Base, get_db_context
from pydantic import BaseModel, ConfigDict
from sqlalchemy import JSON, BigInteger, Column, String, Text
from sqlalchemy.orm import Session

####################
# SQLAlchemy model
####################


class Project(Base):
    __tablename__ = 'project'

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    meta = Column(JSON, server_default='{}')
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


####################
# Pydantic models
####################


class ProjectModel(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    meta: dict = {}
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class ProjectForm(BaseModel):
    title: str
    description: Optional[str] = None
    meta: dict = {}


class ProjectUpdateForm(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    meta: Optional[dict] = None


####################
# Table helper
####################


class ProjectTable:
    def insert_new_project(
        self,
        user_id: str,
        form_data: ProjectForm,
        db: Session | None = None,
    ) -> ProjectModel | None:
        with get_db_context(db) as db:
            now = int(time.time())
            project = Project(
                id=str(uuid.uuid4()),
                user_id=user_id,
                title=form_data.title,
                description=form_data.description,
                meta=form_data.meta,
                created_at=now,
                updated_at=now,
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            return ProjectModel.model_validate(project)

    def get_projects_by_user_id(
        self,
        user_id: str,
        db: Session | None = None,
    ) -> list[ProjectModel]:
        with get_db_context(db) as db:
            rows = db.query(Project).filter_by(user_id=user_id).order_by(Project.updated_at.desc()).all()
            return [ProjectModel.model_validate(r) for r in rows]

    def get_project_by_id(
        self,
        project_id: str,
        db: Session | None = None,
    ) -> ProjectModel | None:
        with get_db_context(db) as db:
            row = db.get(Project, project_id)
            if row is None:
                return None
            return ProjectModel.model_validate(row)

    def update_project_by_id(
        self,
        project_id: str,
        user_id: str,
        form_data: ProjectUpdateForm,
        db: Session | None = None,
    ) -> ProjectModel | None:
        with get_db_context(db) as db:
            row = db.get(Project, project_id)
            if row is None or row.user_id != user_id:
                return None
            if form_data.title is not None:
                row.title = form_data.title
            if form_data.description is not None:
                row.description = form_data.description
            if form_data.meta is not None:
                row.meta = form_data.meta
            row.updated_at = int(time.time())
            db.commit()
            db.refresh(row)
            return ProjectModel.model_validate(row)

    def delete_project_by_id(
        self,
        project_id: str,
        user_id: str,
        db: Session | None = None,
    ) -> bool:
        with get_db_context(db) as db:
            row = db.get(Project, project_id)
            if row is None or row.user_id != user_id:
                return False
            db.delete(row)
            db.commit()
            return True


Projects = ProjectTable()
