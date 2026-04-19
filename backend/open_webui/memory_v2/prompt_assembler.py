"""
Prompt Assembler — builds structured context slots from the memory bundle.

Produces a formatted system message injection with sections:
- [User Preferences]
- [Project Context]
- [Prior Decisions]
- [Thread State]

Token budget is enforced to prevent system prompt bloat.
"""
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Hard limits per slot (number of facts, not tokens — Phase 1)
MAX_USER_PREFS = 3
MAX_PROJECT_FACTS = 5
MAX_PRIOR_DECISIONS = 3
MAX_ARTIFACT_CONTEXT = 2


def assemble_memory_prompt(
    bundle: Dict[str, Any],
    resolved: Dict[str, Any],
) -> Optional[str]:
    """Assembles structured memory context for system message injection.

    Returns a formatted string with labeled sections, or None if nothing to inject.
    """
    slots: list[str] = []

    # --- User Preferences ---
    user_prefs = bundle.get("user_preferences", [])[:MAX_USER_PREFS]
    if user_prefs:
        lines = "\n".join(f"- {fact}" for fact in user_prefs)
        slots.append(f"[User Preferences]\n{lines}")

    # --- Project Context ---
    project_facts = bundle.get("project_facts", [])[:MAX_PROJECT_FACTS]
    if project_facts:
        lines = "\n".join(f"- {fact}" for fact in project_facts)
        slots.append(f"[Project Context]\n{lines}")

    # --- Prior Decisions ---
    prior = bundle.get("prior_decisions", [])[:MAX_PRIOR_DECISIONS]
    if prior:
        lines = "\n".join(f"- {fact}" for fact in prior)
        slots.append(f"[Prior Decisions]\n{lines}")

    # --- Artifact Context ---
    artifacts = bundle.get("artifact_context", [])[:MAX_ARTIFACT_CONTEXT]
    if artifacts:
        lines = "\n".join(f"- {fact}" for fact in artifacts)
        slots.append(f"[Artifact Context]\n{lines}")

    # --- Thread State ---
    if resolved.get("topic_hash"):
        thread_lines = [
            f"- Topic Hash: {resolved['topic_hash']}",
            f"- Needs Long Term Memory: {resolved.get('needs_long_term_memory', False)}",
        ]
        if resolved.get("active_entities"):
            thread_lines.append(f"- Active Entities: {', '.join(resolved['active_entities'])}")
        slots.append("[Thread State]\n" + "\n".join(thread_lines))

    if not slots:
        return None

    return "\n\n".join(slots) + "\n"
