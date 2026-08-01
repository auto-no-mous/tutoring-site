"""add tutor profile slug

Revision ID: 3800f545b9fe
Revises: a5a62e83533e
Create Date: 2026-08-01 19:25:00.106997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3800f545b9fe'
down_revision: Union[str, None] = 'a5a62e83533e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tutor_profiles', sa.Column('slug', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_tutor_profiles_slug'), 'tutor_profiles', ['slug'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_tutor_profiles_slug'), table_name='tutor_profiles')
    op.drop_column('tutor_profiles', 'slug')
