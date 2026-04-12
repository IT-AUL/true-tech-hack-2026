import logging
import re
from collections.abc import Mapping
from typing import Any

log = logging.getLogger(__name__)

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

# Extensive regex patterns for intent classification
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


async def get_auto_routed_route(payload: dict[str, Any]) -> str:
    """
    Analyzes the payload (messages) to determine the best model based on intent and content.
    Returns the route category that should be resolved against the runtime model catalog.
    """
    messages = payload.get('messages', [])
    if not messages:
        return 'fallback'

    # Extract the last message content which usually contains the user's latest objective
    last_user_message = next((msg for msg in reversed(messages) if msg.get('role') == 'user'), None)

    if not last_user_message:
        return 'fallback'

    content = last_user_message.get('content', '')
    has_image = False
    text_content = ''

    # Parse content which could be a string or a list of parts
    if isinstance(content, str):
        text_content = content
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                if part.get('type') in ('text', 'input_text'):
                    text_content += part.get('text', '') + ' '
                elif part.get('type') in ('image_url', 'input_image'):
                    has_image = True

    # 1. Image Generation Intent Checking
    if PATTERNS['image_gen'].search(text_content):
        return 'image_gen'

    # 1.5. Audio Generation Intent Checking
    if PATTERNS['audio_gen'].search(text_content):
        return 'audio_gen'

    # 2. Vision/Image Analysis Check
    # (If an image is attached and the user didn't ask to create an image, we default to VLM)
    if has_image:
        return 'vision'

    # 3. Document Analysis Check Focus
    # If the user text is very long (indicative of pasting a long document)
    if len(text_content) > 10000 or PATTERNS['document'].search(text_content):
        return 'document'

    # 4. Code Generation Check
    if PATTERNS['code'].search(text_content):
        return 'code'

    # 5. Math/Logic Request Check
    if PATTERNS['math_logic'].search(text_content):
        return 'math_logic'

    # 6. Deep Research Check
    if PATTERNS['research'].search(text_content):
        return 'research'

    # 7. Analytics Check
    if PATTERNS['analytics'].search(text_content):
        return 'analytics'

    # 8. Creative Writing Check
    if PATTERNS['creative'].search(text_content):
        return 'creative'

    # 9. Fallback Default Model
    return 'fallback'


async def process_auto_routing(
    request,
    payload: dict[str, Any],
    user,
    available_models: Any | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Processes the payload to extract files, audio, and images for automatic injection into messages.
    Returns the selected model ID and the modified payload.
    """
    from open_webui.models.files import Files
    from open_webui.routers.audio import transcribe
    from open_webui.storage.provider import Storage
    from open_webui.utils.files import get_image_base64_from_file_id

    messages = payload.get('messages', [])
    if not messages:
        model_id, used_fallback = resolve_model_for_route('fallback', available_models)
        if model_id:
            log.info(
                'Auto-routing resolved route=%s model=%s fallback=%s available_models=%s',
                'fallback',
                model_id,
                used_fallback,
                len(_get_available_model_list(available_models)),
            )
            return model_id, payload

        raise ValueError('Auto-routing could not resolve a fallback model from the available catalog.')

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
                b64 = get_image_base64_from_file_id(file_id)
                if b64:
                    has_vision = True
                    content.append(
                        {
                            'type': 'image_url',
                            'image_url': {'url': f'data:{content_type};base64,{b64}'},
                        }
                    )
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
                            # Update DB cache
                            file_data = file_item.data or {}
                            file_data['content'] = transcription_text
                            Files.update_file_data_by_id(file_id, file_data)
                            content.append(
                                {'type': 'text', 'text': f'\\n[Audio Transcription: {transcription_text}]\\n'}
                            )
                    except Exception as e:
                        log.error(f'Error transcribing auto-routing audio {file_id}: {e}')
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
        log.error(
            'Auto-routing failed to resolve route=%s available_models=%s',
            route,
            len(_get_available_model_list(available_models)),
        )
        raise ValueError('Auto-routing could not resolve a model from the available catalog.')

    log.info(
        'Auto-routing resolved route=%s model=%s fallback=%s available_models=%s',
        route,
        model_id,
        used_fallback,
        len(_get_available_model_list(available_models)),
    )
    return model_id, payload
