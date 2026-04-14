"""
Hybrid auto-router for GPTHub.

4-stage classification pipeline:
  Stage 1  Guardrails           (explicit modality, attachments, code blocks, documents)
  Stage 2  Semantic embeddings  (bge-m3 cosine similarity vs seed utterances)
  Stage 3  Cheap LLM classifier (internal model, confidence + complexity)
  Stage 4  Regex safety net     (keyword patterns)

Provider-agnostic: works with any mix of OpenAI-compatible backends.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import time
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, replace
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

PATTERNS = {
    'image_gen': re.compile(
        r'(?i)\b('
        r'нарисуй|изобрази|'
        r'сгенерируй\s+картинку|сгенерируй\s+изображение|нарисовать|сгенерировать\s+изображение|'
        r'сделай\s+картинку|создай\s+картинку|создай\s+изображение|'
        r'хочу\s+картинку|хочу\s+изображение|нужна\s+картинка|дай\s+картинку|'
        r'draw|generate\s+(?:an\s+)?image|'
        r'i\s+want\s+(?:a\s+)?picture|picture\s+of|picture'
        r')\b'
    ),
    'audio_gen': re.compile(r'(?i)\b(звук|аудио|песн|music|song|audio|sound|сгенерируй\s+звук|мелоди)\b'),
    'code': re.compile(
        r'(?i)\b(код|скрипт|баг|рефакторинг|функция|ошибка\s+в\s+коде|разработка|апп|приложение|программа|html|css|javascript|python|c\+\+|java|golang|react|запрограммируй|напиши\s+тест|сделай\s+парсер|code|script|debug)\b'
    ),
    'math_logic': re.compile(
        r'(?i)\b(реши\s+уравнение|математика|докажи|уравнение|теорема|алгоритм|вычисли|посчитай|найди\s+интеграл|геометрия|алгебра|логика|математический|задача|math|equation|calculate)\b'
    ),
    'research': re.compile(
        r'(?i)\b(изучи|исследуй|проанализируй\s+рынок|сравни|найди\s+информацию|глубокий\s+анализ|поиск|подробно\s+изучи|research|investigate|search)\b'
    ),
    'analytics': re.compile(
        r'(?i)\b(анализ\s+данных|статистика|корреляция|csv|график|таблица|отчет|сводка|аналитика|метрики|data\s+science|pandas|dataset|датасет|analytics)\b'
    ),
    'creative': re.compile(
        r'(?i)\b(напиши\s+стих|придумай\s+историю|рассказ|сценарий|шутка|копирайтинг|напиши\s+пост|эссе|сочинение|напиши\s+текст|поэма|creative|story|poem|joke)\b'
    ),
    'document': re.compile(
        r'(?i)\b(документ|pdf|пдф|проанализируй\s+файл|шпоргалка|резюме|контракт|договор|скан|текст\s+ниже|document)\b'
    ),
}

_CODE_BLOCK_RE = re.compile(
    r'```|^(def |class |import |from |function |const |let |var |SELECT |CREATE |<div|<html)', re.MULTILINE
)

# ---------------------------------------------------------------------------
# Route -> model preference keywords (used for scored selection)
# ---------------------------------------------------------------------------

ROUTE_MODEL_PREFERENCES = {
    'image_gen': ('flux', 'gpt-image', 'dall-e', 'imagen', 'qwen-image', 'sd3', 'sdxl', 'z-image'),
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
)
_TIER_CHEAP_KW = (
    'mini',
    'nano',
    'small',
    'anya',
    'flash',
    'lite',
    'turbo',
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
    r'привет|здравствуй(?:те)?|добрый\s+(?:день|вечер)|доброе\s+утро|'
    r'ок(?:ей)?|спасибо|благодарю|да|нет|ага|понятно|ясно|хорошо'
    r')[.!?,\s]*$'
)
_PRECISE_REGEX_OVERRIDE_CATEGORIES = frozenset({'image_gen', 'audio_gen', 'vision', 'document'})


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
    # Ordered model IDs for auto-route upstream failover (same scoring as select_model)
    failover_candidates: tuple[str, ...] = ()


def _copy_routing_decision(decision: RoutingDecision) -> RoutingDecision:
    return replace(decision)


def _emit_routing_metric(decision: RoutingDecision) -> None:
    log.info(
        'routing_decision category=%s complexity=%s model=%s method=%s '
        'confidence=%.2f latency_ms=%d cache_hit=%s fallback=%s',
        decision.category,
        decision.complexity,
        decision.model_id or 'none',
        decision.method,
        decision.confidence,
        decision.latency_ms,
        decision.cache_hit,
        decision.used_model_fallback,
    )


# =========================================================================
# 4. TTL + LRU Cache (pure Python, no external deps)
# =========================================================================

_CACHE_MAX_SIZE = 2048
_CACHE_TTL_S = 600


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
    if features.recent_context and ROUTER_SHORT_MESSAGE_LEN > 0 and len(t) <= ROUTER_SHORT_MESSAGE_LEN:
        return (features.recent_context + '\n' + t).strip()
    return features.text


def _semantic_query_text(features: RequestFeatures) -> str:
    """Embedding query: include recent context when the last turn is short."""
    from open_webui.env import ROUTER_CONTEXT_MAX_CHARS, ROUTER_SHORT_MESSAGE_LEN

    t = features.text.strip()
    if not features.recent_context or not ROUTER_SHORT_MESSAGE_LEN or len(t) > ROUTER_SHORT_MESSAGE_LEN:
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
    base = f'{norm}|{"img" if features.has_image else ""}|{"url" if features.has_url else ""}|{ctx_hash}'
    digest = hashlib.md5(base.encode()).hexdigest()
    if metadata and isinstance(metadata, dict):
        cid = metadata.get('chat_id')
        mid = metadata.get('message_id')
        if cid is not None and mid is not None and str(cid) and str(mid):
            return f'{digest}|{cid}|{mid}'
    return digest


# =========================================================================
# Stage 1: Rule Engine
# =========================================================================


def _classify_with_rules(features: RequestFeatures) -> RoutingDecision | None:
    pattern_text = _rules_pattern_text(features)

    if features.has_image and not PATTERNS['image_gen'].search(pattern_text):
        return RoutingDecision('vision', 'low', method='rules')

    # Do not map voice/video *attachments* to audio_gen (music APIs like Lyria). Attachments are
    # transcribed in process_auto_routing; routing should follow text intent. audio_gen only via
    # explicit keywords below (e.g. «создай музыку», generate a song).

    if PATTERNS['image_gen'].search(pattern_text):
        return RoutingDecision('image_gen', 'low', method='rules')

    if PATTERNS['audio_gen'].search(pattern_text):
        return RoutingDecision('audio_gen', 'low', method='rules')

    if features.has_url:
        return RoutingDecision('research', 'medium', method='rules')

    if features.has_code_block:
        return RoutingDecision('code', _estimate_complexity(features.text_len), method='rules')

    if features.text_len > 10000 or PATTERNS['document'].search(pattern_text):
        return RoutingDecision('document', 'high' if features.text_len > 10000 else 'medium', method='rules')

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
_seed_init_lock = False


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
    global _seed_embeddings, _seed_init_lock

    if _seed_embeddings is None and not _seed_init_lock:
        _seed_init_lock = True
        try:
            _seed_embeddings = await _init_seed_embeddings(embedding_fn)
        except Exception:
            _seed_embeddings = {}
        finally:
            _seed_init_lock = False

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
        )

    return None


# =========================================================================
# Stage 3: LLM Classifier (provider-agnostic, auto-discovery)
# =========================================================================

_ROUTER_SYSTEM_PROMPT = """\
Вы — ассистент маршрутизации. Учитывайте блок «Недавний диалог» (если есть): follow-up вопросы
часто ссылаются на предыдущие реплики. Например, если ранее обсуждали иллюстрацию, а сейчас
короткая просьба вроде «нарисуй», «сделай вариант», «ещё раз» — выберите image_gen.
Аналогично для музыки/звука — audio_gen. Если прикреплено изображение и нужен разбор — vision.

