"""
Enterprise auto-router for GPTHub.

Current live architecture (enterprise engine):
  1. Deterministic modality guardrails (empty request, obvious multimodal signals)
  2. LLM adjudicator first when configured — category + reasoning come from the model
  3. Optional regex override only for precise modalities when LLM is unsure (same idea as legacy)
  4. Routing cache, semantic layer, then rule/regex safety nets if LLM is unavailable or fails
  5. Separate ranked failover chain per resolved route

Legacy routing remains available behind an engine flag for shadow rollout.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import re
import time
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from typing import Any

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES = frozenset(
    {
        'image_gen',
        'audio_gen',
        'vision',
        'code',
        'math_logic',
        'research',
        'analytics',
        'creative',
        'document',
        'fallback',
    }
)

VALID_COMPLEXITIES = frozenset({'low', 'medium', 'high'})

# ---------------------------------------------------------------------------
# Regex patterns (Stage 4 safety net)
# ---------------------------------------------------------------------------

# Obvious «look at / read this image» intent — used when ROUTER_SOFT_IMAGE_ATTACHMENT is on
# to avoid forcing vision for every attachment.
_VISION_ANALYSIS_INTENT_RE = re.compile(
    r'(?i)(?:'
    r'что\s+(?:на|в)\s+(?:картинк\w*|фото|скрин\w*|изображен\w*|картинке|фото)|'
    r'что\s+это\s+(?:за\s+)?(?:фото|картинк\w*|изображен\w*)|'
    r'что\s+изображен\w*|'
    r'опиши\s+(?:что|картинк\w*|фото|изображен\w*|это)|'
    r'прочитай\s+(?:текст\s+)?(?:с|на|из)\s+(?:картинк\w*|фото|скрин\w*)|'
    r'распознай\s+(?:текст\s+)?|'
    r'найди\s+(?:на|в)\s+(?:фото|картинк\w*|изображен\w*)|'
    r'\bocr\b|'
    r"what(?:'s|\s+is)\s+(?:in\s+)?(?:this|the|on\s+the)\s+(?:image|picture|photo|screenshot)|"
    r'describe\s+(?:this|the|what\s+you\s+see)|'
    r'read\s+(?:the\s+)?text\s+(?:in|from|on)'
    r')'
)


def _vision_analysis_intent_in_text(text: str) -> bool:
    if not (text and text.strip()):
        return False
    return bool(_VISION_ANALYSIS_INTENT_RE.search(text.strip()))


def _soft_image_attachment() -> bool:
    from open_webui.env import ROUTER_SOFT_IMAGE_ATTACHMENT

    return ROUTER_SOFT_IMAGE_ATTACHMENT


PATTERNS = {
    'image_gen': re.compile(
        r'(?i)(?:'
        r'\bнарисуй\w*|\bизобрази\w*|'
        r'\bсгенер\w*\s+(?:\w+\s+)*?(?:картинк\w*|изображен\w*|пикч\w*)|'
        r'\bнарисовать\b|'
        r'\bсделай\s+(?:картинк\w*|картик\w*)|'
        r'\bсделай\b[\s\w,.]{0,55}?\b(?:картинк\w*|картик\w*|изображен\w*)|'
        r'\bсоздай\s+(?:картинк\w*|картик\w*|изображен\w*)|'
        r'\bхочу\s+(?:картинк\w*|картик\w*|изображен\w*)|\bнужна\s+(?:картинк\w*|картик\w*)|\bдай\s+(?:картинк\w*|картик\w*)|'
        r'\bкинь\s+(?:\w+\s+)*?пикч\w*|'
        r'\bdraw\b|\bgenerate\s+(?:\w+\s+)*?(?:image|picture)\b|'
        r'\bi\s+want\s+(?:\w+\s+)*?picture\b|\bpicture\s+of\b'
        r')'
    ),
    'audio_gen': re.compile(
        r'(?i)(?:'
        r'\bсгенер\w*\s+(?:\w+\s+)*?(?:звук\w*|аудио\w*|мелоди\w*|музык\w*)|'
        r'\bсоздай\s+(?:музык\w*|мелоди\w*|песн\w*|звук\w*|аудио\w*)|'
        r'\bнапиши\s+(?:музык\w*|мелоди\w*|песн\w*)|'
        r'\bсделай\s+(?:музык\w*|мелоди\w*|песн\w*|звук\w*)|'
        r'\bgenerate\s+(?:(?:a\s+)?(?:music|song|audio|sound|melody))\b|'
        r'\bcreate\s+(?:(?:a\s+)?(?:music|song|audio|melody))\b|'
        r'\bmake\s+(?:(?:a\s+)?(?:music|song|audio|melody))\b|'
        r'\bcompose\s+(?:(?:a\s+)?(?:music|song|melody))\b'
        r')'
    ),
    'code': re.compile(
        r'(?i)(?:'
        r'\bнапиши\s+(?:код\w*|функци\w*|скрипт\w*|тест\w*|программ\w*|API|сервер\w*|endpoint)|'
        r'\bкод\w*\s+на\s+\w+|\bскрипт\w*|\bбаг\w*|\bрефакторинг\w*|\bошибка\s+в\s+коде|'
        r'\bhtml\b|\bcss\b|\bjavascript\b|\bpython\b|\bc\+\+|\bjava\b|\bgolang\b|\breact\b|\bpytorch\b|'
        r'\bsql\s+запрос|\bзапрограммируй|\bсделай\s+парсер|'
        r'\bREST\s+API|\bHTTP\s+сервер|\bпомоги\s+(?:\w+\s+)*?(?:код\w*|ошибк\w*)|'
        r'\bTypeError\b|\bRuntimeError\b|\bSyntaxError\b|'
        r'\bcode\b|\bscript\b|\bdebug\b|\bfunction\b|\bпрограмм\w+\s+на\b|'
        r'\b(?:пузырьк\w*\s+сортировк|сортировк\w+|bubble\s*sort|merge\s*sort|quick\s*sort|heap\s*sort)\w*|'
        r'\bнапиши\s+(?:реализац\w*|псевдокод|алгоритм)|\bреализуй\w*\s+сортировк'
        r')'
    ),
    'math_logic': re.compile(
        r'(?i)(?:'
        r'\bреши\s+(?:уравнен\w*|задач\w*)|\bматематик\w*|\bдокажи\w*|\bуравнен\w+|\bтеорем\w*|\bалгоритм\w*|'
        r'\bвычисли\w*|\bпосчитай\w*|\bнайди\s+(?:интеграл|площадь|производн\w*)|'
        r'\bгеометри\w*|\bалгебр\w*|\bразлож\w*\s+на\s+множител|'
        # Avoid bare «логик*» — matches «логику» in everyday prose (e.g. «логику работы») and
        # poisons short-follow-up regex when prior context is concatenated.
        r'\b(?:математическ|формальн)\w*\s+логик\w*|\bлогическ\w*\s+(?:задач|выражен|цепочк)|'
        r'\bmath\b|\bequation\b|\bcalculate\b|\bderivative\b|\bintegral\b|\bsolve\b|'
        r'\d+\s*[\*x\+\-\/\^]\s*\d+'
        r')'
    ),
    'research': re.compile(
        r'(?i)(?:'
        r'\bизучи\w*|\bисследуй\w*|\bпроанализируй\s+(?:рынок|стать\w*)|'
        r'\bсравни\w*|\bнайди\s+информаци\w*|\bглубокий\s+анализ|\bпоиск\s+информаци\w*|\bподробно\s+изучи\w*|'
        r'\bсделай\s+обзор|'
        r'\bнайди\s+в\s+(?:интернет\w*|сети|google)\w*|\bпогугл\w*|\bзагугл\w*|'
        r'\bвеб[\s-]?поиск\w*|\bпоищи\s+(?:в\s+)?(?:интернет\w*|сети)\w*|'
        r'\bresearch\b|\binvestigate\b|\bweb\s+search\b'
        r')'
    ),
    'analytics': re.compile(
        r'(?i)(?:'
        r'\bанализ\s+данных|\bстатистик\w*|\bкорреляци\w*|\bcsv\b|\bграфик\w*|\bтаблиц\w*|\bотчет\w*|'
        r'\bсводк\w*|\bаналитик\w*|\bметрик\w*|\bконверси\w*|'
        r'\bdata\s+science\b|\bpandas\b|\bdataset\b|\bдатасет\w*|\banalytics\b'
        r')'
    ),
    'creative': re.compile(
        r'(?i)(?:'
        r'\bнапиши\s+(?:стих\w*|пост\w*|эссе|сочинени\w*|текст\s+(?:песни|для)|поэм\w*|рассказ\w*|сценари\w*)|'
        r'\bпридумай\s+истори\w*|\bрасскажи\s+шутк\w*|\bсценари\w*|'
        r'\bшутк\w*\s+про|\bкопирайтинг\w*|\bпродолжи\s+рассказ\w*|'
        r'\bпоэм\w*|\bcreative\b|\bstory\b|\bpoem\b|\bjoke\b'
        r')'
    ),
    'document': re.compile(
        r'(?i)(?:'
        r'\bдокумент\w*|\bpdf\b|\bпдф\b|\bпроанализируй\s+файл|\bшпаргалк\w*|\bшпоргалк\w*|'
        r'\bрезюме\b|\bконтракт\w*|\bдоговор\w*|\bскан\w*|\bтекст\s+ниже|\bdocument\b'
        r')'
    ),
}

_CODE_BLOCK_RE = re.compile(
    r'```|^(def |class |import |from |function |const |let |var |SELECT |CREATE |<div|<html)', re.MULTILINE
)

# ---------------------------------------------------------------------------
# Route -> model preference keywords (used for scored selection)
# ---------------------------------------------------------------------------

ROUTE_MODEL_PREFERENCES = {
    # Stronger / API-flagship names first — keyword score is (len - index), so order matters.
    'image_gen': (
        'gpt-image',
        'gpt-5-image',
        'dall-e',
        'imagen',
        'flux-pro',
        'flux.1',
        'flux',
        'qwen-image',
        'sd3',
        'sdxl',
        'z-image',
    ),
    'audio_gen': ('lyria', 'music', 'audio-gen'),
    'vision': (
        'vision',
        'vl',
        'gpt-4o',
        'gpt-5',
        'grok-4',
        'cotype-pro-vl',
        'omni',
        'claude-4-5',
        'claude-4-6',
        'gemini',
    ),
    'code': ('kodify', 'coder', 'devstral', 'codestral', 'deepseek-coder', 'qwen3-coder', 'code'),
    'research': (
        'qwen3-235b',
        'qwen3-max',
        'gpt-5',
        'claude-opus',
        'deepseek-chat',
        'cogito',
        'qwen3-next-80b',
        'hermes-4',
        'qwen',
        'gpt',
        'claude',
        'deepseek',
        'mistral',
    ),
    'math_logic': (
        'qwen3-235b',
        'qwen3-next-80b',
        'deepseek',
        'gpt-5',
        'claude-opus',
        'thinking',
        'qwen',
        'hermes',
        'cogito',
    ),
    'analytics': ('qwen3-235b', 'deepseek', 'gpt-5', 'qwen3-next-80b', 'claude', 'qwen', 'hermes'),
    'creative': ('claude-opus', 'gpt-5', 'qwen3-235b', 'hermes', 'claude', 'gpt', 'qwen'),
    'document': ('qwen3-235b', 'gpt-5', 'claude', 'qwen3-next-80b', 'deepseek', 'qwen', 'hermes'),
    'fallback': ('qwen', 'gpt', 'claude', 'llama', 'mistral', 'gemini', 'hermes', 'deepseek'),
}

# =========================================================================
# 1. Model Registry
# =========================================================================

_KIND_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ('image_gen', ('flux', 'dall-e', 'gpt-image', 'imagen', 'qwen-image', 'sd3', 'sdxl', 'z-image')),
    ('embedding', ('embedding', 'bge', 'rerank')),
    ('stt', ('whisper', 'transcrib', 'voxtral', 'stt', 'asr')),
    ('audio_gen', ('lyria', 'music', 'audio-gen')),
    ('vlm', ('vision', '-vl-', '-vl ', 'cotype-pro-vl')),
    ('code', ('kodify', 'coder', 'devstral', 'codestral', 'deepseek-coder', 'qwen3-coder')),
]

_TIER_PREMIUM_KW = (
    'reasoner',
    'reasoning',
    '-o1',
    '-o3',
    'gpt-5.1',
    'gpt-5.2',
    'deep-think',
    'claude-4-opus',
    'claude-4-5-opus',
    'claude-4-6',
    'grok-4',
    '235b',
    '480b',
    '397b',
    # Image generation: flagship endpoints (catalog id/name often contains these)
    'gpt-image',
    'gpt-5-image',
    'dall-e-3',
    'imagen-3',
    'flux-pro',
    'flux.1',
)
_TIER_CHEAP_KW = (
    'mini',
    'nano',
    'small',
    'anya',
    'flash',
    'lite',
    'turbo',
    'schnell',
    'lightning',
    '-7b',
    '-14b',
    'distill',
    'haiku',
    'gpt-3.5',
    'gpt-oss-20b',
)

_VLM_PROMOTION_KW = ('gpt-4o', 'gpt-5', 'grok-4', 'claude-4-5', 'claude-4-6', 'omni')


@dataclass(frozen=True, slots=True)
class ModelMeta:
    id: str
    kind: str
    tier: str
    provider_idx: int
    search_text: str


def _get_model_search_text(model: dict[str, Any]) -> str:
    parts = [
        model.get('id', ''),
        model.get('name', ''),
        model.get('owned_by', ''),
        model.get('openai', {}).get('id', '') if isinstance(model.get('openai'), dict) else '',
    ]
    return ' '.join(part for part in parts if part).lower()


def _infer_kind(search_text: str) -> str:
    for kind, keywords in _KIND_KEYWORDS:
        if any(kw in search_text for kw in keywords):
            return kind
    if any(kw in search_text for kw in _VLM_PROMOTION_KW):
        return 'vlm'
    return 'text'


def _infer_tier(search_text: str) -> str:
    if any(kw in search_text for kw in _TIER_PREMIUM_KW):
        return 'premium'
    if any(kw in search_text for kw in _TIER_CHEAP_KW):
        return 'cheap'
    return 'mid'


def build_model_registry(available_models: Any) -> list[ModelMeta]:
    if isinstance(available_models, Mapping):
        raw_list = [m for m in available_models.values() if isinstance(m, dict)]
    elif isinstance(available_models, list):
        raw_list = [m for m in available_models if isinstance(m, dict)]
    else:
        return []

    registry: list[ModelMeta] = []
    for model in raw_list:
        model_id = model.get('id')
        if not model_id or model_id == 'auto':
            continue
        search_text = _get_model_search_text(model)
        registry.append(
            ModelMeta(
                id=model_id,
                kind=_infer_kind(search_text),
                tier=_infer_tier(search_text),
                provider_idx=model.get('urlIdx', 0),
                search_text=search_text,
            )
        )
    return registry


def get_router_model(registry: list[ModelMeta]) -> ModelMeta | None:
    cheap_text = [m for m in registry if m.kind == 'text' and m.tier == 'cheap']
    if cheap_text:
        for preferred in ('anya', 'turbo', 'gpt-3.5'):
            for m in cheap_text:
                if preferred in m.search_text:
                    return m
        return cheap_text[0]
    text_models = [m for m in registry if m.kind == 'text']
    return text_models[0] if text_models else None


# =========================================================================
# 2. Feature Extractor
# =========================================================================

_TRIVIAL_MAX_LEN = 50
_SMALLTALK_SHORT_RE = re.compile(
    r'(?is)^\s*(?:'
    r'hi|hello|hey|thanks|thank\s+you|ok(?:ay)?|sure|yes|no|yep|got\s+it|cool|'
    r'how\s+are\s+you|what\'?s\s+up|whats\s+up|'
    r'привет|здравствуй(?:те)?|добрый\s+(?:день|вечер)|доброе\s+утро|'
    r'как\s+дела|как\s+ты|как\s+жизнь|как\s+настроение|что\s+нового|'
    r'ок(?:ей)?|спасибо|благодарю|да|нет|ага|понятно|ясно|хорошо'
    r')[.!?,\s]*$'
)
_PRECISE_REGEX_OVERRIDE_CATEGORIES = frozenset({'image_gen', 'audio_gen', 'vision', 'document', 'research'})


def _message_content_to_text_for_routing(content: Any) -> tuple[str, bool]:
    """Extract plain text from OpenAI-style message content; flag image parts."""
    has_image = False
    if isinstance(content, str):
        return content, False
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get('type') in ('text', 'input_text'):
                parts.append(part.get('text', ''))
            elif part.get('type') in ('image_url', 'input_image'):
                has_image = True
        return ' '.join(parts), has_image
    return '', False


def _extract_prior_conversation_for_routing(
    messages: list[dict[str, Any]],
    *,
    max_messages: int,
    max_chars: int,
) -> str:
    """
    Build a compact transcript of user/assistant turns *before* the last user message.
    Used for follow-up intent (e.g. image request after discussion).
    """
    if not messages or max_messages <= 0 or max_chars <= 0:
        return ''

    last_user_idx: int | None = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get('role') == 'user':
            last_user_idx = i
            break
    if last_user_idx is None or last_user_idx == 0:
        return ''

    prior = messages[:last_user_idx]
    filtered = [m for m in prior if m.get('role') in ('user', 'assistant')]
    if not filtered:
        return ''
    tail = filtered[-max_messages:]
    lines: list[str] = []
    for m in tail:
        role = m.get('role', '')
        text, _ = _message_content_to_text_for_routing(m.get('content'))
        text = text.strip()
        if not text:
            continue
        label = 'user' if role == 'user' else 'assistant'
        lines.append(f'{label}: {text}')
    blob = '\n'.join(lines)
    if len(blob) <= max_chars:
        return blob
    return blob[-max_chars:]


@dataclass(slots=True)
class RequestFeatures:
    text: str
    text_len: int
    has_image: bool
    has_audio: bool
    has_files: bool
    has_code_block: bool
    has_url: bool
    lang: str
    is_trivial: bool
    recent_context: str = ''


def _detect_lang(text: str) -> str:
    if not text:
        return 'other'
    cyrillic = sum(1 for ch in text if '\u0400' <= ch <= '\u04ff')
    ratio = cyrillic / max(len(text), 1)
    if ratio > 0.3:
        return 'ru'
    return 'en'


def _estimate_complexity(text_len: int) -> str:
    if text_len < 200:
        return 'low'
    if text_len < 2000:
        return 'medium'
    return 'high'


def _should_trivial_short_circuit(features: RequestFeatures) -> bool:
    """
    Skip expensive routing only for genuine small-talk / acknowledgements.

    Ordinary short requests like "сделай логотип" or "хочу картинку котика" should still go
    through semantic / LLM routing even when they are under _TRIVIAL_MAX_LEN.
    """
    if features.recent_context.strip():
        return False
    if features.has_image or features.has_audio or features.has_files or features.has_code_block or features.has_url:
        return False

    text = re.sub(r'\s+', ' ', features.text.strip().lower())
    if not text:
        return True
    if len(text) > _TRIVIAL_MAX_LEN:
        return False
    return bool(_SMALLTALK_SHORT_RE.fullmatch(text))


def _is_smalltalk_followup_turn(features: RequestFeatures) -> bool:
    """
    Short small-talk in the middle of a dialog (e.g. «Как дела» after «Привет»).

    Without this, enterprise routing concatenates prior turns into the semantic query, lexical
    similarity to seed examples drops, semantic layer abstains, and users see scary fallback text
    even though the intent is plain chit-chat.
    """
    if features.has_image or features.has_audio or features.has_files or features.has_code_block or features.has_url:
        return False
    if not features.recent_context.strip():
        return False
    text = re.sub(r'\s+', ' ', features.text.strip().lower())
    if not text or len(text) > _TRIVIAL_MAX_LEN:
        return False
    if any(p.search(text) for p in PATTERNS.values()):
        return False
    return bool(_SMALLTALK_SHORT_RE.fullmatch(text))


def extract_features(payload: dict[str, Any]) -> RequestFeatures:
    from open_webui.env import ROUTER_CONTEXT_MAX_CHARS, ROUTER_CONTEXT_MAX_MESSAGES

    messages = payload.get('messages', [])
    last_user = next((m for m in reversed(messages) if m.get('role') == 'user'), None)
    if not last_user:
        return RequestFeatures(
            text='',
            text_len=0,
            has_image=False,
            has_audio=False,
            has_files=False,
            has_code_block=False,
            has_url=False,
            lang='other',
            is_trivial=True,
            recent_context='',
        )

    recent_context = _extract_prior_conversation_for_routing(
        messages,
        max_messages=ROUTER_CONTEXT_MAX_MESSAGES,
        max_chars=ROUTER_CONTEXT_MAX_CHARS,
    )

    content = last_user.get('content', '')
    text_content = ''
    has_image = False

    if isinstance(content, str):
        text_content = content
    elif isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get('type') in ('text', 'input_text'):
                    parts.append(part.get('text', ''))
                elif part.get('type') in ('image_url', 'input_image'):
                    has_image = True
        text_content = ' '.join(parts)

    files = list(last_user.get('files', []))
    metadata = payload.get('metadata')
    if isinstance(metadata, dict):
        files.extend(metadata.get('files', []))
    # Some clients send files only on the request root before inlet merge copies them onto the message.
    root_files = payload.get('files')
    if isinstance(root_files, list):
        seen = {f.get('id') for f in files if isinstance(f, dict) and f.get('id')}
        for f in root_files:
            if isinstance(f, dict) and f.get('id') not in seen:
                files.append(f)
                seen.add(f.get('id'))
    has_files = bool(files)

    has_audio = False
    has_url = False
    for f in files:
        if isinstance(f, dict):
            ct = str(f.get('type', '') or f.get('content_type', ''))
            if 'audio' in ct or 'video' in ct:
                has_audio = True
            url = f.get('url', '') or f.get('name', '')
            if isinstance(url, str) and re.match(r'https?://', url):
                has_url = True

    if not has_url and re.search(r'https?://\S+', text_content):
        has_url = True

    text_stripped = text_content.strip()
    text_len = len(text_stripped)
    has_code_block = bool(_CODE_BLOCK_RE.search(text_stripped))
    lang = _detect_lang(text_stripped)

    is_trivial = (
        text_len <= _TRIVIAL_MAX_LEN
        and not has_image
        and not has_audio
        and not has_files
        and not has_code_block
        and not has_url
        and not any(p.search(text_stripped) for p in PATTERNS.values())
    )

    return RequestFeatures(
        text=text_stripped,
        text_len=text_len,
        has_image=has_image,
        has_audio=has_audio,
        has_files=has_files,
        has_code_block=has_code_block,
        has_url=has_url,
        lang=lang,
        is_trivial=is_trivial,
        recent_context=recent_context,
    )


# =========================================================================
# 3. RoutingDecision
# =========================================================================


@dataclass(slots=True)
class RoutingDecision:
    category: str
    complexity: str
    method: str = ''
    confidence: float = 1.0
    model_id: str | None = None
    latency_ms: int = 0
    cache_hit: bool = False
    used_model_fallback: bool = False
    failover_candidates: tuple[str, ...] = ()
    reasoning: str = ''
    trace: dict[str, Any] = field(default_factory=dict)


def _copy_routing_decision(decision: RoutingDecision) -> RoutingDecision:
    return replace(decision)


def _emit_routing_metric(decision: RoutingDecision) -> None:
    log.info(
        'routing_decision category=%s complexity=%s model=%s method=%s '
        'confidence=%.2f latency_ms=%d cache_hit=%s fallback=%s stage=%s engine=%s',
        decision.category,
        decision.complexity,
        decision.model_id or 'none',
        decision.method,
        decision.confidence,
        decision.latency_ms,
        decision.cache_hit,
        decision.used_model_fallback,
        decision.trace.get('stage', ''),
        decision.trace.get('engine', ''),
    )


# =========================================================================
# 4. TTL + LRU Cache (pure Python, no external deps)
# =========================================================================

_CACHE_MAX_SIZE = 2048
_CACHE_TTL_S = 180
_CACHE_SOFT_CONFIDENCE_THRESHOLD = 0.8


class _TTLCache:
    __slots__ = ('_data', '_maxsize', '_ttl')

    def __init__(self, maxsize: int = _CACHE_MAX_SIZE, ttl: float = _CACHE_TTL_S):
        self._data: OrderedDict[str, tuple[float, RoutingDecision]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: str) -> RoutingDecision | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        ts, decision = entry
        if time.monotonic() - ts > self._ttl:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return _copy_routing_decision(decision)

    def put(self, key: str, decision: RoutingDecision) -> None:
        self._data[key] = (time.monotonic(), _copy_routing_decision(decision))
        self._data.move_to_end(key)
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


_routing_cache = _TTLCache()


def _rules_pattern_text(features: RequestFeatures) -> str:
    """For short follow-ups, match regex patterns against prior dialog + last line."""
    from open_webui.env import ROUTER_SHORT_MESSAGE_LEN

    t = features.text.strip()
    # Do not blend prior chat into regex when the user attached something: the turn is
    # about the attachment; history often contains words that false-trigger category regexes
    # (e.g. «логику» → math_logic).
    if (
        features.recent_context
        and ROUTER_SHORT_MESSAGE_LEN > 0
        and len(t) <= ROUTER_SHORT_MESSAGE_LEN
        and not (features.has_files or features.has_image or features.has_audio)
    ):
        return (features.recent_context + '\n' + t).strip()
    return features.text


def _semantic_query_text(features: RequestFeatures) -> str:
    """Embedding query: include recent context when the last turn is short."""
    from open_webui.env import (
        ROUTER_CONTEXT_MAX_CHARS,
        ROUTER_CONTEXT_NO_MERGE_MIN_CHARS,
        ROUTER_SHORT_MESSAGE_LEN,
    )

    t = features.text.strip()
    if not features.recent_context:
        return features.text
    if ROUTER_CONTEXT_NO_MERGE_MIN_CHARS > 0 and len(t) >= ROUTER_CONTEXT_NO_MERGE_MIN_CHARS:
        return features.text
    if not ROUTER_SHORT_MESSAGE_LEN or len(t) > ROUTER_SHORT_MESSAGE_LEN:
        return features.text
    combined = (features.recent_context + '\n' + t).strip()
    if len(combined) <= ROUTER_CONTEXT_MAX_CHARS:
        return combined
    return combined[-ROUTER_CONTEXT_MAX_CHARS:]


def build_routing_cache_key(features: RequestFeatures, metadata: dict[str, Any] | None = None) -> str | None:
    """
    Cache key for routing decisions. Returns None to disable read/write for this request.
    Incorporates prior-turn hash and optional chat/message id to avoid cross-chat collisions.
    """
    from open_webui.env import ROUTER_DISABLE_ROUTING_CACHE

    if ROUTER_DISABLE_ROUTING_CACHE:
        return None
    norm = features.text.strip().lower()[:500]
    ctx_hash = hashlib.md5(features.recent_context.encode()).hexdigest()[:16] if features.recent_context else ''
    flags = ''.join(
        [
            'img' if features.has_image else '',
            'url' if features.has_url else '',
            'aud' if features.has_audio else '',
            'fil' if features.has_files else '',
            'cod' if features.has_code_block else '',
        ]
    )
    base = f'{norm}|{flags}|{ctx_hash}'
    digest = hashlib.md5(base.encode()).hexdigest()
    if metadata and isinstance(metadata, dict):
        cid = metadata.get('chat_id')
        mid = metadata.get('message_id')
        if cid is not None and mid is not None and str(cid) and str(mid):
            return f'{digest}|{cid}|{mid}'
    return digest


# =========================================================================
# Enterprise route layer
# =========================================================================

_ROUTER_ENGINE_VALUES = frozenset({'legacy', 'shadow', 'hybrid', 'semantic'})
_ROUTER_DEFAULT_ENGINE = 'hybrid'
_SEMANTIC_ABSTAIN_MARGIN = 0.05
_SEMANTIC_DEFAULT_THRESHOLD = 0.68
_SEMANTIC_ROUTE_THRESHOLDS: dict[str, float] = {
    'image_gen': 0.70,
    'audio_gen': 0.73,
    'vision': 0.74,
    'code': 0.69,
    'math_logic': 0.69,
    'research': 0.71,
    'analytics': 0.69,
    'creative': 0.67,
    'document': 0.69,
    'fallback': 0.64,
}

_IMAGE_GEN_HINTS = (
    'нарис',
    'изобраз',
    'сгенер',
    'генер',
    'созда',
    'картин',
    'изображ',
    'иллюстрац',
    'render',
    'draw',
    'generate image',
    'picture',
    'image',
)
_AUDIO_GEN_HINTS = (
    'музык',
    'мелоди',
    'песн',
    'звук',
    'audio',
    'song',
    'music',
    'melody',
)

# If the user attached a file but explicitly asks for web/search/research, do not force
# guardrail `document` — let the pipeline choose `research` (web search + synthesis).
_RESEARCH_OR_WEB_SEARCH_HINTS = (
    'поиск в интернет',
    'найди в сети',
    'найди в интернет',
    'погугл',
    'загугл',
    'поищи в интернет',
    'поищи в сети',
    'поищи информац',
    'web search',
    'search the web',
    'актуальн информац',
    'свеж информац',
    'что известно про',
    'новости про',
    'собери факт',
    'проверь по источник',
)

_SEMANTIC_ROUTE_EXAMPLES: dict[str, list[str]] = {
    'image_gen': [
        'нарисуй кота в шляпе',
        'создай иллюстрацию города будущего',
        'сгенерируй картинку для поста',
        'создай красивую картинку котика',
        'make an image of a forest',
        'generate a picture of a sunset',
        'хочу красивую картинку котика',
        'нужна обложка в виде изображения',
    ],
    'audio_gen': [
        'создай музыку для видео',
        'сгенерируй мелодию для игры',
        'напиши песню в стиле synthwave',
        'generate background music',
        'make a short audio intro',
    ],
    'vision': [
        'что на изображении',
        'опиши прикрепленную картинку',
        'проанализируй фото и скажи что видно',
        'what is shown in this image',
        'analyze the attached photo',
    ],
    'code': [
        'напиши функцию на python',
        'помоги с ошибкой в коде',
        'сделай api endpoint',
        'write a unit test for this function',
        'debug this stack trace',
        'нужен рефакторинг сервиса',
    ],
    'math_logic': [
        'реши уравнение',
        'вычисли интеграл',
        'докажи теорему',
        'solve this math problem',
        'calculate derivative',
        'объясни алгоритм сортировки',
    ],
    'research': [
        'исследуй рынок и сравни конкурентов',
        'сделай глубокий обзор темы',
        'find and compare best options',
        'prepare a detailed research summary',
        'подробно изучи и сделай выводы',
    ],
    'analytics': [
        'проанализируй csv файл',
        'построй график по данным',
        'analyze this dataset and summarize trends',
        'посчитай метрики и аномалии',
        'нужна аналитика по таблице',
    ],
    'creative': [
        'напиши пост для телеграма',
        'придумай историю про робота',
        'write a creative short story',
        'сделай продающий текст',
        'придумай слоган для бренда',
    ],
    'document': [
        'сделай summary pdf документа',
        'разбери прикрепленный договор',
        'extract key points from this document',
        'проанализируй текст файла',
        'сделай краткое резюме отчета',
    ],
    'fallback': [
        'привет',
        'как дела',
        'спасибо',
        'hello',
        'what can you do',
        'помоги разобраться',
        'объясни простыми словами',
        'давай подумаем вместе',
    ],
}

_semantic_seed_embeddings_v2: dict[str, list[tuple[str, list[float]]]] | None = None
_semantic_seed_lock_v2 = asyncio.Lock()


def _get_router_engine() -> str:
    engine = os.environ.get('AUTO_ROUTE_ENGINE', _ROUTER_DEFAULT_ENGINE).strip().lower()
    return engine if engine in _ROUTER_ENGINE_VALUES else _ROUTER_DEFAULT_ENGINE


def _normalize_router_text(text: str) -> str:
    text = text.lower().replace('ё', 'е')
    text = re.sub(r'https?://\S+', ' url ', text)
    text = re.sub(r'[^0-9a-zа-я_\s]+', ' ', text, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', text).strip()


def _tokenize_router_text(text: str) -> set[str]:
    return {tok for tok in _normalize_router_text(text).split() if tok}


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    normalized = _normalize_router_text(text)
    if len(normalized) < n:
        return {normalized} if normalized else set()
    return {normalized[i : i + n] for i in range(len(normalized) - n + 1)}


def _lexical_similarity(a: str, b: str) -> float:
    a_norm = _normalize_router_text(a)
    b_norm = _normalize_router_text(b)
    if not a_norm or not b_norm:
        return 0.0

    seq = SequenceMatcher(None, a_norm, b_norm).ratio()
    toks_a = _tokenize_router_text(a_norm)
    toks_b = _tokenize_router_text(b_norm)
    union = toks_a | toks_b
    token_overlap = len(toks_a & toks_b) / len(union) if union else 0.0
    grams_a = _char_ngrams(a_norm)
    grams_b = _char_ngrams(b_norm)
    gram_union = grams_a | grams_b
    ngram_overlap = len(grams_a & grams_b) / len(gram_union) if gram_union else 0.0

    score = (0.45 * seq) + (0.30 * ngram_overlap) + (0.25 * token_overlap)
    if a_norm in b_norm or b_norm in a_norm:
        score += 0.05
    return min(score, 1.0)


def _semantic_threshold_for(category: str) -> float:
    return _SEMANTIC_ROUTE_THRESHOLDS.get(category, _SEMANTIC_DEFAULT_THRESHOLD)


def _build_router_query_text(features: RequestFeatures) -> str:
    from open_webui.env import ROUTER_CONTEXT_MAX_CHARS, ROUTER_CONTEXT_NO_MERGE_MIN_CHARS

    text = features.text.strip()
    if not features.recent_context:
        return text
    if ROUTER_CONTEXT_NO_MERGE_MIN_CHARS > 0 and len(text) >= ROUTER_CONTEXT_NO_MERGE_MIN_CHARS:
        return text
    combined = f'{features.recent_context}\nuser: {text}'.strip()
    if len(combined) <= ROUTER_CONTEXT_MAX_CHARS:
        return combined
    return combined[-ROUTER_CONTEXT_MAX_CHARS:]


def _contains_any_hint(text: str, hints: tuple[str, ...]) -> bool:
    lowered = _normalize_router_text(text)
    return any(hint in lowered for hint in hints)


def _user_requests_research_or_web_search(text: str) -> bool:
    """True when the message is about searching the web / gathering external facts, not only about the attachment."""
    if not (text and text.strip()):
        return False
    if PATTERNS['research'].search(text):
        return True
    return _contains_any_hint(text, _RESEARCH_OR_WEB_SEARCH_HINTS)


def _user_requests_image_generation(text: str) -> bool:
    """True when the last message asks to generate/edit an image (even if a file is attached in the thread)."""
    if not (text and text.strip()):
        return False
    return bool(PATTERNS['image_gen'].search(text.strip()))


def route_with_guardrails(features: RequestFeatures) -> RoutingDecision | None:
    if not features.text and not (features.has_image or features.has_audio or features.has_files):
        return RoutingDecision(
            'fallback',
            'low',
            method='guardrail',
            confidence=1.0,
            reasoning='Пустой запрос без вложений — использую общую модель',
            trace={'stage': 'guardrail', 'guardrail': 'empty_request'},
        )

    if features.has_image:
        # Do not use loose substring hints (e.g. «картин» matches «картинок» in «после картинок напиши код»).
        if PATTERNS['image_gen'].search(features.text.strip()):
            return RoutingDecision(
                'image_gen',
                'medium' if features.text_len > 60 else 'low',
                method='guardrail',
                confidence=1.0,
                reasoning='Есть изображение и явный запрос на генерацию/редактирование изображения',
                trace={'stage': 'guardrail', 'guardrail': 'image_generation_intent'},
            )
        if not _soft_image_attachment():
            return RoutingDecision(
                'vision',
                'low',
                method='guardrail',
                confidence=1.0,
                reasoning='Прикреплено изображение — сначала выбираю vision-модель',
                trace={'stage': 'guardrail', 'guardrail': 'attached_image'},
            )
        # Soft policy: картинка — контекст; фиксируем vision только при явном запросе «посмотри / опиши».
        if _vision_analysis_intent_in_text(features.text):
            return RoutingDecision(
                'vision',
                'low',
                method='guardrail',
                confidence=0.9,
                reasoning='Запрос на анализ/описание изображения — выбираю vision-модель',
                trace={'stage': 'guardrail', 'guardrail': 'vision_analysis_intent'},
            )
        return None

    if features.has_files and not features.has_audio:
        if _user_requests_research_or_web_search(features.text):
            # Do not lock to `document`; downstream LLM / regex can pick `research` (web search).
            return None
        if _user_requests_image_generation(features.text):
            # PDF/docs in thread must not override an explicit "draw / generate image" request.
            return RoutingDecision(
                'image_gen',
                'medium' if features.text_len > 60 else 'low',
                method='guardrail',
                confidence=0.95,
                reasoning='Запрос на генерацию изображения — вложенный файл не определяет сценарий текущего сообщения',
                trace={'stage': 'guardrail', 'guardrail': 'image_generation_intent_despite_file'},
            )
        return RoutingDecision(
            'document',
            'medium',
            method='guardrail',
            confidence=0.92,
            reasoning='Прикреплены файлы с текстовым содержимым — выбираю документный сценарий',
            trace={'stage': 'guardrail', 'guardrail': 'attached_file'},
        )

    if features.has_audio:
        return RoutingDecision(
            'fallback',
            'medium',
            method='guardrail',
            confidence=0.85,
            reasoning='Есть аудио/видео вложение — после транскрипции безопасно начать с общей модели',
            trace={'stage': 'guardrail', 'guardrail': 'attached_audio'},
        )

    return None


async def _init_semantic_seed_embeddings_v2(embedding_fn) -> dict[str, list[tuple[str, list[float]]]]:
    all_texts: list[str] = []
    mapping: list[tuple[str, str]] = []
    for category, examples in _SEMANTIC_ROUTE_EXAMPLES.items():
        for example in examples:
            all_texts.append(example)
            mapping.append((category, example))

    embeddings = await embedding_fn(all_texts)
    result: dict[str, list[tuple[str, list[float]]]] = {}
    for idx, (category, example) in enumerate(mapping):
        result.setdefault(category, []).append((example, embeddings[idx]))
    return result


async def _get_semantic_seed_embeddings(embedding_fn):
    global _semantic_seed_embeddings_v2

    if embedding_fn is None:
        return None
    if _semantic_seed_embeddings_v2 is None:
        async with _semantic_seed_lock_v2:
            if _semantic_seed_embeddings_v2 is None:
                try:
                    _semantic_seed_embeddings_v2 = await _init_semantic_seed_embeddings_v2(embedding_fn)
                except Exception as exc:
                    log.warning('Failed to initialize semantic route layer embeddings: %s', exc)
                    _semantic_seed_embeddings_v2 = {}
    return _semantic_seed_embeddings_v2


async def route_with_semantic_layer(
    features: RequestFeatures,
    *,
    embedding_fn=None,
) -> RoutingDecision | None:
    query_text = _build_router_query_text(features)
    if not query_text:
        return None

    best_by_category: dict[str, dict[str, Any]] = {}
    for category, examples in _SEMANTIC_ROUTE_EXAMPLES.items():
        best_example = ''
        best_score = 0.0
        for example in examples:
            score = _lexical_similarity(query_text, example)
            if score > best_score:
                best_score = score
                best_example = example
        best_by_category[category] = {
            'score': best_score,
            'example': best_example,
            'mode': 'lexical',
        }

    seed_embeddings = await _get_semantic_seed_embeddings(embedding_fn)
    if seed_embeddings:
        try:
            query_emb_result = await embedding_fn(query_text)
            query_emb = (
                query_emb_result[0]
                if isinstance(query_emb_result, list) and query_emb_result and isinstance(query_emb_result[0], list)
                else query_emb_result
            )
            for category, pairs in seed_embeddings.items():
                for example, seed_emb in pairs:
                    emb_score = _cosine_similarity(query_emb, seed_emb)
                    lexical = best_by_category[category]['score']
                    combined = max((0.72 * emb_score) + (0.28 * lexical), emb_score)
                    if combined > best_by_category[category]['score']:
                        best_by_category[category] = {
                            'score': combined,
                            'example': example,
                            'mode': 'embedding+lexical',
                            'embedding_score': emb_score,
                            'lexical_score': lexical,
                        }
        except Exception as exc:
            log.warning('Semantic route layer embedding failed, falling back to lexical scoring: %s', exc)

    ranked = sorted(
        (
            {
                'category': category,
                **data,
                'threshold': _semantic_threshold_for(category),
            }
            for category, data in best_by_category.items()
        ),
        key=lambda item: item['score'],
        reverse=True,
    )
    if not ranked:
        return None

    top = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    if top['score'] < top['threshold']:
        return None
    if runner_up is not None and (top['score'] - runner_up['score']) < _SEMANTIC_ABSTAIN_MARGIN:
        return None

    return RoutingDecision(
        category=top['category'],
        complexity=_estimate_complexity(len(query_text)),
        method='semantic',
        confidence=round(top['score'], 3),
        reasoning=(f'Семантический роутер выбрал {top["category"]}: похоже на пример «{top["example"]}»'),
        trace={
            'stage': 'semantic',
            'score': round(top['score'], 3),
            'threshold': top['threshold'],
            'matched_example': top['example'],
            'mode': top.get('mode', 'lexical'),
            'runner_up': {
                'category': runner_up['category'],
                'score': round(runner_up['score'], 3),
            }
            if runner_up is not None
            else None,
        },
    )


def route_with_safe_default(features: RequestFeatures, *, reason: str) -> RoutingDecision:
    return RoutingDecision(
        category='fallback',
        complexity='medium' if features.text_len > 120 else 'low',
        method='default',
        confidence=0.0,
        reasoning=reason,
        trace={'stage': 'default'},
    )


# =========================================================================
# Stage 1: Rule Engine
# =========================================================================


def _classify_with_rules(features: RequestFeatures) -> RoutingDecision | None:
    pattern_text = _rules_pattern_text(features)
    current = features.text.strip()

    if features.has_image and not PATTERNS['image_gen'].search(pattern_text):
        if not _soft_image_attachment():
            return RoutingDecision('vision', 'low', method='rules', reasoning='Прикреплено изображение → vision-анализ')
        if _vision_analysis_intent_in_text(current) or _vision_analysis_intent_in_text(pattern_text):
            return RoutingDecision(
                'vision', 'low', method='rules', reasoning='Явный запрос на анализ/описание изображения → vision'
            )
        # Иначе изображение только контекст — даём сработать остальным правилам / LLM.

    # Merged short-follow-up context can still contain «хочу картинку» while the current line is code.
    img_in_full = PATTERNS['image_gen'].search(pattern_text)
    img_in_current = PATTERNS['image_gen'].search(current)
    code_in_current = bool(current and (PATTERNS['code'].search(current) or PATTERNS['math_logic'].search(current)))
    if img_in_full and not img_in_current and code_in_current:
        return RoutingDecision(
            'code',
            _estimate_complexity(features.text_len),
            method='rules',
            reasoning='Текущее сообщение — код/алгоритм; совпадение image_gen только из истории диалога отклонено',
        )

    if PATTERNS['image_gen'].search(pattern_text):
        return RoutingDecision(
            'image_gen', 'low', method='rules', reasoning='Обнаружен запрос на генерацию изображения'
        )

    if PATTERNS['audio_gen'].search(pattern_text):
        return RoutingDecision(
            'audio_gen', 'low', method='rules', reasoning='Обнаружен запрос на генерацию аудио/музыки'
        )

    if features.has_code_block:
        return RoutingDecision(
            'code',
            _estimate_complexity(features.text_len),
            method='rules',
            reasoning='В сообщении есть блок кода → программирование',
        )

    if features.text_len > 10000 or PATTERNS['document'].search(pattern_text):
        return RoutingDecision(
            'document',
            'high' if features.text_len > 10000 else 'medium',
            method='rules',
            reasoning='Длинный текст или ключевые слова документа → анализ документов',
        )

    return None


# =========================================================================
# Stage 2: Semantic Router (embedding-based)
# =========================================================================

_CATEGORY_SEEDS: dict[str, list[str]] = {
    'image_gen': [
        'нарисуй картинку кота',
        'сгенерируй изображение заката',
        'создай мне красивую иллюстрацию',
        'create an illustration of a forest',
        'generate a picture of a sunset',
        'make me an image',
    ],
    'audio_gen': [
        'сгенерируй мелодию',
        'создай музыку для видео',
        'generate a song',
        'make background music',
    ],
    'code': [
        'напиши функцию на python',
        'fix this bug in my code',
        'рефакторинг класса',
        'write a unit test',
        'создай REST API endpoint',
        'помоги с ошибкой в коде',
        'пузырьковая сортировка массива',
        'реализуй bubble sort на python',
    ],
    'math_logic': [
        'реши уравнение',
        'докажи теорему',
        'solve this math problem',
        'calculate the integral',
        'вычисли производную',
    ],
    'research': [
        'сделай глубокий анализ рынка',
        'investigate this topic thoroughly',
        'подробно изучи и сравни варианты',
        'найди информацию и сделай обзор',
        'do a comprehensive research on',
    ],
    'analytics': [
        'проанализируй данные из CSV',
        'построй график по данным',
        'analyze this dataset',
        'compute statistics for',
        'сделай сводку по метрикам',
    ],
    'creative': [
        'напиши стихотворение',
        'придумай историю про',
        'write a short story',
        'сочини рассказ',
        'write a creative blog post',
    ],
    'document': [
        'проанализируй этот документ',
        'summarize the following PDF',
        'сделай резюме контракта',
        'разбери текст ниже',
        'extract key points from this document',
    ],
}

_SEMANTIC_THRESHOLD = 0.82

_seed_embeddings: dict[str, list[list[float]]] | None = None
_seed_init_lock = asyncio.Lock()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _init_seed_embeddings(embedding_fn) -> dict[str, list[list[float]]]:
    result: dict[str, list[list[float]]] = {}
    all_texts: list[str] = []
    category_spans: list[tuple[str, int, int]] = []

    for cat, seeds in _CATEGORY_SEEDS.items():
        start = len(all_texts)
        all_texts.extend(seeds)
        category_spans.append((cat, start, len(all_texts)))

    try:
        embeddings = await embedding_fn(all_texts)
        for cat, start, end in category_spans:
            result[cat] = embeddings[start:end]
    except Exception as exc:
        log.warning('Failed to compute seed embeddings: %s', exc)
        return {}

    return result


async def _classify_with_embeddings(
    text: str, embedding_fn, *, threshold: float = _SEMANTIC_THRESHOLD
) -> RoutingDecision | None:
    global _seed_embeddings

    if _seed_embeddings is None:
        async with _seed_init_lock:
            if _seed_embeddings is None:
                try:
                    _seed_embeddings = await _init_seed_embeddings(embedding_fn)
                except Exception:
                    _seed_embeddings = {}

    if not _seed_embeddings:
        return None

    try:
        query_emb_result = await embedding_fn(text)
        if isinstance(query_emb_result, list) and query_emb_result and isinstance(query_emb_result[0], list):
            query_emb = query_emb_result[0]
        else:
            query_emb = query_emb_result
    except Exception as exc:
        log.warning('Semantic routing embedding failed: %s', exc)
        return None

    best_cat = 'fallback'
    best_sim = 0.0

    for cat, seed_embs in _seed_embeddings.items():
        for seed_emb in seed_embs:
            sim = _cosine_similarity(query_emb, seed_emb)
            if sim > best_sim:
                best_sim = sim
                best_cat = cat

    if best_sim >= threshold:
        return RoutingDecision(
            category=best_cat,
            complexity=_estimate_complexity(len(text)),
            method='semantic',
            confidence=round(best_sim, 3),
            reasoning=f'Семантическая близость к «{best_cat}» (cosine={best_sim:.2f})',
        )

    return None


# =========================================================================
# Stage 3: LLM Classifier (provider-agnostic, auto-discovery)
# =========================================================================

_ROUTER_SYSTEM_PROMPT = """\
Вы — интеллектуальный маршрутизатор запросов в AI workspace (как у Perplexity: понятно объясняете пользователю ход мыслей).

