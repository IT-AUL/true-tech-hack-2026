"""
Agentic Pipeline — orchestrates web research + presentation generation.

The pipeline:
1. Decides if web research is needed (LLM call)
2. Runs web searches
3. Synthesises a detailed topic string with research context
4. Calls the existing generate_presentation() tool directly with all the
   necessary __event_emitter__, __chat_id__, __message_id__ parameters so
   that the tool can attach the file to the message the same way it does
   when called natively by the LLM.
"""

import asyncio
import json
import logging
import re

from fastapi import HTTPException, Request
from open_webui.models.files import Files
from open_webui.models.users import UserModel
from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.misc import get_last_user_message

log = logging.getLogger(__name__)


def robust_json_parse(text: str) -> dict:
    """Parse JSON from LLM output, tolerating markdown code fences."""
    if not text:
        return {}
    # First try: braces extraction
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end >= start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass
    # Fallback: strip markdown fences
    try:
        cleaned = text.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        return json.loads(cleaned.strip())
    except Exception as exc:
        log.warning(f'robust_json_parse failed: {exc} | text[:120]={text[:120]}')
        return {}


async def run_agentic_pipeline(
    request: Request,
    form_data: dict,
    extra_params: dict,
    user: UserModel,
) -> tuple[dict, dict]:
    """
    Intercept a presentation request, run optional web research,
    then call generate_presentation() directly.

    Returns (modified_form_data, agent_flags).
    agent_flags is always {} — file delivery is handled entirely inside
    generate_presentation() via __event_emitter__ + __chat_id__ + __message_id__.
    """
    event_emitter = extra_params.get('__event_emitter__')
    metadata = extra_params.get('__metadata__', {})
    model = extra_params.get('__model__', {})

    chat_id = metadata.get('chat_id')
    message_id = metadata.get('message_id')

    log.info(f'[PIPELINE] Starting with chat_id={chat_id}, message_id={message_id}')
    log.debug(f'[PIPELINE] Metadata: {metadata}')

    messages = form_data.get('messages', [])
    user_query = get_last_user_message(messages)
    orchestrator_model = form_data.get('model', 'default')

    async def _emit(description: str, done: bool = False):
        if event_emitter:
            await event_emitter(
                {
                    'type': 'status',
                    'data': {
                        'action': 'presentation',
                        'description': description,
                        'done': done,
                    },
                }
            )

    async def _safe_llm(payload: dict, retries: int = 3):
        for attempt in range(retries):
            try:
                return await generate_chat_completion(request, form_data=payload, user=user)
            except HTTPException as exc:
                if attempt == retries - 1:
                    raise
                log.warning(f'LLM attempt {attempt + 1}/{retries} failed: {exc}')
                await asyncio.sleep(2)
            except Exception as exc:
                if attempt == retries - 1:
                    raise
                log.warning(f'LLM attempt {attempt + 1}/{retries} unexpected error: {exc}')
                await asyncio.sleep(2)
        return None

    def _llm_text(resp) -> str:
        try:
            raw = json.loads(resp.body.decode('utf-8')) if hasattr(resp, 'body') else resp
            return raw.get('choices', [{}])[0].get('message', {}).get('content', '')
        except Exception:
            return ''

    # ── Step 1: Should we search the web? ──────────────────────────────────
    await _emit('Анализ необходимости поиска в интернете...')

    research_results: list[str] = []
    try:
        decision_resp = await _safe_llm(
            {
                'model': orchestrator_model,
                'messages': [
                    {'role': 'system', 'content': 'You are a strict JSON-only planning agent.'},
                    {
                        'role': 'user',
                        'content': (
                            f'The user wants a presentation on: "{user_query}"\n'
                            'Do you need fresh internet data? Reply ONLY with JSON:\n'
                            '{"needs_research": true, "search_queries": ["q1", "q2"]} or {"needs_research": false}'
                        ),
                    },
                ],
                'stream': False,
            }
        )
        decision = robust_json_parse(_llm_text(decision_resp))

        if decision.get('needs_research') and decision.get('search_queries'):
            queries = decision['search_queries'][:2]
            await _emit(f'Поиск в интернете: {", ".join(queries)}')

            from open_webui.tools.builtin import search_web

            for q in queries:
                try:
                    res = await search_web(
                        q,
                        count=3,
                        __request__=request,
                        __user__=user.model_dump() if hasattr(user, 'model_dump') else user,
                    )
                    if res and 'error' not in res:
                        research_results.append(f"Results for '{q}':\n{res}")
                except Exception as exc:
                    log.warning(f'search_web failed for "{q}": {exc}')
    except Exception as exc:
        log.warning(f'Research decision step failed: {exc}')

    # ── Step 2: Build enriched topic string ────────────────────────────────
    if research_results:
        context_block = '\n\n'.join(research_results)
        enriched_topic = f'{user_query}\n\n=== Research context (use this data in the slides) ===\n{context_block}'
    else:
        enriched_topic = user_query

    # ── Step 3: Synthesis of full presentation content (one-shot) ────────────
    await _emit('Синтез структуры и контента для 7 слайдов...')

    presentation_gen_prompt = f"""Ты Эксперт по созданию презентаций. На основе предоставленного контекста создай ПОЛНЫЙ контент для презентации из 7 слайдов.
Задача: Сделать качественную, информативную презентацию.

Контекст: {enriched_topic}

Ответь ИСКЛЮЧИТЕЛЬНО валидным JSON объектом на русском языке:
{{
  "title": "Главный заголовок презентации",
  "slides": [
    {{
      "title": "Заголовок слайда",
      "bullets": ["Детальный тезис 1", "Детальный тезис 2", "Детальный тезис 3"],
      "notes": "Полный текст выступления для этого слайда."
    }}
  ]
}}
"""
    gen_payload = {
        'model': orchestrator_model,
        'messages': [{'role': 'user', 'content': presentation_gen_prompt}],
        'stream': False,
    }

    slides_data = None
    pres_title = user_query

    try:
        content_res = await _safe_llm(gen_payload)
        raw_text = _llm_text(content_res)
        parsed_data = robust_json_parse(raw_text)

        if parsed_data and 'slides' in parsed_data:
            slides_data = parsed_data['slides']
            pres_title = parsed_data.get('title', user_query)
            log.info(f'[PIPELINE] Single-shot synthesis success: {len(slides_data)} slides generated.')
        else:
            log.warning('[PIPELINE] Single-shot synthesis returned no slides, falling back.')
    except Exception as exc:
        log.warning(f'[PIPELINE] Content synthesis failed: {exc}. Falling back to tool-led planning.')

    # ── Step 4: Call generate_presentation() for Local Assembly ─────────────
    from open_webui.tools.builtin import generate_presentation

    model_param = model if (isinstance(model, dict) and model.get('id')) else {'id': orchestrator_model}

    result_str = await generate_presentation(
        topic=pres_title,
        num_slides=7,
        slides_data=slides_data,  # Pass pre-generated content
        __request__=request,
        __user__=user.model_dump() if hasattr(user, 'model_dump') else (user if isinstance(user, dict) else {}),
        __event_emitter__=event_emitter,
        __chat_id__=chat_id,
        __message_id__=message_id,
        __model__=model_param,
    )

    # ── Step 5: Extract FILE_ID and final delivery ─────────────────────────
    file_id = None
    file_payload = []
    file_match = re.search(r'FILE_ID:([a-f0-9\-]+)', result_str)

    if file_match:
        file_id = file_match.group(1)
        # Cleaner text for the UI
        result_str = result_str.replace(f' FILE_ID:{file_id}', '').strip()

        file_obj = Files.get_file_by_id(file_id)
        if file_obj:
            file_payload = [
                {
                    'type': 'file',
                    'id': file_obj.id,
                    'url': file_obj.id,
                    'name': file_obj.filename,
                    'content_type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    'size': file_obj.meta.get('size', 0) if file_obj.meta else 0,
                    'status': 'uploaded',
                }
            ]

            # Final delivery string
            result_str = f'Презентация «{pres_title}» готова! Вы можете скачать её по ссылке ниже.\n\n[📥 Скачать презентацию: {file_obj.filename}](/api/v1/files/{file_id}/content)'

    return {
        'content': result_str,
        'files': file_payload,
        'file_id': file_id,
    }
