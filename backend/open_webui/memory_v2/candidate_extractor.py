"""
Candidate Extractor — hybrid heuristics + LLM extraction for memory facts.

Phase 1: Simple regex/keyword heuristics for explicit user instructions.
The actual LLM-based extraction is delegated to Mem0 via write_policy.py.
This module adds a heuristic pre-filter to catch explicit "запомни" signals
and boost their importance.
"""
import logging
import re
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Explicit memory signals in Russian and English
EXPLICIT_MEMORY_PATTERNS = [
    r'запомни\b',
    r'учитывай\b',
    r'я предпочитаю\b',
    r'мне нравится\b',
    r'я использую\b',
    r'я работаю с\b',
    r'меня зовут\b',
    r'мое имя\b',
    r'моё имя\b',
    r'я основатель\b',
    r'я разработчик\b',
    r'я из\b',
    r'я живу в\b',
    r'remember\b',
    r'my name is\b',
    r'i prefer\b',
    r'i use\b',
    r'i work with\b',
    r'i am from\b',
    r'i live in\b',
]

# Compile patterns for performance
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in EXPLICIT_MEMORY_PATTERNS]

# Factual statement patterns (user declaring facts about themselves)
FACTUAL_PATTERNS = [
    r'(?:я|мы)\s+(?:работаем?|используем?|предпочитаем?|выбрали?|решили?)\b',
    r'(?:наш|наша|наше|наши)\s+(?:проект|команда|стек|архитектура)\b',
    r'(?:мы|я)\s+(?:на|в)\s+(?:Python|TypeScript|React|Vue|Svelte|Go|Rust)\b',
]

_COMPILED_FACTUAL = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in FACTUAL_PATTERNS]


class MemoryCandidate:
    """A candidate fact for long-term memory storage."""
    def __init__(
        self,
        content: str,
        scope: str = "project",       # user | project | decision
        memory_type: str = "profile_fact",
        confidence: float = 0.7,
        importance: float = 0.5,
        source: str = "heuristic",
        entity_ids: Optional[List[str]] = None,
    ):
        self.content = content
        self.scope = scope
        self.memory_type = memory_type
        self.confidence = confidence
        self.importance = importance
        self.source = source
        self.entity_ids = entity_ids or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "scope": self.scope,
            "memory_type": self.memory_type,
            "confidence": self.confidence,
            "importance": self.importance,
            "source": self.source,
            "entity_ids": self.entity_ids,
        }


def has_explicit_memory_signal(text: str) -> bool:
    """Check if the text contains explicit memory instruction patterns."""
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            return True
    return False


def has_factual_content(text: str) -> bool:
    """Check if the text contains factual statements worth remembering."""
    for pattern in _COMPILED_FACTUAL:
        if pattern.search(text):
            return True
    return False


def extract_memory_candidates(
    messages: List[Dict[str, Any]],
    response: str,
) -> List[MemoryCandidate]:
    """
    Analyzes the chat turn (user messages + final assistant response)
    to extract candidates for long-term memory recording.

    Uses hybrid approach:
    1. Heuristic patterns for explicit signals (high confidence)
    2. Factual statement detection for implicit facts (medium confidence)

    The actual LLM-based deep extraction is handled by Mem0 in write_policy.
    """
    candidates: List[MemoryCandidate] = []

    # Extract last user message
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

    if not last_user_msg:
        return candidates

    # Check for explicit memory signals → high importance
    if has_explicit_memory_signal(last_user_msg):
        candidates.append(MemoryCandidate(
            content=last_user_msg,
            scope="user",
            memory_type="profile_fact",
            confidence=0.9,
            importance=0.9,
            source="explicit_signal",
        ))
        log.info(f"[EXTRACTOR] Explicit memory signal detected: {last_user_msg[:80]}...")

    # Check for factual content → medium importance
    elif has_factual_content(last_user_msg):
        candidates.append(MemoryCandidate(
            content=last_user_msg,
            scope="project",
            memory_type="architecture_fact",
            confidence=0.6,
            importance=0.5,
            source="factual_heuristic",
        ))
        log.debug(f"[EXTRACTOR] Factual content detected: {last_user_msg[:80]}...")

    return candidates
