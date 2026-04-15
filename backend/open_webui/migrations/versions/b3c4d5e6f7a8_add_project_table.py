"""Add project table and project_id column to chat

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-14 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from open_webui.migrations.util import get_existing_tables

revision: str = 'b3c4d5e6f7a8'
down_revision: str | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    # 1. Create project table
    if 'project' not in existing_tables:
        op.create_table(
            'project',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('title', sa.Text(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('meta', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('idx_project_user_id', 'project', ['user_id'])
        op.create_index('idx_project_updated_at', 'project', ['updated_at'])

    # 2. Add project_id column to chat table (nullable, so existing chats are unaffected)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('chat')]
    if 'project_id' not in existing_columns:
        op.add_column(
            'chat',
            sa.Column('project_id', sa.String(), nullable=True),
        )
        op.create_index('idx_chat_project_id', 'chat', ['project_id'])


def downgrade() -> None:
    op.drop_index('idx_chat_project_id', table_name='chat')
    op.drop_column('chat', 'project_id')

    op.drop_index('idx_project_updated_at', table_name='project')
    op.drop_index('idx_project_user_id', table_name='project')
    op.drop_table('project')