Задача: выбрать ОДНУ категорию маршрутизации для текущего запроса. Учитывайте:
- последнее сообщение пользователя (главный сигнал),
- справочно — недавний диалог (follow-up, местоимения «это/там», ссылки на прошлый код),
- вложения (картинка, файлы, аудио),
- непрямые формулировки, опечатки, сленг, короткие follow-up реплики.

Приоритет контекста:
- Классифицируйте в первую очередь по блоку «Текущее сообщение (решающее)». Более ранние реплики — только справочно: уточнение местоимений, короткий follow-up, явная отсылка к прошлому («как выше»).
- Не подменяйте задачу из последнего сообщения длинными темами из истории (например старая тема не должна перебивать новый вопрос).
- Если пользователь явно назвал алгоритм, язык программирования или технологию — не заменяйте другим без явной просьбы переключиться.
- Вложение (картинка, файл) в ходе диалога — это контекст для задачи из текста; не переводите в vision/document только из-за факта вложения, если по тексту нужен код, общий ответ, генерация картинки или другое. vision — когда нужно именно «увидеть» или описать прикреплённое изображение.

Правила классификации:
1. Смотрите на намерение пользователя, а не только на ключевые слова.
2. Если сомневаетесь между узкой категорией и общим чатом — честно снизьте confidence и/или выберите fallback.
3. Приветствия и чистый small talk без задачи — обычно fallback.
4. Запрос «сделай картинку / нарисуй / сгенерируй изображение» — image_gen, если речь именно о генерации/редактировании картинки, а не о теории.

