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
import re
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy singleton – created once on first use so that missing env vars do not
# crash the entire application at import time.
# ---------------------------------------------------------------------------


_mem0_instance = None


def _strip_think(text: str) -> str:
    """Remove <think>...</think> reasoning blocks emitted by Qwen3/GLM/R1 models."""
    # Remove closed blocks
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    # Remove unclosed blocks (model cut off mid-thought)
    text = re.sub(r'<think>[\s\S]*$', '', text, flags=re.IGNORECASE)
    return text.strip()


def _sanitize_messages(messages: list[dict]) -> list[dict]:
    """Strip thinking blocks from all message content before writing to memory."""
    cleaned = []
    for msg in messages:
        content = msg.get('content', '')
        if isinstance(content, str):
            content = _strip_think(content)
        cleaned.append({**msg, 'content': content})
    return cleaned

def _get_mem0_client():
    """Return a fully-configured Mem0 Memory instance (singleton)."""
    global _mem0_instance
    
    if _mem0_instance is not None:
        return _mem0_instance
    
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

    from open_webui.env import MEM0_EMBEDDING_DIMS

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
                'embedding_model_dims': MEM0_EMBEDDING_DIMS,
            },
        },
        'custom_fact_extraction_prompt': (
            'You are a Personal Memory Assistant. Your ONLY job is to extract '
            'factual information ABOUT THE USER from the conversation.\n\n'
            'Focus on:\n'
            "- User's name, location, role, company, team\n"
            "- User's preferences (language, tools, frameworks, style)\n"
            "- User's goals, projects, deadlines\n"
            '- Technical decisions the user made\n'
            '- Important facts the user shared about themselves\n\n'
            'DO NOT extract:\n'
            '- What the assistant said or how the assistant behaves\n'
            '- Generic conversational patterns\n'
            '- Greetings or pleasantries\n\n'
            'Return each fact as a short, clear sentence about the user. '
            'If no user facts are found, return an empty list.\n'
            "Example: \"User's name is Renat\" or \"User prefers dark theme\" or "
            '"User is building a project called VibeHub".\n\n'
            'IMPORTANT: Output ONLY the JSON list of facts. '
            'Do NOT use <think>...</think> blocks or any chain-of-thought reasoning.'
        ),
    }

    # Only enable Neo4j graph store if credentials are actually configured.
    # Without this, local development works with just the vector store.
    if NEO4J_PASSWORD:
        config['graph_store'] = {
            'provider': 'neo4j',
            'config': {
                'url': NEO4J_URI,
                'username': NEO4J_USERNAME,
                'password': NEO4J_PASSWORD,
            },
        }
        log.info('Initializing Mem0 Memory client with Neo4j graph store at %s', NEO4J_URI)
    else:
        log.info('Initializing Mem0 Memory client WITHOUT graph store (Neo4j not configured)')

    # Inject custom base_url for OpenAI-compatible providers if set
    if MEM0_LLM_BASE_URL:
        config['llm']['config']['openai_base_url'] = MEM0_LLM_BASE_URL
    if MEM0_EMBEDDER_BASE_URL:
        config['embedder']['config']['openai_base_url'] = MEM0_EMBEDDER_BASE_URL

    try:
        instance = Memory.from_config(config)
        _mem0_instance = instance
        # Ensure the Qdrant collection exists with the correct dimensions.
        # Mem0's from_config creates it, but if the collection was deleted externally
        # (e.g., during development), we need to re-create it explicitly.
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            qc = QdrantClient(url=MEM0_VECTOR_STORE_URL)
            collection_name = MEM0_VECTOR_STORE_COLLECTION
            existing = [c.name for c in qc.get_collections().collections]
            if collection_name not in existing:
                qc.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=MEM0_EMBEDDING_DIMS,
                        distance=Distance.COSINE,
                    ),
                )
                log.info(f'Created Qdrant collection "{collection_name}" with dims={MEM0_EMBEDDING_DIMS}')
            else:
                log.info(f'Qdrant collection "{collection_name}" already exists')
        except Exception as qe:
            log.warning(f'Qdrant collection pre-check failed (non-fatal): {qe}')
        return instance
    except Exception as exc:
        log.warning('Mem0 initialization failed: %s', exc)
        raise


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
        # Strip <think>...</think> blocks from thinking models (Qwen3, GLM, R1)
        # before writing to Qdrant to prevent reasoning traces polluting facts.
        clean_messages = _sanitize_messages(messages)
        # agent_id scopes memories to the project so different projects
        # share no facts, even for the same user.
        mem.add(
            messages=clean_messages,
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
