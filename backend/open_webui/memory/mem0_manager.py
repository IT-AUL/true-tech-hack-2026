"""
memory/mem0_manager.py
======================
Singleton wrapper around Mem0's Memory client configured for:
  - LLM provider: OpenAI-compatible (reads from env)
  - Embedder:     OpenAI-compatible (reads from env)
  - Vector store: Qdrant (reads from env, defaults to local qdrant)
  - Graph store:  Neo4j  (reads from env, defaults to docker service 'neo4j')

All credentials come from environment variables – see env.py for the full list.
To configure, create / update your .env file:

    NEO4J_URI=bolt://neo4j:7687
    NEO4J_USERNAME=neo4j
    NEO4J_PASSWORD=<your-password>

    MEM0_LLM_MODEL=gpt-4o-mini
    MEM0_LLM_BASE_URL=https://api.gpt.mws.ru/v1
    MEM0_LLM_API_KEY=<your-key>

    MEM0_EMBEDDER_MODEL=text-embedding-3-small
    MEM0_EMBEDDER_BASE_URL=https://api.gpt.mws.ru/v1
    MEM0_EMBEDDER_API_KEY=<your-key>

    MEM0_VECTOR_STORE_URL=http://qdrant:6333
    MEM0_SEARCH_TOP_K=10
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy singleton – created once on first use so that missing env vars do not
# crash the entire application at import time.
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_mem0_client():
    """Return a fully-configured Mem0 Memory instance (singleton)."""
    from open_webui.env import (
        MEM0_EMBEDDER_API_KEY,
        MEM0_EMBEDDER_BASE_URL,
        MEM0_EMBEDDER_MODEL,
        MEM0_EMBEDDER_PROVIDER,
        MEM0_LLM_API_KEY,
        MEM0_LLM_BASE_URL,
        MEM0_LLM_MODEL,
        MEM0_LLM_PROVIDER,
        MEM0_VECTOR_STORE_COLLECTION,
        MEM0_VECTOR_STORE_PROVIDER,
        MEM0_VECTOR_STORE_URL,
        NEO4J_PASSWORD,
        NEO4J_URI,
        NEO4J_USERNAME,
    )

    try:
        from mem0 import Memory
    except ImportError as exc:
        raise RuntimeError(
            "mem0ai is not installed. Add 'mem0ai' to requirements.txt and rebuild the Docker image."
        ) from exc

    config: dict[str, Any] = {
        'llm': {
            'provider': MEM0_LLM_PROVIDER,
            'config': {
                'model': MEM0_LLM_MODEL,
                'api_key': MEM0_LLM_API_KEY,
            },
        },
        'embedder': {
            'provider': MEM0_EMBEDDER_PROVIDER,
            'config': {
                'model': MEM0_EMBEDDER_MODEL,
                'api_key': MEM0_EMBEDDER_API_KEY,
            },
        },
        'vector_store': {
            'provider': MEM0_VECTOR_STORE_PROVIDER,
            'config': {
                'url': MEM0_VECTOR_STORE_URL,
                'collection_name': MEM0_VECTOR_STORE_COLLECTION,
            },
        },
        'graph_store': {
            'provider': 'neo4j',
            'config': {
                'url': NEO4J_URI,
                'username': NEO4J_USERNAME,
                'password': NEO4J_PASSWORD,
            },
        },
    }

    # Inject custom base_url for OpenAI-compatible providers if set
    if MEM0_LLM_BASE_URL:
        config['llm']['config']['openai_base_url'] = MEM0_LLM_BASE_URL
    if MEM0_EMBEDDER_BASE_URL:
        config['embedder']['config']['openai_base_url'] = MEM0_EMBEDDER_BASE_URL

    log.info('Initializing Mem0 Memory client with Neo4j graph store at %s', NEO4J_URI)
    return Memory.from_config(config)


# ---------------------------------------------------------------------------
# Public async helpers
# ---------------------------------------------------------------------------


async def add_messages_to_project_memory(
    project_id: str,
    user_id: str,
    messages: list[dict],
) -> None:
    """
    Extract and store facts from *messages* into the project's long-term memory.

    ``messages`` follows the OpenAI format: list of
    ``{"role": "user"|"assistant", "content": "..."}``.

    This call is intentionally fire-and-forget (wrapped in asyncio.to_thread)
    so it does not block the streaming response.
    """

    def _sync_add():
        mem = _get_mem0_client()
        # agent_id scopes memories to the project so different projects
        # share no facts, even for the same user.
        mem.add(
            messages=messages,
            user_id=user_id,
            agent_id=f'project-{project_id}',
            metadata={'project_id': project_id},
        )

    try:
        await asyncio.to_thread(_sync_add)
    except Exception as exc:
        log.warning('Mem0 add_messages_to_project_memory failed (non-fatal): %s', exc)


async def search_project_memory(
    project_id: str,
    user_id: str,
    query: str,
    top_k: int | None = None,
) -> list[dict]:
    """
    Search the project's long-term memory for facts relevant to *query*.

    Returns a list of memory objects with at least a ``memory`` string key.
    Returns ``[]`` on any error so callers can proceed without memory context.
    """
    from open_webui.env import MEM0_SEARCH_TOP_K

    k = top_k if top_k is not None else MEM0_SEARCH_TOP_K

    def _sync_search() -> list[dict]:
        mem = _get_mem0_client()
        results = mem.search(
            query=query,
            user_id=user_id,
            agent_id=f'project-{project_id}',
            limit=k,
        )
        # Mem0 returns {"results": [...]} in newer versions, handle both shapes.
        if isinstance(results, dict):
            return results.get('results', [])
        return results or []

    try:
        return await asyncio.to_thread(_sync_search)
    except Exception as exc:
        log.warning('Mem0 search_project_memory failed (non-fatal): %s', exc)
        return []


async def get_all_project_memories(project_id: str, user_id: str) -> list[dict]:
    """Return all stored memories for the project (for display in the UI)."""

    def _sync_get() -> list[dict]:
        mem = _get_mem0_client()
        results = mem.get_all(
            user_id=user_id,
            agent_id=f'project-{project_id}',
        )
        if isinstance(results, dict):
            return results.get('results', [])
        return results or []

    try:
        return await asyncio.to_thread(_sync_get)
    except Exception as exc:
        log.warning('Mem0 get_all_project_memories failed (non-fatal): %s', exc)
        return []


async def delete_project_memory(
    project_id: str,
    user_id: str,
    memory_id: str,
) -> bool:
    """Delete a single memory entry by Mem0 memory id."""

    def _sync_delete() -> None:
        mem = _get_mem0_client()
        mem.delete(memory_id=memory_id)

    try:
        await asyncio.to_thread(_sync_delete)
        return True
    except Exception as exc:
        log.warning('Mem0 delete_project_memory failed: %s', exc)
        return False


async def delete_all_project_memories(project_id: str, user_id: str) -> bool:
    """Wipe all memories associated with a project (called on project delete)."""

    def _sync_delete_all() -> None:
        mem = _get_mem0_client()
        mem.delete_all(
            user_id=user_id,
            agent_id=f'project-{project_id}',
        )

    try:
        await asyncio.to_thread(_sync_delete_all)
        return True
    except Exception as exc:
        log.warning('Mem0 delete_all_project_memories failed: %s', exc)
        return False
