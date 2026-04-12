import hashlib
import json
import logging
import os
import re
from collections.abc import Mapping
from typing import Any

import httpx

log = logging.getLogger(__name__)

# Simple in-memory cache for decisions within a short timeframe/process life
_ROUTING_CACHE: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Routing Preferences (Dynamic Model Resolution)
# ---------------------------------------------------------------------------
ROUTE_MODEL_PREFERENCES = {
    'image_gen': ('flux', 'gpt-image', 'dall-e', 'imagen'),
    'audio_gen': ('lyria', 'music', 'audio-gen'),
    'vision': ('vision', 'gemini', 'vl', 'gpt-4o', 'claude', 'omni'),
    'code': ('coder', 'code', 'devstral', 'deepseek-coder'),
    'research': ('research',),
    'math_logic': ('reason', 'math'),
    'analytics': ('analyst', 'analytics'),
    'creative': ('creative', 'writer'),
    'document': ('document', 'pdf'),
    'fallback': ('qwen', 'gpt', 'claude', 'llama', 'mistral', 'gemini'),
}

NON_TEXT_MODEL_KEYWORDS = (
    'embedding',
    'rerank',
    'whisper',
    'tts',
    'transcribe',
    'transcription',
    'stt',
    'asr',
    'flux',
    'lyria',
    'image',
    'audio',
    'speech',
    'moderation',
)

# ---------------------------------------------------------------------------
# Reka AI settings (used for intelligent classification)
# ---------------------------------------------------------------------------
REKA_API_KEY = os.environ.get('REKA_API_KEY') or os.environ.get('ROUTERAI_API_KEY', '')
REKA_API_URL = os.environ.get('REKA_API_URL') or os.environ.get('ROUTERAI_API_URL', 'https://api.reka.ai/v1')
REKA_ROUTER_MODEL = os.environ.get('REKA_ROUTER_MODEL', 'rekaai/reka-edge')

