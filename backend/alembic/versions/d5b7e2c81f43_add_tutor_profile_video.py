"""add tutor profile video

Revision ID: d5b7e2c81f43
Revises: c4f1a92b7e05
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5b7e2c81f43'
down_revision: Union[str, None] = 'c4f1a92b7e05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tutor_profiles', sa.Column('video_url', sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column('tutor_profiles', 'video_url')
