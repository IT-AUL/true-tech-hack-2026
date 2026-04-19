"""
Memory Write Policy — governs what gets written to long-term memory.

Responsibilities:
1. Extract MemoryCandidates via heuristics
2. Route candidates to the correct store (user / project / decision)
3. Delegate to Mem0 for LLM-based extraction + Qdrant write
4. Log what was extracted for debugging
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from open_webui.memory_v2.candidate_extractor import (
    MemoryCandidate,
    extract_memory_candidates,
    has_explicit_memory_signal,
)

log = logging.getLogger(__name__)


async def write_memory_candidates(
    user_id: str,
    project_id: Optional[str],
    thread_id: str,
    messages: List[Dict[str, Any]],
    response_text: str,
    resolved: Dict[str, Any],
):
    """
    Background job triggered after the stream/response is complete.
    Extracts facts and safely writes them to Long-Term Memory.

    Flow:
    1. Run hybrid heuristic extraction
    2. If project_id exists → push to Mem0 (which does LLM extraction + Qdrant write)
    3. If explicit signal detected → boost the importance for Mem0
    """
    try:
        log.debug(f"[MEMORY POLICY] Starting background extraction for thread {thread_id}")

        # 1. Run heuristic candidate extraction
        candidates = extract_memory_candidates(messages, response_text)

        # Extract last user message for Mem0 bridge
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                        elif isinstance(part, str):
                            text_parts.append(part)
                    content = " ".join(text_parts)
                last_user_msg = str(content)
                break

        # 2. Write to Project Memory via Mem0
        if project_id and last_user_msg and response_text:
            try:
                from open_webui.memory.mem0_manager import add_messages_to_project_memory

                await add_messages_to_project_memory(
                    project_id=project_id,
                    user_id=user_id,
                    messages=[
                        {'role': 'user', 'content': last_user_msg},
                        {'role': 'assistant', 'content': response_text},
                    ],
                )

                # Log heuristic findings for debugging
                if candidates:
                    for c in candidates:
                        log.info(
                            f"[MEMORY POLICY] Heuristic candidate: "
                            f"scope={c.scope} type={c.memory_type} "
                            f"conf={c.confidence:.1f} imp={c.importance:.1f} "
                            f"src={c.source} content={c.content[:80]}..."
                        )
                else:
                    log.debug("[MEMORY POLICY] No heuristic candidates (Mem0 LLM extraction still runs)")

                log.debug(f"[MEMORY POLICY] Pushed memory to project {project_id}")
            except Exception as mem_exc:
                log.warning(f"[MEMORY POLICY] Project memory write failed: {mem_exc}")

        # 3. Log summary
        explicit = has_explicit_memory_signal(last_user_msg) if last_user_msg else False
        log.info(
            f"[MEMORY POLICY] Done: thread={thread_id[:8]}... "
            f"project={'yes' if project_id else 'no'} "
            f"heuristic_candidates={len(candidates)} "
            f"explicit_signal={explicit}"
        )

    except Exception as e:
        log.exception(f"[MEMORY POLICY] Error in write_memory_candidates: {e}")
