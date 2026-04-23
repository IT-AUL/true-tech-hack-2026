"""
title: Generate Document
author: system
description: Generates DOCX, XLSX, PDF, TXT, MD documents on request. Use when user asks to create, save or export a file.
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
