import asyncio
import logging
from typing import Any, Dict, List, Optional, TypedDict

from fastapi import Request

from open_webui.memory_v2.session_cache import session_cache
from open_webui.memory_v2.context_resolver import ResolvedContext

log = logging.getLogger(__name__)

class ContextBundle(TypedDict):
    user_preferences: List[str]
    project_facts: List[str]
    prior_decisions: List[str]
    artifact_context: List[str]
    thread_summary: Optional[str]

async def get_context_bundle(
    request: Request,
    user: Any,
    project_id: Optional[str],
    thread_id: str,
    resolved: ResolvedContext,
    event_emitter: Optional[Any] = None,
) -> ContextBundle:
    """Retrieval Pipeline with Cascade and Fallbacks."""
    
    cache_key = f"memory_cache:{project_id or 'global'}:{resolved['topic_hash']}"
    
    # Cascade 1: Session Cache Hit
    cached_bundle = await session_cache.get(cache_key)
    if cached_bundle:
        log.debug(f"[MEMORY GATEWAY] Cache hit for topic {resolved['topic_hash']}")
        
        if event_emitter:
            await event_emitter({
                "type": "status",
                "data": {
                    "action": "memory",
                    "description": "Smart Cache Hit",
                    "routing": {
                        "category": "memory",
                        "subtitle": "Smart Cache Hit",
                        "reasoning": "Fast Context Retrieval (Session Hit)."
                    },
                    "done": True
                }
            })
            
        return cached_bundle
        
    # Standard empty bundle
    bundle: ContextBundle = {
        "user_preferences": [],
        "project_facts": [],
        "prior_decisions": [],
        "artifact_context": [],
        "thread_summary": None,
    }
    
    # If this is a very short continuation, we might not even hit the long-term DB
    if not resolved["needs_long_term_memory"]:
        log.debug(f"[MEMORY GATEWAY] Skipping long-term search (needs_long_term_memory=False)")
        # Cache this empty/light bundle to save time on next micro-turns
        await session_cache.set(cache_key, bundle, ttl_seconds=600)
        return bundle
        
    log.info(f"[MEMORY GATEWAY] Fetching long-term memory for thread {thread_id}")

    if event_emitter:
        log.info("[MEMORY GATEWAY] Emitting 'Querying Knowledge Base' status via WebSocket")
        await event_emitter({
            "type": "status",
            "data": {
                "action": "memory",
                "description": "Querying Knowledge Base",
                "routing": {
                    "category": "memory",
                    "subtitle": "Querying Knowledge Base",
                    "reasoning": "Searching Long-term Memory Stores..."
                },
                "done": False
            }
        })
    else:
        log.warning("[MEMORY GATEWAY] No event_emitter available, skipping UI status")

    # Cascade 2: Parallel fetch User Memory & Project Memory
    # We use existing OpenWebUI tools but supply the 'resolved_query'
    user_task = _fetch_user_memory(request, user, resolved["resolved_query"])
    project_task = _fetch_project_memory(project_id, user.id, resolved["resolved_query"])
    
    user_docs, project_docs = await asyncio.gather(user_task, project_task, return_exceptions=True)
    
    if isinstance(user_docs, list):
        bundle["user_preferences"] = user_docs
        
    if isinstance(project_docs, list):
        bundle["project_facts"] = project_docs

    # Rerank & Budget constraint
    bundle["user_preferences"] = bundle["user_preferences"][:3]  # Max 3 facts
    bundle["project_facts"] = bundle["project_facts"][:5]        # Max 5 facts

    total_facts = len(bundle["user_preferences"]) + len(bundle["project_facts"])

    if event_emitter:
        await event_emitter({
            "type": "status",
            "data": {
                "action": "memory",
                "description": "Memory Extracted",
                "routing": {
                    "category": "memory",
                    "subtitle": "Memory Extracted",
                    "reasoning": f"Retrieved {total_facts} relevant facts from User & Project sources."
                },
                "done": True
            }
        })

    # Cache the structured bundle
    await session_cache.set(cache_key, bundle, ttl_seconds=900)
    
    return bundle



async def _fetch_user_memory(request: Request, user: Any, query: str) -> List[str]:
    """Wraps query_memory logic safely."""
    try:
        from open_webui.routers.memories import QueryMemoryForm, query_memory
        
        results = await query_memory(
            request,
            QueryMemoryForm(content=query, k=5), # Fetch 5 to dedup
            user,
        )
        
        found_facts = []
        if results and hasattr(results, 'documents'):
            if results.documents and len(results.documents) > 0:
                # results.documents[0] is the list of top matches
                for doc in results.documents[0]:
                    found_facts.append(doc)
        return found_facts
    except Exception as e:
        log.warning(f"Failed to fetch user memory: {e}")
        return []

async def _fetch_project_memory(project_id: Optional[str], user_id: str, query: str) -> List[str]:
    """Wraps mem0 project memory logic."""
    if not project_id:
        return []
    try:
        from open_webui.memory.mem0_manager import search_project_memory
        
        facts = await search_project_memory(
            project_id=project_id,
            user_id=user_id,
            query=query,
            top_k=5,
        )
        found_facts = []
        for fact in facts:
            text = fact.get('memory', '') or fact.get('text', '')
            if text:
                found_facts.append(text)
        return found_facts
    except Exception as e:
        log.warning(f"Failed to fetch project memory: {e}")
        return []