Категории:
- image_gen  : генерация изображения/иллюстрации
- audio_gen  : генерация музыки/звука/аудио
- vision     : анализ прикреплённого изображения
- code       : программирование, отладка, скрипты
- math_logic : математика, уравнения, алгоритмы
- research   : глубокое исследование, анализ рынка
- analytics  : анализ данных, статистика, CSV/графики
- creative   : творческое письмо, стихи, копирайтинг
- document   : анализ/суммаризация документов
- fallback   : всё остальное / общий разговор

Сложность:
- low    : простой вопрос, факт, приветствие
- medium : обычная задача средней сложности
- high   : глубокий анализ, сложный код, исследование

Ответь ТОЛЬКО JSON: {"category": "...", "complexity": "...", "confidence": 0.0-1.0}\
"""

_LLM_CONFIDENCE_THRESHOLD = 0.7

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


async def _classify_with_llm(
    features: RequestFeatures,
    request=None,
    registry: list[ModelMeta] | None = None,
) -> RoutingDecision | None:
    config = _get_classifier_config(request, registry)
    if not config:
        log.debug('No LLM classifier config available; skipping Stage 3.')
        return None

    model, base_url, api_key = config

    context_parts: list[str] = []
    if features.recent_context:
        context_parts.append('Недавний диалог:\n' + features.recent_context[:2500])
    if features.has_image:
        context_parts.append('[User attached an image]')
    if features.has_audio:
        context_parts.append('[User attached audio]')
    if features.text:
        context_parts.append('Текущее сообщение пользователя:\n' + features.text[:2000])
    user_message = '\n\n'.join(context_parts) or '(empty message)'

    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': _ROUTER_SYSTEM_PROMPT},
            {'role': 'user', 'content': user_message},
        ],
        'max_tokens': 64,
        'temperature': 0.0,
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

            if category not in VALID_CATEGORIES:
                log.warning('LLM returned unknown category %r, defaulting to fallback', category)
                category = 'fallback'
            if complexity not in VALID_COMPLEXITIES:
                complexity = 'medium'

            return RoutingDecision(
                category=category,
                complexity=complexity,
                method='llm',
                confidence=confidence,
            )

        except httpx.TimeoutException:
            if attempt == 0:
                log.warning('LLM classifier timeout (attempt 1), retrying...')
                continue
            log.warning('LLM classifier timed out after retry')
            return None
        except Exception as exc:
            log.warning('LLM routing failed (%s). Raw: %s', exc, raw or 'N/A')
            return None

    return None


# =========================================================================
# Stage 4: Regex Safety Net
# =========================================================================


def _classify_with_regex(text: str, has_image: bool) -> RoutingDecision:
    if PATTERNS['image_gen'].search(text):
        cat = 'image_gen'
    elif PATTERNS['audio_gen'].search(text):
        cat = 'audio_gen'
    elif has_image:
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
    else:
        cat = 'fallback'

    return RoutingDecision(
        category=cat,
        complexity=_estimate_complexity(len(text)),
        method='regex_fallback',
    )


def _classify_with_regex_from_features(features: RequestFeatures) -> RoutingDecision:
    t = _rules_pattern_text(features)
    return _classify_with_regex(t, features.has_image)


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
    preferred_tier = _COMPLEXITY_TO_TIER.get(complexity, 'mid')
    keywords = ROUTE_MODEL_PREFERENCES.get(category, ())

    candidates: list[tuple[int, str]] = []
    for model in registry:
        if model.kind in _NON_ROUTABLE_KINDS or model.id == 'auto':
            continue
        if _exclude_generative_media_for_category(category, model):
            continue
        score = 0
        if model.kind == preferred_kind:
            score += 10
        elif preferred_kind == 'text' and model.kind == 'vlm':
            score += 4
        elif preferred_kind == 'text' and model.kind == 'code':
            score += 2
        if model.tier == preferred_tier:
            score += 5
        for idx, kw in enumerate(keywords):
            if kw in model.search_text:
                score += len(keywords) - idx
        if score > 0:
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


async def get_auto_routed_route(
    payload: dict[str, Any],
    request=None,
    registry: list[ModelMeta] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RoutingDecision:
    t0 = time.monotonic()
    features = extract_features(payload)

    key = build_routing_cache_key(features, metadata)
    if key is not None:
        cached = _routing_cache.get(key)
        if cached is not None:
            cached.cache_hit = True
            cached.latency_ms = int((time.monotonic() - t0) * 1000)
            return cached

    def _maybe_cache(decision: RoutingDecision) -> None:
        if key is not None:
            _routing_cache.put(key, decision)

    # Only skip semantic/LLM for genuine greetings / acknowledgements with no context.
    if _should_trivial_short_circuit(features):
        decision = RoutingDecision('fallback', 'low', method='trivial_short_circuit')
        decision.latency_ms = int((time.monotonic() - t0) * 1000)
        _maybe_cache(decision)
        return decision

    # Stage 1: Rules
    decision = _classify_with_rules(features)
    if decision:
        decision.latency_ms = int((time.monotonic() - t0) * 1000)
        _maybe_cache(decision)
        return decision

    # Stage 2: Semantic (if embedding function available)
    embedding_fn = None
    if request:
        embedding_fn = getattr(getattr(request, 'app', None), 'state', None)
        embedding_fn = getattr(embedding_fn, 'EMBEDDING_FUNCTION', None)

    if embedding_fn is not None:
        sem_text = _semantic_query_text(features)
        decision = await _classify_with_embeddings(sem_text, embedding_fn)
        if decision:
            decision.latency_ms = int((time.monotonic() - t0) * 1000)
            _maybe_cache(decision)
            return decision

    # Stage 3: LLM classifier
    llm_decision = await _classify_with_llm(features, request=request, registry=registry)
    if llm_decision and llm_decision.confidence >= _LLM_CONFIDENCE_THRESHOLD:
        llm_decision.latency_ms = int((time.monotonic() - t0) * 1000)
        _maybe_cache(llm_decision)
        return llm_decision

    # Keep regex only as a safety net for very precise hard signals.
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
            regex_decision.latency_ms = int((time.monotonic() - t0) * 1000)
            _maybe_cache(regex_decision)
            return regex_decision
        llm_decision.method = 'llm_low_conf'
        llm_decision.latency_ms = int((time.monotonic() - t0) * 1000)
        _maybe_cache(llm_decision)
        return llm_decision

    # Stage 4: Regex safety net
    decision = _classify_with_regex_from_features(features)
    decision.latency_ms = int((time.monotonic() - t0) * 1000)
    _maybe_cache(decision)
    return decision


# =========================================================================
# Public API
# =========================================================================


def evaluate_route_deterministic(payload: dict[str, Any]) -> RoutingDecision:
    """
    Run Stage 1 (rules) and Stage 4 (regex) only — no LLM or embedding calls.
    Use for offline evaluation datasets and fast regression checks.
    """
    features = extract_features(payload)
    if _should_trivial_short_circuit(features):
        return RoutingDecision('fallback', 'low', method='trivial_short_circuit')
    decision = _classify_with_rules(features)
    if decision:
        return decision
    return _classify_with_regex_from_features(features)


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

    decision = await get_auto_routed_route(payload, request=request, registry=registry, metadata=metadata)

    if has_vision and decision.category != 'image_gen':
        decision.category = 'vision'

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
