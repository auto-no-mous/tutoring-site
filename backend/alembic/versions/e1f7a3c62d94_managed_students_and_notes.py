"""managed students: owner flag, claim token, tutor notes

Revision ID: e1f7a3c62d94
Revises: d9b4c17e2f68
Create Date: 2026-08-30 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f7a3c62d94'
down_revision: Union[str, None] = 'd9b4c17e2f68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite не умеет добавлять колонку с внешним ключом через ALTER TABLE, поэтому
    # batch-режим: alembic пересоберёт таблицу с нужным ограничением.
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('managed_by_tutor_id', sa.Uuid(), nullable=True))
        batch.add_column(sa.Column('claim_token', sa.String(length=64), nullable=True))
        batch.add_column(sa.Column('claim_token_expires_at', sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            'fk_users_managed_by_tutor_id', 'tutor_profiles', ['managed_by_tutor_id'], ['id'], ondelete='CASCADE'
        )
    op.create_index(op.f('ix_users_managed_by_tutor_id'), 'users', ['managed_by_tutor_id'], unique=False)
    op.create_index(op.f('ix_users_claim_token'), 'users', ['claim_token'], unique=True)

    op.create_table(
        'tutor_student_notes',
        sa.Column('tutor_id', sa.Uuid(), nullable=False),
        sa.Column('student_id', sa.Uuid(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['tutor_id'], ['tutor_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tutor_id', 'student_id', name='uq_tutor_student_notes_pair'),
    )
    op.create_index(op.f('ix_tutor_student_notes_tutor_id'), 'tutor_student_notes', ['tutor_id'], unique=False)
    op.create_index(op.f('ix_tutor_student_notes_student_id'), 'tutor_student_notes', ['student_id'], unique=False)

    # Поток привязки через VK/Яндекс идёт тем же путём, что и привязка провайдера из
    # настроек, но авторизуется токеном из ссылки, а не сессией - отсюда отдельный флаг.
    op.add_column('oauth_states', sa.Column('is_claim', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('oauth_states', 'is_claim')
    op.drop_index(op.f('ix_tutor_student_notes_student_id'), table_name='tutor_student_notes')
    op.drop_index(op.f('ix_tutor_student_notes_tutor_id'), table_name='tutor_student_notes')
    op.drop_table('tutor_student_notes')
    op.drop_index(op.f('ix_users_claim_token'), table_name='users')
    op.drop_index(op.f('ix_users_managed_by_tutor_id'), table_name='users')
    with op.batch_alter_table('users') as batch:
        batch.drop_constraint('fk_users_managed_by_tutor_id', type_='foreignkey')
        batch.drop_column('claim_token_expires_at')
        batch.drop_column('claim_token')
        batch.drop_column('managed_by_tutor_id')
