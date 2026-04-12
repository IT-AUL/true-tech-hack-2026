import hashlib
import json
import logging
import os
import re
from typing import Any

import httpx

log = logging.getLogger(__name__)

# Simple in-memory cache for decisions within a short timeframe/process life
_ROUTING_CACHE: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Model mapping — top-ranked models per category based on user spec
# ---------------------------------------------------------------------------
MODELS = {
    'image_gen': 'black-forest-labs/flux.2-max',
    'audio_gen': 'google/lyria-3-pro-preview',
    'vision': 'google/gemini-3.1-flash-lite-preview',
    'code': 'qwen/qwen3.6-plus',
    'research': 'qwen/qwen3.6-plus',
    'math_logic': 'qwen/qwen3.6-plus',
    'analytics': 'qwen/qwen3.6-plus',
    'creative': 'qwen/qwen3.6-plus',
    'document': 'qwen/qwen3.6-plus',
    'fallback': 'qwen/qwen3.6-plus',
}

# ---------------------------------------------------------------------------
# Reka AI settings (read from environment — no hardcodes)
# ---------------------------------------------------------------------------
REKA_API_KEY = os.environ.get('REKA_API_KEY') or os.environ.get('ROUTERAI_API_KEY', '')
REKA_API_URL = os.environ.get('REKA_API_URL') or os.environ.get('ROUTERAI_API_URL', 'https://api.reka.ai/v1')
REKA_ROUTER_MODEL = os.environ.get('REKA_ROUTER_MODEL', 'rekaai/reka-edge')

# ---------------------------------------------------------------------------
# Regex fallback patterns (used when the LLM router is unavailable)
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
# LLM routing via reka-edge
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
    """
    Call reka-edge to classify the user intent.
    Returns a category key (str) or None on failure.
    """
    if not REKA_API_KEY:
        log.warning('REKA_API_KEY is not set — skipping LLM routing, using regex fallback.')
        return None

    # Build a short context string for the router
    context_parts: list[str] = []
    if has_image:
        context_parts.append('[User attached an image]')
    if text_content:
        # Truncate to avoid excessive token usage
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

        # Robust JSON extraction: find the first { and last }
        match = re.search(r'(\{.*\})', raw, re.DOTALL)
        if match:
            raw = match.group(1)

        result = json.loads(raw)
        category = result.get('category', 'fallback')

        if category not in MODELS:
            log.warning('LLM returned unknown category %r — defaulting to fallback', category)
            return 'fallback'

        log.debug('LLM router chose category: %s', category)
        return category

    except Exception as exc:
        log.warning('LLM routing failed (%s). Raw response: %s', exc, raw if 'raw' in locals() else 'N/A')
        return None


# ---------------------------------------------------------------------------
# Regex-based fallback classifier (kept as safety net)
# ---------------------------------------------------------------------------


def _classify_with_regex(text_content: str, has_image: bool) -> str:
    """Classify intent using regex patterns. Returns a MODELS key."""
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
# Public API
# ---------------------------------------------------------------------------


async def get_auto_routed_model(payload: dict[str, Any]) -> str:
    """
    Analyzes the payload (messages) to determine the best model based on intent
    and content.  Uses reka-edge via the Reka AI API as the primary classifier;
    falls back to regex patterns if the LLM call is unavailable or fails.
    Returns the model ID string.
    """
    messages = payload.get('messages', [])
    if not messages:
        return MODELS['fallback']

    # Generate a cache key based on the conversation history
    # This prevents multiple calls for title generation, etc.
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
        return MODELS['fallback']

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

    # --- Primary: LLM router (reka-edge) ---
    category = await _classify_with_llm(text_content, has_image)
    method = 'LLM'

    # --- Fallback: regex classifier ---
    if category is None:
        category = _classify_with_regex(text_content, has_image)
        method = 'Regex (Fallback)'

    model_id = MODELS.get(category, MODELS['fallback'])
    log.info(f"--- AUTO-ROUTING: Selected category '{category}' using {method} ---")

    # Store in cache
    if cache_key:
        _ROUTING_CACHE[cache_key] = model_id
        # Optional: simple cache cleanup if it grows too large
        if len(_ROUTING_CACHE) > 1000:
            _ROUTING_CACHE.clear()

    return model_id


async def process_auto_routing(request, payload: dict[str, Any], user) -> tuple[str, dict[str, Any]]:
    """
    Processes the payload to extract files, audio, and images for automatic
    injection into messages.  Returns the selected model ID and the modified
    payload.
    """
    from open_webui.models.files import Files
    from open_webui.routers.audio import transcribe
    from open_webui.storage.provider import Storage
    from open_webui.utils.files import get_image_base64_from_file_id

    messages = payload.get('messages', [])
    if not messages:
        return MODELS['fallback'], payload

    has_vision = False

    for msg in messages:
        if msg.get('role') != 'user':
            continue

        files = []
        if 'files' in msg:
            files.extend(msg['files'])

        if 'metadata' in payload and isinstance(payload['metadata'], dict):
            metadata_files = payload['metadata'].get('files', [])
            if metadata_files:
                files.extend(metadata_files)

        file_ids = [f.get('id') or f.get('file_id') for f in files if isinstance(f, dict)]

        content = msg.get('content', '')
        if isinstance(content, list):
            for part in content:
                if part.get('type') == 'file' and 'file_id' in part:
                    file_ids.append(part['file_id'])

        file_ids = list(set([fid for fid in file_ids if fid]))

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
                has_vision = True
                b64 = get_image_base64_from_file_id(file_id)
                if b64:
                    content.append({'type': 'image_url', 'image_url': {'url': f'data:{content_type};base64,{b64}'}})
            elif content_type.startswith('audio/') or content_type.startswith('video/'):
                cached_text = file_item.data.get('content', '') if file_item.data else ''
                if cached_text:
                    content.append({'type': 'text', 'text': f'\\n[Audio Transcription: {cached_text}]\\n'})
                else:
                    try:
                        file_path = Storage.get_file(file_item.path)
                        res = transcribe(request, file_path, None, user)
                        transcription_text = res.get('text', '')
                        if transcription_text:
                            file_data = file_item.data or {}
                            file_data['content'] = transcription_text
                            Files.update_file_data_by_id(file_id, file_data)
                            content.append(
                                {'type': 'text', 'text': f'\\n[Audio Transcription: {transcription_text}]\\n'}
                            )
                    except Exception as e:
                        log.error('Error transcribing auto-routing audio %s: %s', file_id, e)
            else:
                text_content = file_item.data.get('content', '') if file_item.data else ''
                if text_content:
                    content.append(
                        {
                            'type': 'text',
                            'text': f'\\n[File Content ({file_item.filename}):\\n{text_content}]\\n',
                        }
                    )

    model_id = await get_auto_routed_model(payload)
    if has_vision and model_id != MODELS['image_gen']:
        model_id = MODELS['vision']

    return model_id, payload
