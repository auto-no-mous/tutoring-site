"""add whiteboards

Revision ID: a4e8c15f9b73
Revises: e1f7a3c62d94
Create Date: 2026-08-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4e8c15f9b73'
down_revision: Union[str, None] = 'e1f7a3c62d94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'whiteboards',
        sa.Column('tutor_id', sa.Uuid(), nullable=False),
        sa.Column('student_id', sa.Uuid(), nullable=True),
        sa.Column('group_id', sa.Uuid(), nullable=True),
        sa.Column('url', sa.String(length=512), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['tutor_id'], ['tutor_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # Доска принадлежит либо ученику, либо группе - но не обоим и не никому.
        sa.CheckConstraint(
            "(student_id IS NOT NULL AND group_id IS NULL) "
            "OR (student_id IS NULL AND group_id IS NOT NULL)",
            name='ck_whiteboards_exactly_one_owner',
        ),
    )
    op.create_index(op.f('ix_whiteboards_tutor_id'), 'whiteboards', ['tutor_id'], unique=False)
    op.create_index(op.f('ix_whiteboards_student_id'), 'whiteboards', ['student_id'], unique=False)
    op.create_index(op.f('ix_whiteboards_group_id'), 'whiteboards', ['group_id'], unique=False)
    op.create_index(op.f('ix_whiteboards_last_used_at'), 'whiteboards', ['last_used_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_whiteboards_last_used_at'), table_name='whiteboards')
    op.drop_index(op.f('ix_whiteboards_group_id'), table_name='whiteboards')
    op.drop_index(op.f('ix_whiteboards_student_id'), table_name='whiteboards')
    op.drop_index(op.f('ix_whiteboards_tutor_id'), table_name='whiteboards')
    op.drop_table('whiteboards')