Поля ответа (важно для UI):
- understanding — 1–2 предложения: своими словами, что вы поняли из запроса (по-русски, живым языком).
- reasoning — 2–4 предложения: почему выбрана эта категория, что пользователь получит от подходящей модели; без шаблонов вроде «выбрана категория X»; можно упомянуть вложения или контекст диалога.
- Не дублируйте дословно understanding и reasoning; вместе они должны читаться как короткое объяснение для человека.

Категории:
- image_gen  : генерация или редактирование изображения / иллюстрации
- audio_gen  : генерация музыки / звука / аудио
- vision     : анализ или описание прикреплённого изображения
- code       : программирование, отладка, API, тесты, рефакторинг
- math_logic : математика, вычисления, логика, алгоритмы
- research   : исследование, обзор, сравнение, сбор фактов из сети/источников
- analytics  : данные, таблицы, CSV, метрики, графики
- creative   : маркетинговый или творческий текст, идеи
- document   : документы и файлы, summary, extract, review
- fallback   : общий разговор, простые вопросы без узкой модальности

Сложность: low | medium | high

Ответь ТОЛЬКО одним JSON-объектом:
{"category":"...","complexity":"...","confidence":0.0-1.0,"understanding":"...","reasoning":"..."}\
"""

_LLM_CONFIDENCE_THRESHOLD = 0.7

# Circuit breaker: after N consecutive LLM classifier failures, skip LLM for a cooldown period.
_LLM_CB_FAILURE_THRESHOLD = 3
_LLM_CB_COOLDOWN_S = 300  # 5 minutes
_llm_cb_consecutive_failures = 0
_llm_cb_open_until: float = 0.0

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(4.0, connect=1.5),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _http_client


def _get_classifier_config(request=None, registry: list[ModelMeta] | None = None) -> tuple[str, str, str] | None:
    model = os.environ.get('ROUTER_MODEL')
    base_url = os.environ.get('ROUTER_API_BASE_URL')
    api_key = os.environ.get('ROUTER_API_KEY')
    if model and base_url and api_key:
        return model, base_url, api_key

    if request and registry:
        router_model = get_router_model(registry)
        if router_model:
            try:
                idx = router_model.provider_idx
                base_url = request.app.state.config.OPENAI_API_BASE_URLS[idx]
                api_key = request.app.state.config.OPENAI_API_KEYS[idx]
                return router_model.id, base_url, api_key
            except (AttributeError, IndexError):
                pass

    reka_key = os.environ.get('REKA_API_KEY') or os.environ.get('ROUTERAI_API_KEY')
    if reka_key:
        return (
            os.environ.get('REKA_ROUTER_MODEL', 'rekaai/reka-edge'),
            os.environ.get('REKA_API_URL', 'https://api.reka.ai/v1'),
            reka_key,
        )

    if request:
        try:
            base_url = request.app.state.config.OPENAI_API_BASE_URLS[0]
            api_key = request.app.state.config.OPENAI_API_KEYS[0]
            if base_url and api_key and registry:
                cheap = get_router_model(registry)
                model_id = cheap.id if cheap else (registry[0].id if registry else None)
                if model_id:
                    return model_id, base_url, api_key
        except (AttributeError, IndexError):
            pass

    return None


def _llm_circuit_breaker_open() -> bool:
    global _llm_cb_open_until
    if _llm_cb_open_until <= 0:
        return False
    if time.monotonic() >= _llm_cb_open_until:
        _llm_cb_open_until = 0.0
        return False
    return True


def _llm_record_success() -> None:
    global _llm_cb_consecutive_failures, _llm_cb_open_until
    _llm_cb_consecutive_failures = 0
    _llm_cb_open_until = 0.0


def _llm_record_failure() -> None:
    global _llm_cb_consecutive_failures, _llm_cb_open_until
    _llm_cb_consecutive_failures += 1
    if _llm_cb_consecutive_failures >= _LLM_CB_FAILURE_THRESHOLD:
        _llm_cb_open_until = time.monotonic() + _LLM_CB_COOLDOWN_S
        log.warning(
            'LLM classifier circuit breaker OPEN after %d failures (cooldown %ds)',
            _llm_cb_consecutive_failures,
            _LLM_CB_COOLDOWN_S,
        )


async def _classify_with_llm(
    features: RequestFeatures,
    request=None,
    registry: list[ModelMeta] | None = None,
) -> RoutingDecision | None:
    from open_webui.env import ROUTER_MAX_TOKENS, ROUTER_TEMPERATURE

    if _llm_circuit_breaker_open():
        log.debug('LLM classifier circuit breaker is open; skipping.')
        return None

    config = _get_classifier_config(request, registry)
    if not config:
        log.debug('No LLM classifier config available; skipping Stage 5.')
        return None

    model, base_url, api_key = config

    context_parts: list[str] = []
    if features.text:
        context_parts.append('Текущее сообщение (решающее):\n' + features.text[:2000])
    if features.has_image:
        context_parts.append('[User attached an image]')
    if features.has_audio:
        context_parts.append('[User attached audio]')
    if features.has_files:
        context_parts.append('[User attached files]')
    if features.has_url:
        context_parts.append('[Message contains URL]')
    if features.recent_context:
        context_parts.append(
            'Справочно: предыдущие реплики (не подменяют задачу последнего сообщения):\n'
            + features.recent_context[:2500]
        )
    user_message = '\n\n'.join(context_parts) or '(empty message)'

    body: dict[str, Any] = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': _ROUTER_SYSTEM_PROMPT},
            {'role': 'user', 'content': user_message},
        ],
        'max_tokens': ROUTER_MAX_TOKENS,
        'temperature': ROUTER_TEMPERATURE,
    }
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    client = _get_http_client()
    raw = ''

    for attempt in range(2):
        try:
            resp = await client.post(f'{base_url}/chat/completions', headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

            raw = data['choices'][0]['message']['content'].strip()
            match = re.search(r'(\{.*\})', raw, re.DOTALL)
            if match:
                raw = match.group(1)

            result = json.loads(raw)
            category = result.get('category', 'fallback')
            complexity = result.get('complexity', 'medium')
            confidence = float(result.get('confidence', 0.5))
            understanding = str(result.get('understanding', '') or '').strip()
            reasoning = str(result.get('reasoning', '') or '').strip()

            if category not in VALID_CATEGORIES:
                log.warning('LLM returned unknown category %r, defaulting to fallback', category)
                category = 'fallback'
            if complexity not in VALID_COMPLEXITIES:
                complexity = 'medium'
            if understanding and reasoning:
                reasoning = f'{understanding}\n\n{reasoning}'
            elif understanding:
                reasoning = understanding
            if not reasoning:
                reasoning = f'Маршрут: {category} (confidence {confidence:.2f}).'

            _llm_record_success()
            return RoutingDecision(
                category=category,
                complexity=complexity,
                method='llm_adjudicator',
                confidence=confidence,
                reasoning=reasoning,
                trace={
                    'stage': 'llm',
                    'confidence': confidence,
                    'llm_category': category,
                    'llm_complexity': complexity,
                    'has_understanding': bool(understanding),
                },
            )

        except httpx.TimeoutException:
            if attempt == 0:
                log.warning('LLM classifier timeout (attempt 1), retrying...')
                continue
            log.warning('LLM classifier timed out after retry')
            _llm_record_failure()
            return None
        except Exception as exc:
            log.warning('LLM routing failed (%s). Raw: %s', exc, raw or 'N/A')
            _llm_record_failure()
            return None

    _llm_record_failure()
    return None


# =========================================================================
# Stage 4: Regex Safety Net
# =========================================================================


def _classify_with_regex(text: str, has_image: bool, has_url: bool = False) -> RoutingDecision:
    if PATTERNS['image_gen'].search(text):
        cat = 'image_gen'
    elif PATTERNS['audio_gen'].search(text):
        cat = 'audio_gen'
    elif has_image and (not _soft_image_attachment() or _vision_analysis_intent_in_text(text)):
        cat = 'vision'
    elif len(text) > 10000 or PATTERNS['document'].search(text):
        cat = 'document'
    elif PATTERNS['code'].search(text):
        cat = 'code'
    elif PATTERNS['math_logic'].search(text):
        cat = 'math_logic'
    elif PATTERNS['research'].search(text):
        cat = 'research'
    elif PATTERNS['analytics'].search(text):
        cat = 'analytics'
    elif PATTERNS['creative'].search(text):
        cat = 'creative'
    elif has_url and re.search(r'(?i)(анализ|разбер|обзор|изуч|резюме|summarize|analyze|review|research)', text):
        cat = 'research'
    else:
        cat = 'fallback'

    reasoning = f'Regex-классификация: {cat}' if cat != 'fallback' else 'Нет явных сигналов — общая модель'
    return RoutingDecision(
        category=cat,
        complexity=_estimate_complexity(len(text)),
        method='regex_fallback',
        reasoning=reasoning,
    )


def _classify_with_regex_from_features(features: RequestFeatures) -> RoutingDecision:
    t = _rules_pattern_text(features)
    return _classify_with_regex(t, features.has_image, features.has_url)


def _should_regex_override_llm(
    features: RequestFeatures,
    llm_decision: RoutingDecision,
    regex_decision: RoutingDecision,
) -> bool:
    if regex_decision.category == 'fallback' or regex_decision.category == llm_decision.category:
        return False
    if regex_decision.category in _PRECISE_REGEX_OVERRIDE_CATEGORIES:
        return True
    if regex_decision.category == 'code' and features.has_code_block:
        return True
    if regex_decision.category == 'research' and features.has_url:
        return True
    # LLM sometimes picks image_gen when the user asks for code after a turn about pictures.
    if (
        regex_decision.category == 'code'
        and llm_decision.category in ('image_gen', 'vision')
        and features.text.strip()
        and (PATTERNS['code'].search(features.text.strip()) or PATTERNS['math_logic'].search(features.text.strip()))
    ):
        return True
    return False


# =========================================================================
# Scored Model Selection
# =========================================================================

_CATEGORY_TO_KIND: dict[str, str] = {
    'image_gen': 'image_gen',
    'audio_gen': 'audio_gen',
    'vision': 'vlm',
    'code': 'code',
}

_COMPLEXITY_TO_TIER: dict[str, str] = {
    'low': 'cheap',
    'medium': 'mid',
    'high': 'premium',
}

_NON_ROUTABLE_KINDS = frozenset({'embedding', 'stt'})
_MEDIA_GENERATION_KINDS = frozenset({'image_gen', 'audio_gen'})

# Lightweight benchmark-aware boost layer (especially useful for MWS catalogs where
# both strong and lightweight variants coexist under similar naming patterns).
_MODEL_BENCHMARK_BOOSTS: dict[str, dict[str, int]] = {
    'qwen2.5-72b-instruct': {
        'fallback': 8,
        'research': 9,
        'math_logic': 8,
        'analytics': 8,
        'document': 7,
        'creative': 6,
        'code': 5,
    },
    'deepseek-r1-distill-qwen-32b': {
        'fallback': 6,
        'research': 8,
        'math_logic': 9,
        'analytics': 7,
        'code': 8,
    },
    'mws-gpt-alpha': {
        'fallback': 7,
        'research': 6,
        'creative': 6,
        'document': 5,
    },
    'qwq-32b': {
        'fallback': 5,
        'research': 7,
        'math_logic': 8,
        'code': 6,
    },
    'cotype-pro-vl-32b': {
        'vision': 10,
        'fallback': 3,
    },
    'qwen3-vl-30b-a3b-instruct': {
        'vision': 9,
        'research': 4,
        'fallback': 3,
    },
    'gemma-3-27b-it': {
        'fallback': 5,
        'creative': 6,
        'document': 4,
    },
    'gpt-oss-20b': {
        'fallback': 4,
        'code': 5,
    },
}

_LOW_CAPACITY_PENALTY_KW = ('llama-3.1-8b', '-8b-instruct', 'mini', 'small', 'flash', 'lite', 'lightning')


def _is_generative_media_model(meta: ModelMeta) -> bool:
    """
    True for image/audio *generation* endpoints (Flux, Lyria, etc.).

    Catalog entries sometimes use kind=text while id/name still contains lyria/flux;
    rely on _infer_kind(search_text) so these never enter fallback/vision/code routes.
    """
    if meta.kind in _MEDIA_GENERATION_KINDS:
        return True
    return _infer_kind(meta.search_text) in _MEDIA_GENERATION_KINDS


def _exclude_generative_media_for_category(category: str, meta: ModelMeta) -> bool:
    """Whether to skip this model when building candidates for the given route."""
    if category in _MEDIA_GENERATION_KINDS:
        return False
    return _is_generative_media_model(meta)


def _media_preferred_tier_for_scoring(complexity: str, category: str) -> str:
    """
    For image/audio generation, do not map a «short prompt» (complexity low) to preferred tier
    `cheap` — that makes fast/light endpoints win over stronger models in the catalog.
    """
    if category not in _MEDIA_GENERATION_KINDS:
        return _COMPLEXITY_TO_TIER.get(complexity, 'mid')
    base = _COMPLEXITY_TO_TIER.get(complexity, 'mid')
    if base == 'cheap':
        return 'mid'
    if complexity == 'high':
        return 'premium'
    return base


def _media_endpoint_quality_bonus(search_text: str, category: str) -> int:
    """Extra score so flagship image endpoints beat fast variants when ids differ only subtly."""
    if category != 'image_gen':
        return 0
    st = search_text.lower()
    bonus = 0
    if any(k in st for k in ('gpt-image', 'gpt-5-image', 'dall-e-3', 'dalle-3', 'imagen-3', 'imagen3')):
        bonus += 14
    elif any(k in st for k in ('flux-pro', 'flux.1', 'flux-2', 'flux2', 'flux/dev', 'qwen-image')):
        bonus += 10
    elif any(k in st for k in ('dall-e', 'imagen', 'flux', 'sdxl', 'sd3', 'z-image')):
        bonus += 4
    if any(k in st for k in ('schnell', 'turbo', 'lightning', 'fast', 'mini', 'nano', 'flash', 'lite')):
        bonus -= 12
    return bonus


def _tier_score_for_complexity(complexity: str, model_tier: str, preferred_tier: str) -> int:
    if model_tier == preferred_tier:
        return {'low': 3, 'medium': 5, 'high': 7}.get(complexity, 5)
    if complexity == 'low' and model_tier == 'mid':
        # For "simple" requests we still often want stronger chat quality.
        return 2
    if complexity == 'high' and model_tier == 'mid':
        return 1
    return 0


def _marker_matches(marker: str, search_text: str) -> bool:
    """Word-boundary-aware marker match to avoid substring collisions (e.g. 'gpt' in 'gpt-oss-20b')."""
    padded = f' {search_text} '
    return f' {marker} ' in padded or f' {marker}-' in padded or f'-{marker} ' in padded or search_text == marker


def _benchmark_score_for_model(meta: ModelMeta, category: str, complexity: str = 'medium') -> int:
    score = 0
    for marker, boosts in _MODEL_BENCHMARK_BOOSTS.items():
        if _marker_matches(marker, meta.search_text):
            score += boosts.get(category, boosts.get('fallback', 0))
    if category not in _MEDIA_GENERATION_KINDS:
        if complexity != 'low' and any(kw in meta.search_text for kw in _LOW_CAPACITY_PENALTY_KW):
            score -= 4
    return score


def _filter_failover_candidates_for_category(
    category: str, ordered_ids: list[str], registry: list[ModelMeta]
) -> list[str]:
    """
    Avoid failing over from a text task into image/audio generation models (and vice versa).
    """
    if not registry:
        return ordered_ids
    by_id = {m.id: m for m in registry}
    out: list[str] = []
    for mid in ordered_ids:
        meta = by_id.get(mid)
        if meta is None:
            out.append(mid)
            continue
        if category in _MEDIA_GENERATION_KINDS:
            inferred_kind = _infer_kind(meta.search_text)
            if meta.kind != category and inferred_kind != category:
                continue
            out.append(mid)
            continue
        if _exclude_generative_media_for_category(category, meta):
            continue
        out.append(mid)
    return out


def _collect_scored_model_pairs(category: str, complexity: str, registry: list[ModelMeta]) -> list[tuple[int, str]]:
    preferred_kind = _CATEGORY_TO_KIND.get(category, 'text')
    preferred_tier = _media_preferred_tier_for_scoring(complexity, category)
    keywords = ROUTE_MODEL_PREFERENCES.get(category, ())

    candidates: list[tuple[int, str]] = []
    for model in registry:
        if model.kind in _NON_ROUTABLE_KINDS or model.id == 'auto':
            continue
        if _exclude_generative_media_for_category(category, model):
            continue
        # For media generation categories, only score models of the matching kind
        if preferred_kind in _MEDIA_GENERATION_KINDS and model.kind != preferred_kind:
            continue
        score = 0
        if model.kind == preferred_kind:
            score += 10
        elif preferred_kind == 'text' and model.kind == 'vlm':
            score += 4
        elif preferred_kind == 'text' and model.kind == 'code':
            score += 2
        score += _tier_score_for_complexity(complexity, model.tier, preferred_tier)
        score += _benchmark_score_for_model(model, category, complexity)
        score += _media_endpoint_quality_bonus(model.search_text, category)
        for idx, kw in enumerate(keywords):
            if kw in model.search_text:
                score += len(keywords) - idx
        if score >= -2:
            candidates.append((score, model.id))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates


def select_model_candidates(category: str, complexity: str, registry: list[ModelMeta], *, limit: int = 8) -> list[str]:
    """
    Ranked unique model IDs for auto-route failover (same scoring as select_model, plus legacy fallbacks).

    For vision / image_gen / audio_gen we append **every** catalog model of that kind after the scored
    slice so auto-route can failover across providers until AUTO_ROUTE_FAILOVER_MAX attempts.
    """
    if limit < 1:
        return []

    scored = _collect_scored_model_pairs(category, complexity, registry)
    seen: set[str] = set()
    out: list[str] = []
    for _, mid in scored:
        if mid not in seen:
            seen.add(mid)
            out.append(mid)
            if len(out) >= limit:
                return out

    modality_kind: str | None = _CATEGORY_TO_KIND.get(category)
    if modality_kind in ('vlm', 'image_gen', 'audio_gen'):
        for model in registry:
            if model.kind != modality_kind or model.id == 'auto':
                continue
            if model.id not in seen:
                seen.add(model.id)
                out.append(model.id)
                if len(out) >= limit:
                    return out
        if modality_kind in ('image_gen', 'audio_gen'):
            return out[:limit]

    for model in registry:
        if _exclude_generative_media_for_category(category, model):
            continue
        if model.kind == 'text' and model.tier in ('mid', 'cheap') and model.id != 'auto':
            if model.id not in seen:
                seen.add(model.id)
                out.append(model.id)
                if len(out) >= limit:
                    return out
    for model in registry:
        if _exclude_generative_media_for_category(category, model):
            continue
        if model.kind in ('text', 'vlm', 'code') and model.id != 'auto':
            if model.id not in seen:
                seen.add(model.id)
                out.append(model.id)
                if len(out) >= limit:
                    return out
    return out[:limit]


def select_model(category: str, complexity: str, registry: list[ModelMeta]) -> tuple[str | None, bool]:
    candidates = _collect_scored_model_pairs(category, complexity, registry)

    if candidates:
        return candidates[0][1], False

    # Fallback: prefer a capable text/vlm model, avoid media-generation models
    for model in registry:
        if _exclude_generative_media_for_category(category, model):
            continue
        if model.kind == 'text' and model.tier in ('mid', 'cheap') and model.id != 'auto':
            return model.id, True
    for model in registry:
        if _exclude_generative_media_for_category(category, model):
            continue
        if model.kind in ('text', 'vlm', 'code') and model.id != 'auto':
            return model.id, True
    return None, True


# Legacy compat
def resolve_model_for_route(route: str, available_models: Any) -> tuple[str | None, bool]:
    registry = build_model_registry(available_models)
    return select_model(route, 'medium', registry)


# =========================================================================
# Orchestrator (4-stage pipeline)
# =========================================================================


async def _get_auto_routed_route_legacy(
    payload: dict[str, Any],
    request=None,
    registry: list[ModelMeta] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RoutingDecision:
    """
    Rebalanced pipeline:
      1. Feature extraction
      2. Trivial short-circuit (greetings only)
      3. Hard guardrails (image attachment, explicit gen keywords)
      4. Soft cache (confidence-gated: hit with conf >= 0.8 is final, else re-check)
      5. Semantic embeddings
      6. LLM classifier
      7. Regex safety net
    """
    t0 = time.monotonic()
    features = extract_features(payload)

    key = build_routing_cache_key(features, metadata)

    def _finalize(decision: RoutingDecision) -> RoutingDecision:
        decision.latency_ms = int((time.monotonic() - t0) * 1000)
        if key is not None:
            _routing_cache.put(key, decision)
        return decision

    # --- Stage 1: Trivial short-circuit ---
    if _should_trivial_short_circuit(features):
        d = RoutingDecision(
            'fallback',
            'low',
            method='trivial_short_circuit',
            reasoning='Короткое приветствие / подтверждение — общая модель',
        )
        return _finalize(d)

    # --- Stage 2: Hard guardrails (always before cache) ---
    decision = _classify_with_rules(features)
    if decision:
        return _finalize(decision)

    # --- Stage 3: Soft cache ---
    if key is not None:
        cached = _routing_cache.get(key)
        if cached is not None and cached.confidence >= _CACHE_SOFT_CONFIDENCE_THRESHOLD:
            cached.cache_hit = True
            cached.reasoning = f'Кеш (conf={cached.confidence:.2f}, метод={cached.method})'
            cached.latency_ms = int((time.monotonic() - t0) * 1000)
            return cached

    # --- Stage 4: Semantic embeddings ---
    embedding_fn = None
    if request:
        embedding_fn = getattr(getattr(request, 'app', None), 'state', None)
        embedding_fn = getattr(embedding_fn, 'EMBEDDING_FUNCTION', None)

    if embedding_fn is not None:
        sem_text = _semantic_query_text(features)
        decision = await _classify_with_embeddings(sem_text, embedding_fn)
        if decision:
            return _finalize(decision)

    # --- Stage 5: LLM classifier ---
    llm_decision = await _classify_with_llm(features, request=request, registry=registry)
    if llm_decision and llm_decision.confidence >= _LLM_CONFIDENCE_THRESHOLD:
        return _finalize(llm_decision)

    if llm_decision and llm_decision.confidence > 0:
        regex_decision = _classify_with_regex_from_features(features)
        if _should_regex_override_llm(features, llm_decision, regex_decision):
            log.info(
                'Low LLM confidence (%.2f), regex override: %s -> %s',
                llm_decision.confidence,
                llm_decision.category,
                regex_decision.category,
            )
            regex_decision.method = 'llm+regex_override'
            regex_decision.confidence = llm_decision.confidence
            regex_decision.reasoning = (
                f'LLM дал {llm_decision.category} (conf={llm_decision.confidence:.2f}), '
                f'regex уточнил до {regex_decision.category}'
            )
            return _finalize(regex_decision)
        llm_decision.method = 'llm_low_conf'
        return _finalize(llm_decision)

    # --- Stage 6: Regex safety net ---
    decision = _classify_with_regex_from_features(features)
    return _finalize(decision)


# =========================================================================
# Enterprise orchestrator
# =========================================================================


def _maybe_get_embedding_fn(request):
    if request is None:
        return None
    app_state = getattr(getattr(request, 'app', None), 'state', None)
    return getattr(app_state, 'EMBEDDING_FUNCTION', None)


async def _get_auto_routed_route_enterprise(
    payload: dict[str, Any],
    request=None,
    registry: list[ModelMeta] | None = None,
    metadata: dict[str, Any] | None = None,
    *,
    allow_llm: bool = True,
) -> RoutingDecision:
    t0 = time.monotonic()
    features = extract_features(payload)
    key = build_routing_cache_key(features, metadata)
    embedding_fn = _maybe_get_embedding_fn(request)

    def _finalize(decision: RoutingDecision) -> RoutingDecision:
        decision.latency_ms = int((time.monotonic() - t0) * 1000)
        decision.trace.setdefault('engine', 'enterprise')
        decision.trace.setdefault('stage', decision.method or 'unknown')
        if key is not None and decision.method not in {'guardrail'}:
            _routing_cache.put(key, decision)
        return decision

    guardrail_decision = route_with_guardrails(features)
    if guardrail_decision is not None:
        return _finalize(guardrail_decision)

    # --- Primary: LLM adjudicator (reasoning always from the router model when it responds) ---
    if allow_llm:
        llm_decision = await _classify_with_llm(features, request=request, registry=registry)
        if llm_decision is not None:
            if llm_decision.confidence >= _LLM_CONFIDENCE_THRESHOLD:
                # Same as low-confidence path: explicit rules / regex must win over a confident but
                # wrong LLM (e.g. "создай картинку" → LLM fallback → text model refuses image API).
                rules_decision = _classify_with_rules(features)
                if rules_decision is not None and _should_regex_override_llm(features, llm_decision, rules_decision):
                    rules_decision.method = 'llm+regex_override'
                    rules_decision.confidence = llm_decision.confidence
                    rules_decision.reasoning = (
                        f'LLM ({llm_decision.confidence:.2f}): {llm_decision.category} — '
                        f'явные правила → {rules_decision.category}. {rules_decision.reasoning}'
                    )
                    rules_decision.trace.setdefault('stage', 'llm+rules_override')
                    return _finalize(rules_decision)
                regex_decision_hi = _classify_with_regex_from_features(features)
                if _should_regex_override_llm(features, llm_decision, regex_decision_hi):
                    regex_decision_hi.method = 'llm+regex_override'
                    regex_decision_hi.confidence = llm_decision.confidence
                    regex_decision_hi.reasoning = (
                        f'LLM ({llm_decision.confidence:.2f}): {llm_decision.reasoning} '
                        f'→ regex уточнил категорию до {regex_decision_hi.category}'
                    )
                    regex_decision_hi.trace.setdefault('stage', 'llm+regex_override')
                    return _finalize(regex_decision_hi)
                return _finalize(llm_decision)
            rules_low = _classify_with_rules(features)
            if rules_low is not None and _should_regex_override_llm(features, llm_decision, rules_low):
                rules_low.method = 'llm+regex_override'
                rules_low.confidence = llm_decision.confidence
                rules_low.reasoning = (
                    f'LLM ({llm_decision.confidence:.2f}): {llm_decision.category} — '
                    f'явные правила → {rules_low.category}. {rules_low.reasoning}'
                )
                rules_low.trace.setdefault('stage', 'llm+rules_override')
                return _finalize(rules_low)
            regex_decision = _classify_with_regex_from_features(features)
            if _should_regex_override_llm(features, llm_decision, regex_decision):
                regex_decision.method = 'llm+regex_override'
                regex_decision.confidence = llm_decision.confidence
                regex_decision.reasoning = (
                    f'LLM ({llm_decision.confidence:.2f}): {llm_decision.reasoning} '
                    f'→ regex уточнил категорию до {regex_decision.category}'
                )
                regex_decision.trace.setdefault('stage', 'llm+regex_override')
                return _finalize(regex_decision)
            llm_decision.method = 'llm_adjudicator_low_conf'
            llm_decision.trace.setdefault('stage', 'llm')
            llm_decision.trace['below_threshold'] = True
            return _finalize(llm_decision)

    if key is not None:
        cached = _routing_cache.get(key)
        if cached is not None and cached.confidence >= _CACHE_SOFT_CONFIDENCE_THRESHOLD:
            cached.cache_hit = True
            cached.reasoning = f'Кеш маршрутизации: {cached.reasoning}'
            cached.trace.setdefault('stage', 'cache')
            cached.trace['cache_hit'] = True
            return _finalize(cached)

    if _is_smalltalk_followup_turn(features):
        return _finalize(
            RoutingDecision(
                category='fallback',
                complexity='low',
                method='smalltalk_followup',
                confidence=1.0,
                reasoning='Короткий small talk в диалоге — общая модель (LLM недоступен)',
                trace={'stage': 'smalltalk_followup'},
            )
        )

    semantic_decision = await route_with_semantic_layer(features, embedding_fn=embedding_fn)
    if semantic_decision is not None:
        # Embedding layer can pick image_gen when history mentions pictures; explicit rules may say code.
        explicit_after_semantic = _classify_with_rules(features)
        if (
            explicit_after_semantic is not None
            and explicit_after_semantic.category == 'code'
            and semantic_decision.category in ('image_gen', 'vision')
        ):
            explicit_after_semantic.method = 'rules'
            explicit_after_semantic.reasoning = (
                f'Semantic дал {semantic_decision.category}; переопределение: {explicit_after_semantic.reasoning}'
            )
            explicit_after_semantic.trace.setdefault('stage', 'semantic_then_rules')
            return _finalize(explicit_after_semantic)
        return _finalize(semantic_decision)

    explicit_rule_decision = _classify_with_rules(features)
    if explicit_rule_decision is not None:
        return _finalize(explicit_rule_decision)

    return _finalize(_classify_with_regex_from_features(features))


def _log_shadow_router_decision(
    legacy_decision: RoutingDecision,
    enterprise_decision: RoutingDecision,
    *,
    features: RequestFeatures,
) -> None:
    if (
        legacy_decision.category == enterprise_decision.category
        and legacy_decision.complexity == enterprise_decision.complexity
        and legacy_decision.method == enterprise_decision.method
    ):
        return
    log.info(
        'routing_shadow_diff text=%r legacy=%s/%s/%s enterprise=%s/%s/%s',
        features.text[:160],
        legacy_decision.category,
        legacy_decision.complexity,
        legacy_decision.method,
        enterprise_decision.category,
        enterprise_decision.complexity,
        enterprise_decision.method,
    )


async def get_auto_routed_route(
    payload: dict[str, Any],
    request=None,
    registry: list[ModelMeta] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RoutingDecision:
    engine = _get_router_engine()

    if engine == 'legacy':
        decision = await _get_auto_routed_route_legacy(payload, request=request, registry=registry, metadata=metadata)
        decision.trace.setdefault('engine', 'legacy')
        return decision

    enterprise_decision = await _get_auto_routed_route_enterprise(
        payload,
        request=request,
        registry=registry,
        metadata=metadata,
        allow_llm=engine != 'semantic',
    )

    if engine in {'hybrid', 'semantic'}:
        return enterprise_decision

    legacy_decision = await _get_auto_routed_route_legacy(
        payload, request=request, registry=registry, metadata=metadata
    )
    legacy_decision.trace.setdefault('engine', 'legacy')
    _log_shadow_router_decision(legacy_decision, enterprise_decision, features=extract_features(payload))
    return legacy_decision


# =========================================================================
# Public API
# =========================================================================


def evaluate_route_deterministic(payload: dict[str, Any]) -> RoutingDecision:
    """
    Enterprise deterministic evaluation path:
      1. guardrails
      2. semantic route layer using lexical similarity only
      3. safe fallback

    Used for offline evaluation and threshold calibration without live model calls.
    """
    features = extract_features(payload)
    decision = route_with_guardrails(features)
    if decision is not None:
        decision.trace.setdefault('engine', 'enterprise')
        return decision

    query_text = _build_router_query_text(features)
    if query_text:
        best_by_category: list[tuple[float, str, str]] = []
        for category, examples in _SEMANTIC_ROUTE_EXAMPLES.items():
            best_example = ''
            best_score = 0.0
            for example in examples:
                score = _lexical_similarity(query_text, example)
                if score > best_score:
                    best_score = score
                    best_example = example
            best_by_category.append((best_score, category, best_example))
        best_by_category.sort(reverse=True)
        if best_by_category:
            top_score, top_category, top_example = best_by_category[0]
            runner_score = best_by_category[1][0] if len(best_by_category) > 1 else 0.0
            threshold = _semantic_threshold_for(top_category)
            if top_score >= threshold and (top_score - runner_score) >= _SEMANTIC_ABSTAIN_MARGIN:
                return RoutingDecision(
                    top_category,
                    _estimate_complexity(len(query_text)),
                    method='semantic',
                    confidence=round(top_score, 3),
                    reasoning=f'Лексическая route-layer близость к «{top_example}»',
                    trace={
                        'engine': 'enterprise',
                        'stage': 'semantic',
                        'score': round(top_score, 3),
                        'threshold': threshold,
                        'matched_example': top_example,
                    },
                )

    return route_with_safe_default(
        features,
        reason='Детерминированная оценка: guardrails и semantic route layer не дали уверенного маршрута',
    )


async def process_auto_routing(
    request,
    payload: dict[str, Any],
    user,
    available_models: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Main entry point for auto-routing. Resolves intent into a specific model ID
    available in the current instance's model catalog.
    """
    from open_webui.models.files import Files
    from open_webui.routers.audio import transcribe
    from open_webui.storage.provider import Storage
    from open_webui.utils.files import get_image_base64_from_file_id

    if available_models is None:
        available_models = getattr(getattr(request, 'app', None), 'state', None)
        available_models = getattr(available_models, 'OPENAI_MODELS', None)

    registry = build_model_registry(available_models) if available_models else []

    messages = payload.get('messages', [])
    if not messages:
        from open_webui.env import AUTO_ROUTE_FAILOVER_MAX

        cands = select_model_candidates('fallback', 'low', registry, limit=AUTO_ROUTE_FAILOVER_MAX) if registry else []
        if not cands:
            mid = 'fallback'
            cands = ['fallback']
        else:
            mid = cands[0]
            cands = _filter_failover_candidates_for_category('fallback', list(cands), registry)
            if not cands:
                cands = [mid]
        return mid, payload, RoutingDecision('fallback', 'low', method='empty', failover_candidates=tuple(cands))

    # Index of the latest user turn — request-level metadata.files must apply only here.
    # Otherwise every historical user message inherits the same attachments and we inject
    # image_url into the last text-only message (e.g. "Привет"), forcing vision routing.
    last_user_msg_index: int | None = None
    for idx in range(len(messages) - 1, -1, -1):
        if messages[idx].get('role') == 'user':
            last_user_msg_index = idx
            break

    has_vision = False
    for i, msg in enumerate(messages):
        if msg.get('role') != 'user':
            continue
        files = list(msg.get('files', []))
        if last_user_msg_index is not None and i == last_user_msg_index and isinstance(payload.get('metadata'), dict):
            files.extend(payload['metadata'].get('files', []))

        file_ids = [f.get('id') or f.get('file_id') for f in files if isinstance(f, dict)]
        content = msg.get('content', '')
        if isinstance(content, list):
            for part in content:
                if part.get('type') == 'file' and 'file_id' in part:
                    file_ids.append(part['file_id'])
        file_ids = list({file_id for file_id in file_ids if file_id})

        if not file_ids:
            continue

        if isinstance(content, str):
            msg['content'] = [{'type': 'text', 'text': content}]
            content = msg['content']

        for file_id in file_ids:
            file_item = Files.get_file_by_id(file_id)
            if not file_item:
                continue
            content_type = file_item.meta.get('content_type', '')
            if content_type.startswith('image/'):
                b64 = get_image_base64_from_file_id(file_id)
                if b64:
                    if i == last_user_msg_index:
                        has_vision = True
                    content.append({'type': 'image_url', 'image_url': {'url': f'data:{content_type};base64,{b64}'}})
            elif content_type.startswith('audio/') or content_type.startswith('video/'):
                cached_text = file_item.data.get('content', '') if file_item.data else ''
                if cached_text:
                    content.append({'type': 'text', 'text': f'\n[Audio Transcription: {cached_text}]\n'})
                else:
                    try:
                        file_path = Storage.get_file(file_item.path)
                        res = transcribe(request, file_path, None, user)
                        transcription_text = res.get('text', '')
                        if transcription_text:
                            file_data = file_item.data or {}
                            file_data['content'] = transcription_text
                            Files.update_file_data_by_id(file_id, file_data)
                            content.append({'type': 'text', 'text': f'\n[Audio Transcription: {transcription_text}]\n'})
                    except Exception as e:
                        log.error('Error transcribing auto-routing audio %s: %s', file_id, e)
            else:
                text_content = file_item.data.get('content', '') if file_item.data else ''
                if text_content:
                    content.append(
                        {'type': 'text', 'text': f'\n[File Content ({file_item.filename}):\n{text_content}]\n'}
                    )

    # --- Frontend task_mode override (user explicitly selected a mode from the UI pill bar) ---
    _TASK_MODE_TO_CATEGORY = {
        'code': 'code',
        'research': 'research',
        'vision': 'vision',
        'chat': 'fallback',
    }
    task_mode = payload.get('task_mode') or (metadata.get('task_mode') if isinstance(metadata, dict) else None)
    if task_mode and task_mode in _TASK_MODE_TO_CATEGORY:
        forced_category = _TASK_MODE_TO_CATEGORY[task_mode]
        features = extract_features(payload)
        decision = RoutingDecision(
            category=forced_category,
            complexity=_estimate_complexity(features.text_len),
            method='user_mode_override',
            confidence=1.0,
            reasoning=f'Пользователь выбрал режим «{task_mode}» — маршрутизация зафиксирована',
            trace={'stage': 'user_mode_override', 'engine': 'enterprise', 'task_mode': task_mode},
        )
    else:
        decision = await get_auto_routed_route(payload, request=request, registry=registry, metadata=metadata)

    if has_vision and decision.category != 'image_gen':
        if not _soft_image_attachment():
            decision.category = 'vision'
            decision.trace.setdefault('vision_attachment_policy', 'legacy_force_vlm')
        elif decision.category == 'fallback':
            decision.category = 'vision'
            decision.trace.setdefault('vision_attachment_policy', 'soft_upgrade_fallback_only')
        else:
            decision.trace.setdefault('vision_attachment_policy', 'soft_respect_route')

    from open_webui.env import AUTO_ROUTE_FAILOVER_MAX

    model_id, used_fallback = select_model(decision.category, decision.complexity, registry)
    if not model_id:
        raise ValueError(f'Could not resolve model for route {decision.category}')

    cands = select_model_candidates(decision.category, decision.complexity, registry, limit=AUTO_ROUTE_FAILOVER_MAX)
    if model_id not in cands:
        cands = [model_id, *cands]
    seen: set[str] = set()
    ordered: list[str] = []
    for x in cands:
        if x not in seen:
            seen.add(x)
            ordered.append(x)
    ordered = _filter_failover_candidates_for_category(decision.category, ordered, registry)
    if not ordered:
        ordered = [model_id]
    decision.failover_candidates = tuple(ordered[:AUTO_ROUTE_FAILOVER_MAX])

    decision.model_id = model_id
    decision.used_model_fallback = used_fallback
    _emit_routing_metric(decision)

    return model_id, payload, decision
