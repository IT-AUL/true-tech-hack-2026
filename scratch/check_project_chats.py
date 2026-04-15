from open_webui.internal.db import SessionLocal
from open_webui.models.chats import Chat
from sqlalchemy import select

def check_project_chats():
    db = SessionLocal()
    try:
        # Проверяем чаты, у которых есть project_id
        stmt = select(Chat).where(Chat.project_id.isnot(None))
        result = db.execute(stmt).scalars().all()
        print(f"Found {len(result)} chats linked to projects.")
        for chat in result:
            print(f"- Chat ID: {chat.id}, Project ID: {chat.project_id}, Title: {chat.title}")
    finally:
        db.close()

if __name__ == "__main__":
    check_project_chats()
