with open('/Users/dremotha/Projects/Temp/true-tech-hack-2026/backend/open_webui/tools/builtin.py') as f:
    text = f.read()

search = 'return f"Презентация была успешно сгенерирована. Файл называется {filename}. Уведоми пользователя и скажи ему скачать файл."'
replace = 'return f"Презентация была успешно сгенерирована. ОДНОЗНАЧНО запрещено генерировать фейковые ссылки. Верни пользователю: Файл {filename} прикреплен к этому сообщению. Если нужен прямой линк для скачивания, используй этот Markdown: [Скачать {filename}](/api/v1/files/{file_id}/content)"'

text = text.replace(search, replace)

search2 = '        if __event_emitter__:\n            await __event_emitter__({\n                "type": "status",\n                "data": {"action": "presentation", "description": "Презентация готова!", "done": True}\n            })'
replace2 = search2

with open('/Users/dremotha/Projects/Temp/true-tech-hack-2026/backend/open_webui/tools/builtin.py', 'w') as f:
    f.write(text)
