"""add telegram link token to users

Revision ID: 7aca467e39e3
Revises: d2e6a9c4f1b7
Create Date: 2026-07-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7aca467e39e3'
down_revision: Union[str, None] = 'd2e6a9c4f1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('telegram_link_token', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('telegram_link_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_users_telegram_link_token'), 'users', ['telegram_link_token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_telegram_link_token'), table_name='users')
    op.drop_column('users', 'telegram_link_token_expires_at')
    op.drop_column('users', 'telegram_link_token')
