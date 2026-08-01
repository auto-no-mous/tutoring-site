"""add grade to users, merge tutor_profiles.achievements into about

Revision ID: c1a5f7e2b3d4
Revises: afaef8f1e8f1
Create Date: 2026-07-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a5f7e2b3d4'
down_revision: Union[str, None] = 'afaef8f1e8f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('grade', sa.Integer(), nullable=True))

    conn = op.get_bind()
    tutor_profiles = sa.table(
        'tutor_profiles',
        sa.column('id', sa.Uuid()),
        sa.column('about', sa.Text()),
        sa.column('achievements', sa.Text()),
    )
    rows = conn.execute(sa.select(tutor_profiles.c.id, tutor_profiles.c.about, tutor_profiles.c.achievements)).fetchall()
    for row in rows:
        if row.achievements:
            merged = f"{row.about}\n\n{row.achievements}" if row.about else row.achievements
            conn.execute(tutor_profiles.update().where(tutor_profiles.c.id == row.id).values(about=merged))

    op.drop_column('tutor_profiles', 'achievements')


def downgrade() -> None:
    op.add_column('tutor_profiles', sa.Column('achievements', sa.Text(), nullable=False, server_default=''))
    op.drop_column('users', 'grade')
