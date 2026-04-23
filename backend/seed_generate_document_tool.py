"""
Script: seed_generate_document_tool.py
Registers the 'generate_document' tool in the Open WebUI database.
Run this INSIDE the gpthub Docker container:
  docker exec -it gpthub python /app/backend/seed_generate_document_tool.py
"""

import os
import sys

# Ensure the backend is on the path
sys.path.insert(0, '/app/backend')
os.environ.setdefault('DATABASE_URL', 'sqlite:////app/backend/data/webui.db')
os.environ.setdefault('DATA_DIR', '/app/backend/data')
os.environ.setdefault('ENABLE_DB_MIGRATIONS', 'False')
os.environ.setdefault('WEBUI_SECRET_KEY', 'seed-script')

TOOL_ID = 'generate_document'
TOOL_NAME = 'Генерация документов'

TOOL_CODE = '''\
"""
title: Генерация документов
author: system
description: Генерирует файлы DOCX, XLSX, PDF, TXT, MD по запросу пользователя.
version: 1.0.0
license: MIT
"""

import io
import json
import logging
import uuid
from typing import Any

log = logging.getLogger(__name__)


class Tools:
    async def generate_document(
        self,
        content: str,
        filename: str,
        format: str,
        __request__: Any = None,
        __user__: dict = None,
        __event_emitter__=None,
        __chat_id__: str = None,
        __message_id__: str = None,
    ) -> str:
        """
        Generate and save a document (DOCX, XLSX, PDF, TXT or MD).
        Use this whenever the user asks to create, save, or export a file.

        :param content: The full text/markdown content for the document.
        :param filename: Desired file name WITHOUT extension (e.g. "report").
        :param format: File format – one of: docx, xlsx, pdf, txt, md.
        :return: JSON string confirming success and providing the file id.
        """
        from open_webui.models.files import Files, FileForm
        from open_webui.models.chats import Chats
        from open_webui.storage.provider import Storage
        from open_webui.utils import document_generator

        if __request__ is None:
            return json.dumps({"error": "Request context not available"})

        fmt = format.lower().strip(".")
        if fmt not in ["docx", "xlsx", "pdf", "txt", "md"]:
            return json.dumps({"error": f"Unsupported format: {format}. Use one of: docx, xlsx, pdf, txt, md"})

        try:
            messages = [document_generator.MessageItem(role="assistant", content=content)]
            file_bytes = document_generator.generate_document_by_format(fmt, filename, messages)

            file_id = str(uuid.uuid4())
            full_filename = f"{filename}.{fmt}"

            media_types = {
                "txt": "text/plain",
                "md": "text/markdown",
                "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
            content_type = media_types.get(fmt, "application/octet-stream")

            _, file_path = Storage.upload_file(
                io.BytesIO(file_bytes), full_filename, {"content_type": content_type}
            )

            user_id = (__user__ or {}).get("id", "system")
            file_item = Files.insert_new_file(
                user_id,
                FileForm(
                    id=file_id,
                    filename=full_filename,
                    path=file_path,
                    meta={"content_type": content_type, "size": len(file_bytes)},
                ),
            )

            if not file_item:
                return json.dumps({"error": "Failed to register file in database"})

            file_data = {
                "id": file_id,
                "name": full_filename,
                "type": "file",
                "url": f"/api/v1/files/{file_id}/content",
            }

            if __chat_id__ and __message_id__:
                Chats.add_message_files_by_id_and_message_id(__chat_id__, __message_id__, [file_data])

            if __event_emitter__:
                await __event_emitter__({"type": "chat:message:files", "data": {"files": [file_data]}})
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": f"✅ Файл {full_filename} создан", "done": True},
                    }
                )

            return json.dumps(
                {
                    "status": "success",
                    "message": f"Document '{full_filename}' created. The user can now download it from the chat.",
                    "file_id": file_id,
                },
                ensure_ascii=False,
            )

        except Exception as e:
            log.exception(f"generate_document error: {e}")
            return json.dumps({"error": str(e)})
'''

TOOL_SPECS = [
    {
        'name': 'generate_document',
        'description': (
            'Generate and save a document (DOCX, XLSX, PDF, TXT or MD). '
            'Use this whenever the user asks to create, save, or export a file.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'content': {
                    'type': 'string',
                    'description': 'The full text/markdown content for the document.',
                },
                'filename': {
                    'type': 'string',
                    'description': "Desired file name WITHOUT extension (e.g. 'report').",
                },
                'format': {
                    'type': 'string',
                    'enum': ['docx', 'xlsx', 'pdf', 'txt', 'md'],
                    'description': 'File format.',
                },
            },
            'required': ['content', 'filename', 'format'],
        },
    }
]


def main():
    from open_webui.models.tools import ToolForm, ToolMeta, Tools
    from open_webui.models.users import Users

    # Find the first admin user
    admin_user = None
    all_users = Users.get_users()
    for user in all_users:
        if hasattr(user, 'role') and user.role == 'admin':
            admin_user = user
            break
        elif isinstance(user, dict) and user.get('role') == 'admin':
            admin_user = Users.get_user_by_id(user['id'])
            break

    if not admin_user:
        print('❌ No admin user found. Create an admin account first.')
        sys.exit(1)

    print(f'✅ Using admin user: {admin_user.email} ({admin_user.id})')

    # Check if tool already exists
    existing = Tools.get_tool_by_id(TOOL_ID)
    if existing:
        print(f"⚠️  Tool '{TOOL_ID}' already exists. Updating...")
        Tools.update_tool_by_id(
            TOOL_ID,
            {
                'name': TOOL_NAME,
                'content': TOOL_CODE,
                'specs': TOOL_SPECS,
                'meta': {'description': 'Генерирует DOCX, XLSX, PDF, TXT, MD документы.'},
            },
        )
        print(f"✅ Tool '{TOOL_ID}' updated successfully!")
    else:
        form = ToolForm(
            id=TOOL_ID,
            name=TOOL_NAME,
            content=TOOL_CODE,
            meta=ToolMeta(description='Генерирует DOCX, XLSX, PDF, TXT, MD документы.'),
        )
        result = Tools.insert_new_tool(admin_user.id, form, TOOL_SPECS)
        if result:
            print(f"✅ Tool '{TOOL_ID}' registered successfully!")
            print('   → Go to Workspace → Tools in Open WebUI to see it.')
            print('   → Attach it to a model or enable it in a chat to use it.')
        else:
            print(f"❌ Failed to register tool '{TOOL_ID}'.")
            sys.exit(1)


if __name__ == '__main__':
    main()
