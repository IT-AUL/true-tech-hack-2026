from open_webui.internal.db import engine
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()
print(f'Tables: {tables}')

if 'project' in tables:
    print('Project table exists.')
    columns = [c['name'] for c in inspector.get_columns('project')]
    print(f'Project columns: {columns}')
else:
    print('Project table MISSING.')

if 'chat' in tables:
    columns = [c['name'] for c in inspector.get_columns('chat')]
    print(f'Chat columns: {columns}')
    if 'project_id' in columns:
        print('chat.project_id exists.')
    else:
        print('chat.project_id MISSING.')