# ---------------------------------------------------------------------------
# Regex patterns (safety fallback for classification)
# ---------------------------------------------------------------------------
PATTERNS = {
    'image_gen': re.compile(
        r'(?i)\b(нарисуй|сгенерируй\s+картинку|нарисовать|сгенерировать\s+изображение|изобрази|сделай\s+картинку|создай\s+изображение|draw|generate\s+image|picture)\b'
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

# ---------------------------------------------------------------------------
# LLM classification logic
# ---------------------------------------------------------------------------

_ROUTER_SYSTEM_PROMPT = """\
Вы — ассистент маршрутизации. Получив диалог, выберите одну наиболее подходящую категорию \
для последнего сообщения пользователя из списка ниже и ответьте ТОЛЬКО корректным JSON-объектом \
в формате: {"category": "<category_name>"}

Доступные категории:
- image_gen  : пользователь хочет сгенерировать / нарисовать изображение или иллюстрацию
- audio_gen  : пользователь хочет сгенерировать музыку, звук или аудио
- vision     : сообщение содержит изображение, которое нужно проанализировать или описать
- code       : задачи по программированию, отладке, написанию скриптов
- math_logic : математика, уравнения, логика, алгоритмы
- research   : глубокое исследование, анализ рынка, поиск информации
- analytics  : анализ данных, статистика, обработка CSV/графиков
- creative   : творческое письмо, стихи, рассказы, копирайтинг
- document   : анализ или суммаризация документов/PDF
- fallback   : всё остальное / общий разговор

НЕ добавляйте никакого дополнительного текста, markdown или объяснений — только JSON-объект.\
"""


async def _classify_with_llm(text_content: str, has_image: bool) -> str | None:
    if not REKA_API_KEY:
        log.warning('REKA_API_KEY is not set — skipping LLM routing, using regex fallback.')
        return None

    context_parts: list[str] = []
    if has_image:
        context_parts.append('[User attached an image]')
    if text_content:
        context_parts.append(text_content[:2000])

    user_message = '\n'.join(context_parts) or '(empty message)'

    payload = {
        'model': REKA_ROUTER_MODEL,
        'messages': [
            {'role': 'system', 'content': _ROUTER_SYSTEM_PROMPT},
            {'role': 'user', 'content': user_message},
        ],
        'max_tokens': 32,
        'temperature': 0.0,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f'{REKA_API_URL}/chat/completions',
                headers={
                    'Authorization': f'Bearer {REKA_API_KEY}',
                    'Content-Type': 'application/json',
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        raw = data['choices'][0]['message']['content'].strip()
        match = re.search(r'(\{.*\})', raw, re.DOTALL)
        if match:
            raw = match.group(1)

        result = json.loads(raw)
        category = result.get('category', 'fallback')

        if category not in ROUTE_MODEL_PREFERENCES:
            log.warning('LLM returned unknown category %r — defaulting to fallback', category)
            return 'fallback'

        log.debug('LLM router chose category: %s', category)
        return category

    except Exception as exc:
        log.warning('LLM routing failed (%s). Raw response: %s', exc, raw if 'raw' in locals() else 'N/A')
        return None


def _classify_with_regex(text_content: str, has_image: bool) -> str:
    if PATTERNS['image_gen'].search(text_content):
        return 'image_gen'
    if PATTERNS['audio_gen'].search(text_content):
        return 'audio_gen'
    if has_image:
        return 'vision'
    if len(text_content) > 10000 or PATTERNS['document'].search(text_content):
        return 'document'
    if PATTERNS['code'].search(text_content):
        return 'code'
    if PATTERNS['math_logic'].search(text_content):
        return 'math_logic'
    if PATTERNS['research'].search(text_content):
        return 'research'
    if PATTERNS['analytics'].search(text_content):
        return 'analytics'
    if PATTERNS['creative'].search(text_content):
        return 'creative'
    return 'fallback'


# ---------------------------------------------------------------------------
# Helper functions for dynamic model matching
# ---------------------------------------------------------------------------


def _get_available_model_list(available_models: Any) -> list[dict[str, Any]]:
    if isinstance(available_models, Mapping):
        return [model for model in available_models.values() if isinstance(model, dict)]
    if isinstance(available_models, list):
        return [model for model in available_models if isinstance(model, dict)]
    return []


def _get_model_search_text(model: dict[str, Any]) -> str:
    parts = [
        model.get('id', ''),
        model.get('name', ''),
        model.get('owned_by', ''),
        model.get('openai', {}).get('id', '') if isinstance(model.get('openai'), dict) else '',
    ]
    return ' '.join(part for part in parts if part).lower()


def _match_preferred_model(route: str, available_models: list[dict[str, Any]]) -> str | None:
    for keyword in ROUTE_MODEL_PREFERENCES.get(route, ()):
        for model in available_models:
            model_id = model.get('id')
            if not model_id or model_id == 'auto':
                continue
            if keyword in _get_model_search_text(model):
                return model_id
    return None


def _resolve_text_fallback(available_models: list[dict[str, Any]]) -> str | None:
    preferred_fallback = _match_preferred_model('fallback', available_models)
    if preferred_fallback:
        return preferred_fallback
    for model in available_models:
        model_id = model.get('id')
        if not model_id or model_id == 'auto':
            continue
        search_text = _get_model_search_text(model)
        if not any(keyword in search_text for keyword in NON_TEXT_MODEL_KEYWORDS):
            return model_id
    return None


def resolve_model_for_route(route: str, available_models: Any) -> tuple[str | None, bool]:
    model_list = _get_available_model_list(available_models)
    matched_model = _match_preferred_model(route, model_list)
    if matched_model:
        return matched_model, False
    return _resolve_text_fallback(model_list), True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_auto_routed_route(payload: dict[str, Any]) -> str:
    """
    Analyzes the payload to determine the best route category.
    Uses LLM classification with caching and regex fallback.
    """
    messages = payload.get('messages', [])
    if not messages:
        return 'fallback'

    try:
        history_str = json.dumps(messages, sort_keys=True)
        cache_key = hashlib.md5(history_str.encode()).hexdigest()
        if cache_key in _ROUTING_CACHE:
            log.debug('Using cached auto-routing decision for key %s', cache_key)
            return _ROUTING_CACHE[cache_key]
    except Exception:
        cache_key = None

    last_user_message = next((msg for msg in reversed(messages) if msg.get('role') == 'user'), None)
    if not last_user_message:
        return 'fallback'

    content = last_user_message.get('content', '')
    has_image = False
    text_content = ''

    if isinstance(content, str):
        text_content = content
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                if part.get('type') in ('text', 'input_text'):
                    text_content += part.get('text', '') + ' '
                elif part.get('type') in ('image_url', 'input_image'):
                    has_image = True

    # --- Step 1: LLM classification ---
    category = await _classify_with_llm(text_content, has_image)
    method = 'LLM'

    # --- Step 2: Fallback to Regex ---
    if category is None:
        category = _classify_with_regex(text_content, has_image)
        method = 'Regex (Fallback)'

    log.info('--- AUTO-ROUTING: Detected route "%s" using %s ---', category, method)

    if cache_key:
        _ROUTING_CACHE[cache_key] = category
        if len(_ROUTING_CACHE) > 1000:
            _ROUTING_CACHE.clear()

    return category


async def process_auto_routing(
    request,
    payload: dict[str, Any],
    user,
    available_models: Any | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Main entry point for auto-routing. Resolves intent into a specific model ID
    available in the current instance's model catalog.
    """
    from open_webui.models.files import Files
    from open_webui.utils.files import get_image_base64_from_file_id

    messages = payload.get('messages', [])
    if not messages:
        model_id, used_fallback = resolve_model_for_route('fallback', available_models)
        return model_id or 'fallback', payload

    has_vision = False
    for msg in messages:
        if msg.get('role') != 'user':
            continue
        files = msg.get('files', [])
        if 'metadata' in payload and isinstance(payload['metadata'], dict):
            files.extend(payload['metadata'].get('files', []))

        file_ids = list(set([f.get('id') or f.get('file_id') for f in files if isinstance(f, dict)]))
        content = msg.get('content', '')
        if isinstance(content, list):
            for part in content:
                if part.get('type') == 'file' and 'file_id' in part:
                    file_ids.append(part['file_id'])

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
                    has_vision = True
                    content.append({'type': 'image_url', 'image_url': {'url': f'data:{content_type};base64,{b64}'}})
            else:
                text_content = file_item.data.get('content', '') if file_item.data else ''
                if text_content:
                    content.append(
                        {'type': 'text', 'text': f'\\n[File Content ({file_item.filename}):\\n{text_content}]\\n'}
                    )

    route = await get_auto_routed_route(payload)
    if has_vision and route != 'image_gen':
        route = 'vision'

    if available_models is None:
        available_models = getattr(getattr(request, 'app', None), 'state', None)
        available_models = getattr(available_models, 'OPENAI_MODELS', None)

    model_id, used_fallback = resolve_model_for_route(route, available_models)
    if not model_id:
        raise ValueError(f'Could not resolve model for route {route}')

    log.info('Auto-routing resolved route=%s -> model=%s (fallback=%s)', route, model_id, used_fallback)
    return model_id, payload
