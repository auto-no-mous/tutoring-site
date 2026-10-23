"""email_log: keep the full text of each email

Revision ID: 3c59e2ed4a4b
Revises: ad6ea770ef16
Create Date: 2026-10-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c59e2ed4a4b'
down_revision: Union[str, None] = 'ad6ea770ef16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Пусто у прежних записей: для них сохранялось только превью (body_preview).
    op.add_column('email_log', sa.Column('body_text', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('email_log', 'body_text')
