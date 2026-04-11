import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# Model mapping defaults to top-ranked models per category based on user spec
MODELS = {
    'image_gen': 'qwen-image',
    'vision': 'qwen3-vl-30b-a3b-instruct',
    'code': 'qwen3-coder-480b-a35b',
    'research': 'kimi-k2-instruct',
    'math_logic': 'QwQ-32B',
    'analytics': 'gpt-oss-120b',
    'creative': 'gemma-3-27b-it',
    'document': 'Qwen3-235B-A22B-Instruct-2507-FP8',
    'fallback': 'gpt-oss-120b',
}

# Extensive regex patterns for intent classification
PATTERNS = {
    'image_gen': re.compile(
        r'(?i)\b(нарисуй|сгенерируй\s+картинку|нарисовать|сгенерировать\s+изображение|изобрази|сделай\s+картинку|создай\s+изображение|draw|generate\s+image|picture)\b'
    ),
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
