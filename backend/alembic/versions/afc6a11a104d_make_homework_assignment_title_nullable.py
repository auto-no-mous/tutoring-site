"""make homework assignment title nullable

Revision ID: afc6a11a104d
Revises: 812624be4c19
Create Date: 2026-08-07 21:38:19.515265

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'afc6a11a104d'
down_revision: Union[str, None] = '812624be4c19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite has no ALTER COLUMN - batch mode rebuilds the table under the hood.
    with op.batch_alter_table('homework_assignments') as batch_op:
        batch_op.alter_column('title', existing_type=sa.VARCHAR(length=255), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('homework_assignments') as batch_op:
        batch_op.alter_column('title', existing_type=sa.VARCHAR(length=255), nullable=False)
