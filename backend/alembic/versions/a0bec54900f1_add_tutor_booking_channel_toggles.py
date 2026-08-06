"""add tutor booking channel toggles

Revision ID: a0bec54900f1
Revises: 3800f545b9fe
Create Date: 2026-08-03 18:32:59.943028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0bec54900f1'
down_revision: Union[str, None] = '3800f545b9fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tutor_profiles', sa.Column('allow_individual_bookings', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('tutor_profiles', sa.Column('allow_group_bookings', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column('tutor_profiles', 'allow_group_bookings')
    op.drop_column('tutor_profiles', 'allow_individual_bookings')
