"""add email log

Revision ID: e3b1c8d94a52
Revises: 5f2a9c7e6b41
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3b1c8d94a52'
down_revision: Union[str, None] = '5f2a9c7e6b41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('direction', sa.String(length=8), nullable=False),
        sa.Column('kind', sa.String(length=24), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('address_from', sa.String(length=320), nullable=False),
        sa.Column('address_to', sa.String(length=320), nullable=False),
        sa.Column('subject', sa.String(length=512), nullable=False),
        sa.Column('body_preview', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('sent_by_id', sa.Uuid(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sent_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_email_log_direction'), 'email_log', ['direction'])
    op.create_index(op.f('ix_email_log_kind'), 'email_log', ['kind'])
    op.create_index(op.f('ix_email_log_status'), 'email_log', ['status'])
    op.create_index(op.f('ix_email_log_address_to'), 'email_log', ['address_to'])
    op.create_index(op.f('ix_email_log_user_id'), 'email_log', ['user_id'])
    op.create_index(op.f('ix_email_log_created_at'), 'email_log', ['created_at'])


def downgrade() -> None:
    op.drop_index(op.f('ix_email_log_created_at'), table_name='email_log')
    op.drop_index(op.f('ix_email_log_user_id'), table_name='email_log')
    op.drop_index(op.f('ix_email_log_address_to'), table_name='email_log')
    op.drop_index(op.f('ix_email_log_status'), table_name='email_log')
    op.drop_index(op.f('ix_email_log_kind'), table_name='email_log')
    op.drop_index(op.f('ix_email_log_direction'), table_name='email_log')
    op.drop_table('email_log')
