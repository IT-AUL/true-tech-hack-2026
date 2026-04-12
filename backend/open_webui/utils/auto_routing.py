import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# Model mapping defaults to top-ranked models per category based on user spec
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


async def get_auto_routed_model(payload: dict[str, Any]) -> str:
    """
    Analyzes the payload (messages) to determine the best model based on intent and content.
    Returns the ID of the routed model.
    """
    messages = payload.get('messages', [])
    if not messages:
        return MODELS['fallback']

    # Extract the last message content which usually contains the user's latest objective
    last_user_message = next((msg for msg in reversed(messages) if msg.get('role') == 'user'), None)

    if not last_user_message:
        return MODELS['fallback']

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
        return MODELS['image_gen']

    # 1.5. Audio Generation Intent Checking
    if PATTERNS['audio_gen'].search(text_content):
        return MODELS['audio_gen']

    # 2. Vision/Image Analysis Check
    # (If an image is attached and the user didn't ask to create an image, we default to VLM)
    if has_image:
        return MODELS['vision']

    # 3. Document Analysis Check Focus
    # If the user text is very long (indicative of pasting a long document)
    if len(text_content) > 10000 or PATTERNS['document'].search(text_content):
        return MODELS['document']

    # 4. Code Generation Check
    if PATTERNS['code'].search(text_content):
        return MODELS['code']

    # 5. Math/Logic Request Check
    if PATTERNS['math_logic'].search(text_content):
        return MODELS['math_logic']

    # 6. Deep Research Check
    if PATTERNS['research'].search(text_content):
        return MODELS['research']

    # 7. Analytics Check
    if PATTERNS['analytics'].search(text_content):
        return MODELS['analytics']

    # 8. Creative Writing Check
    if PATTERNS['creative'].search(text_content):
        return MODELS['creative']

    # 9. Fallback Default Model
    return MODELS['fallback']


async def process_auto_routing(request, payload: dict[str, Any], user) -> tuple[str, dict[str, Any]]:
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

    model_id = await get_auto_routed_model(payload)
    if has_vision and model_id != MODELS['image_gen']:
        model_id = MODELS['vision']

    return model_id, payload
