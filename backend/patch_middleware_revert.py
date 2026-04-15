with open('/Users/dremotha/Projects/Temp/true-tech-hack-2026/backend/open_webui/utils/middleware.py') as f:
    text = f.read()

search = """        from open_webui.utils.auto_routing import PATTERNS
        user_msg_for_check = get_last_user_message(form_data.get('messages', []))
        if user_msg_for_check and isinstance(user_msg_for_check, str) and PATTERNS['presentation'].search(user_msg_for_check):
            sys_instruct = "ВНИМАНИЕ: Пользователь запросил создание презентации. У тебя ЕСТЬ инструмент `generate_presentation`, ты ОБЯЗАН сразу вызвать его для генерации файла PPTX, не пытайся писать слайды текстом вручную!"
            form_data['messages'] = add_or_update_system_message(sys_instruct, form_data.get('messages', []), append=True)"""

replace = """        from open_webui.utils.auto_routing import PATTERNS
        user_msg_for_check = get_last_user_message(form_data.get('messages', []))
        is_pres = False
        if user_msg_for_check and isinstance(user_msg_for_check, str) and PATTERNS['presentation'].search(user_msg_for_check):
            is_pres = True

        if is_pres:
            # We intercept and process here to ensure 100% reliable orchestrated map-reduce!
            from open_webui.utils.agentic_pipeline import run_agentic_pipeline
            try:
                form_data, flags = await run_agentic_pipeline(request, form_data, extra_params, user)
                events.extend(flags.get('events', []))
            except Exception as e:
                log.exception(f"Agentic pipeline failed: {e}")"""

text = text.replace(search, replace)

with open('/Users/dremotha/Projects/Temp/true-tech-hack-2026/backend/open_webui/utils/middleware.py', 'w') as f:
    f.write(text)
