"""
Context Resolver — analyzes the conversation to determine retrieval strategy.

Outputs:
- resolved_query: enriched search query (not just last message)
- task_type: chat | code | research | planning | creative
- mode_hint: optional mode override
- topic_hash: fingerprint for session cache
- needs_long_term_memory: gating heuristic
- referenced_artifact_ids: file references
- active_entities: extracted named entities
"""
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, TypedDict

log = logging.getLogger(__name__)


class ResolvedContext(TypedDict):
    resolved_query: str
    task_type: str
    mode_hint: Optional[str]
    topic_hash: str
    needs_long_term_memory: bool
    referenced_artifact_ids: List[str]
    active_entities: List[str]


def _generate_topic_hash(messages: List[Dict[str, Any]]) -> str:
    """Use the context of the last few messages to shape a topic footprint."""
    recent_texts = []
    for msg in messages[-4:]:
        content = msg.get("content", "")
        if isinstance(content, list):
            content = str(content)
        recent_texts.append(str(content))
    combined = "||".join(recent_texts)
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


# Short follow-up phrases that don't need long-term memory
_SHORT_FOLLOWUPS = {
    "да", "ок", "сделай", "пожалуйста", "дальше", "продолжай", "еще",
    "хорошо", "ладно", "ага", "давай", "понял", "спасибо", "нет", "стоп",
    "ok", "yes", "no", "continue", "go on", "thanks", "sure", "next",
    "done", "got it", "please",
}


def _detect_needs_long_term_memory(resolved_query: str, depth: int) -> bool:
    """Heuristic to decide if we even need long-term vector retrieval."""
    content_lower = resolved_query.lower().strip()
    if len(content_lower) < 15 and content_lower in _SHORT_FOLLOWUPS:
        return False
    return True


# --- Task type detection ---

_CODE_KEYWORDS = re.compile(
    r'\b(код|code|функция|function|баг|bug|ошибка|error|debug|рефакторинг|refactor|api|endpoint'
    r'|компонент|component|тест|test|migration|деплой|deploy)\b',
    re.IGNORECASE | re.UNICODE,
)

_RESEARCH_KEYWORDS = re.compile(
    r'\b(найди|search|исследуй|research|сравни|compare|объясни|explain|перечисли|list'
    r'|обзор|overview|документация|docs|зависимости|dependencies)\b',
    re.IGNORECASE | re.UNICODE,
)

_PLANNING_KEYWORDS = re.compile(
    r'\b(план|plan|архитектура|architecture|проектируй|design|стратегия|strategy'
    r'|roadmap|этапы|phases|приоритеты|priorities)\b',
    re.IGNORECASE | re.UNICODE,
)

_CREATIVE_KEYWORDS = re.compile(
    r'\b(напиши|write|создай|create|придумай|invent|презентация|presentation'
    r'|слайды|slides|история|story|генерируй|generate)\b',
    re.IGNORECASE | re.UNICODE,
)


def _detect_task_type(text: str) -> str:
    """Classify the user message into a task type."""
    if _CODE_KEYWORDS.search(text):
        return "code"
    if _RESEARCH_KEYWORDS.search(text):
        return "research"
    if _PLANNING_KEYWORDS.search(text):
        return "planning"
    if _CREATIVE_KEYWORDS.search(text):
        return "creative"
    return "chat"


# --- Simple entity extraction ---

_TECH_ENTITIES = re.compile(
    r'\b(Python|TypeScript|JavaScript|React|Vue|Svelte|FastAPI|Django|Flask'
    r'|PostgreSQL|Postgres|Redis|Qdrant|Neo4j|Docker|Kubernetes|K8s'
    r'|Mem0|OpenWebUI|VibeHub|GPT|LLM|Qwen|DeepSeek|Llama'
    r'|Git|GitHub|CI|CD|REST|GraphQL|WebSocket|SSE'
    r'|Celery|Arq|RQ|Alembic|SQLAlchemy|Pydantic'
    r'|Chrome|Chromium|Firefox|Safari|iOS|Android'
    r'|AWS|GCP|Azure|S3|CloudFlare)\b',
    re.IGNORECASE,
)


def _extract_entities(text: str) -> List[str]:
    """Extract technology/tool/product entities from text."""
    matches = _TECH_ENTITIES.findall(text)
    # Normalize to lowercase and deduplicate
    seen = set()
    result = []
    for m in matches:
        lower = m.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(m)
    return result


async def resolve_context(
    user_id: str,
    project_id: Optional[str],
    thread_id: str,
    messages: List[Dict[str, Any]],
) -> ResolvedContext:
    """Takes recent messages and thread state and synthesizes the true user intent."""

    # Get last user message
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            if isinstance(last_user_message, list):
                text_parts = []
                for part in last_user_message:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                last_user_message = " ".join(text_parts)
            break

    # Build enriched resolved_query
    resolved_query = last_user_message
    if len(last_user_message) < 50 and len(messages) >= 2:
        prev_msg = messages[-2]
        if prev_msg.get("role") == "assistant":
            prev_content = prev_msg.get("content", "")
            if isinstance(prev_content, list):
                prev_content = str(prev_content)
            snippet = prev_content[:200]
            resolved_query = f"Context: {snippet}\nUser: {last_user_message}"

    topic_hash = _generate_topic_hash(messages)
    needs_long_term_memory = _detect_needs_long_term_memory(last_user_message, len(messages))
    task_type = _detect_task_type(last_user_message)
    active_entities = _extract_entities(last_user_message)

    # Extract file IDs / artifact refs if any
    referenced_artifacts = []
    for msg in messages[-1:]:
        metadata = msg.get("metadata", {})
        if "files" in metadata:
            for f in metadata["files"]:
                file_id = f.get("id")
                if file_id:
                    referenced_artifacts.append(file_id)

    return {
        "resolved_query": resolved_query,
        "task_type": task_type,
        "mode_hint": None,
        "topic_hash": topic_hash,
        "needs_long_term_memory": needs_long_term_memory,
        "referenced_artifact_ids": referenced_artifacts,
        "active_entities": active_entities,
    }
