from open_webui.internal.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text('ALTER TABLE project RENAME COLUMN name TO title'))
        conn.commit()
        print('Column project.name renamed to project.title')
    except Exception as e:
        print(f'Error renaming column: {e}')
