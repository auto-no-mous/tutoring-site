"""support chat: users.is_support, support threads without a tutor

Revision ID: d4e9a2b7c1f3
Revises: c3d8f1a6e2b9
Create Date: 2026-11-13 12:57:46.874615

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e9a2b7c1f3'
down_revision: Union[str, None] = 'c3d8f1a6e2b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('is_support', sa.Boolean(), nullable=False, server_default=sa.false()))
    # Обращение в поддержку не привязано к репетитору.
    with op.batch_alter_table('chat_threads') as batch:
        batch.alter_column('tutor_id', existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    # Обращения в поддержку живут только с tutor_id = NULL - при откате их некуда деть.
    op.execute("DELETE FROM chat_threads WHERE type = 'support'")
    with op.batch_alter_table('chat_threads') as batch:
        batch.alter_column('tutor_id', existing_type=sa.Uuid(), nullable=False)
    with op.batch_alter_table('users') as batch:
        batch.drop_column('is_support')
