"""add tutor social links

Revision ID: 5f2a9c7e6b41
Revises: 41847be334d7
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f2a9c7e6b41'
down_revision: Union[str, None] = '41847be334d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tutor_profiles', sa.Column('telegram_url', sa.String(length=512), nullable=True))
    op.add_column('tutor_profiles', sa.Column('vk_url', sa.String(length=512), nullable=True))
    op.add_column('tutor_profiles', sa.Column('youtube_url', sa.String(length=512), nullable=True))
    op.add_column(
        'tutor_profiles',
        sa.Column('extra_links', sa.JSON(), nullable=False, server_default='[]'),
    )


def downgrade() -> None:
    op.drop_column('tutor_profiles', 'extra_links')
    op.drop_column('tutor_profiles', 'youtube_url')
    op.drop_column('tutor_profiles', 'vk_url')
    op.drop_column('tutor_profiles', 'telegram_url')
