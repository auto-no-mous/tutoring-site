"""add booking outcome, group membership left_by, group_attendances table

Revision ID: d2e6a9c4f1b7
Revises: c1a5f7e2b3d4
Create Date: 2026-07-23 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e6a9c4f1b7'
down_revision: Union[str, None] = 'c1a5f7e2b3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('outcome', sa.String(length=32), nullable=True))
    op.add_column('group_memberships', sa.Column('left_by', sa.String(length=16), nullable=True))

    op.create_table(
        'group_attendances',
        sa.Column('occurrence_id', sa.Uuid(), nullable=False),
        sa.Column('student_id', sa.Uuid(), nullable=False),
        sa.Column('outcome', sa.String(length=32), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['occurrence_id'], ['group_occurrences.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('occurrence_id', 'student_id', name='uq_group_attendance_occurrence_student'),
    )
    op.create_index(op.f('ix_group_attendances_occurrence_id'), 'group_attendances', ['occurrence_id'], unique=False)
    op.create_index(op.f('ix_group_attendances_student_id'), 'group_attendances', ['student_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_group_attendances_student_id'), table_name='group_attendances')
    op.drop_index(op.f('ix_group_attendances_occurrence_id'), table_name='group_attendances')
    op.drop_table('group_attendances')
    op.drop_column('group_memberships', 'left_by')
    op.drop_column('bookings', 'outcome')
