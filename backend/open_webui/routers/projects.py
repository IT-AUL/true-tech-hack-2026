"""
routers/projects.py
===================
REST API for project management and long-term memory inspection.

Endpoints
---------
CRUD
  POST   /projects/             – Create a new project
  GET    /projects/             – List own projects
  GET    /projects/{id}         – Get project by id
  PATCH  /projects/{id}         – Update project metadata
  DELETE /projects/{id}         – Delete project (+ all its memories)

Memory
  GET    /projects/{id}/memory          – List all facts stored for project
  DELETE /projects/{id}/memory/{mem_id} – Delete one memory fact
  DELETE /projects/{id}/memory          – Wipe all project memories

Chats
  GET    /projects/{id}/chats           – List chats in the project
  POST   /projects/{id}/chats/{chat_id} – Assign an existing chat to the project
  DELETE /projects/{id}/chats/{chat_id} – Remove chat from project

Files
  GET    /projects/{id}/files           – List all files associated with chats in the project
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_session
from open_webui.memory.mem0_manager import (
    delete_all_project_memories,
    delete_project_memory,
    get_all_project_memories,
)
from open_webui.models.chats import Chat, ChatTitleIdResponse
from open_webui.models.files import Files, FileModelResponse
from open_webui.models.projects import ProjectForm, ProjectModel, Projects, ProjectUpdateForm
from open_webui.utils.auth import get_verified_user
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_project_access(project_id: str, user, db: Session) -> ProjectModel:
    """Fetch project and verify ownership, raising 404/403 as appropriate."""
    project = Projects.get_project_by_id(project_id, db=db)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    if project.user_id != user.id and user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)
    return project


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.post('/', response_model=ProjectModel)
async def create_project(
    form_data: ProjectForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    """Create a new project belonging to the current user."""
    project = Projects.insert_new_project(user.id, form_data, db=db)
    if not project:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT())
    return project


@router.get('/', response_model=list[ProjectModel])
async def list_projects(
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    """Return all projects owned by the current user."""
    return Projects.get_projects_by_user_id(user.id, db=db)


@router.get('/{project_id}', response_model=ProjectModel)
async def get_project(
    project_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    return _require_project_access(project_id, user, db)


@router.put('/{project_id}', response_model=ProjectModel)
async def update_project(
    project_id: str,
    form_data: ProjectUpdateForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    _require_project_access(project_id, user, db)
    updated = Projects.update_project_by_id(project_id, user.id, form_data, db=db)
    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT())
    return updated


@router.delete('/{project_id}', response_model=bool)
async def delete_project(
    project_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    """Delete the project and all its Mem0 memories."""
    _require_project_access(project_id, user, db)
    # Wipe graph + vector memories first (non-fatal if fails)
    await delete_all_project_memories(project_id=project_id, user_id=user.id)
    ok = Projects.delete_project_by_id(project_id, user.id, db=db)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT())
    return True


# ---------------------------------------------------------------------------
# Memory endpoints
# ---------------------------------------------------------------------------


@router.get('/{project_id}/memory')
async def list_project_memory(
    project_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    """Return all facts stored in the project's long-term memory (Mem0)."""
    _require_project_access(project_id, user, db)
    memories = await get_all_project_memories(project_id=project_id, user_id=user.id)
    return {'memories': memories}


@router.delete('/{project_id}/memory', response_model=bool)
async def wipe_project_memory(
    project_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    """Delete ALL memory entries for the project."""
    _require_project_access(project_id, user, db)
    return await delete_all_project_memories(project_id=project_id, user_id=user.id)


@router.delete('/{project_id}/memory/{memory_id}', response_model=bool)
async def delete_memory_entry(
    project_id: str,
    memory_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    """Delete a single memory fact by its Mem0 id."""
    _require_project_access(project_id, user, db)
    return await delete_project_memory(project_id=project_id, user_id=user.id, memory_id=memory_id)


# ---------------------------------------------------------------------------
# Chat assignment endpoints
# ---------------------------------------------------------------------------


@router.get('/{project_id}/chats', response_model=list[ChatTitleIdResponse])
async def list_project_chats(
    project_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    """Return all chats assigned to the project."""
    _require_project_access(project_id, user, db)
    chats = (
        db.query(Chat)
        .filter_by(project_id=project_id, user_id=user.id, archived=False)
        .order_by(Chat.updated_at.desc())
        .all()
    )
    return [
        ChatTitleIdResponse(
            id=c.id,
            title=c.title,
            updated_at=c.updated_at,
            created_at=c.created_at,
        )
        for c in chats
    ]


@router.post('/{project_id}/chats/{chat_id}', response_model=bool)
async def assign_chat_to_project(
    project_id: str,
    chat_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    """Assign an existing chat to the project."""
    _require_project_access(project_id, user, db)
    chat = db.get(Chat, chat_id)
    if not chat or chat.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    chat.project_id = project_id
    db.commit()
    return True


@router.delete('/{project_id}/chats/{chat_id}', response_model=bool)
async def remove_chat_from_project(
    project_id: str,
    chat_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    """Remove a chat from the project (sets project_id = NULL)."""
    _require_project_access(project_id, user, db)
    chat = db.get(Chat, chat_id)
    if not chat or chat.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    chat.project_id = None
    db.commit()
    return True


# ---------------------------------------------------------------------------
# File endpoints
# ---------------------------------------------------------------------------


@router.get('/{project_id}/files', response_model=list[FileModelResponse])
async def list_project_files(
    project_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    """Return all files associated with chats in the project."""
    _require_project_access(project_id, user, db)

    # Retrieve all files associated with chats belonging to this project
    chats = db.query(Chat).filter_by(project_id=project_id, user_id=user.id).all()

    file_ids = set()
    for chat in chats:
        chat_data = chat.chat or {}

        # Check top-level files if they exist
        files_toplevel = chat_data.get('files', [])
        for f in files_toplevel:
            if isinstance(f, dict) and 'id' in f:
                file_ids.add(f['id'])
            elif isinstance(f, str):
                file_ids.add(f)

        # Check files inside messages
        history = chat_data.get('history', {})
        messages = history.get('messages', {})
        for msg_id, msg in messages.items():
            if isinstance(msg, dict):
                msg_files = msg.get('files', [])
                for f in msg_files:
                    if isinstance(f, dict) and 'id' in f:
                        file_ids.add(f['id'])
                    elif isinstance(f, str):
                        file_ids.add(f)

                # Also check inline embedded files in the message or models.
                # If there are any other file references, they might be in msg structure.

    if not file_ids:
        return []

    project_files = Files.get_files_by_ids(list(file_ids), db=db)
    return project_files
