"""add users.photo_url

Revision ID: c7d2e91a4b60
Revises: b6f0d41c7a92
Create Date: 2026-08-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d2e91a4b60'
down_revision: Union[str, None] = 'b6f0d41c7a92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('photo_url', sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'photo_url')
