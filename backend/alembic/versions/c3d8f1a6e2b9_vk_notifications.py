"""users: VK notifications - who to message and the pending link code

Revision ID: c3d8f1a6e2b9
Revises: a7c3e5f19b2d
Create Date: 2026-11-11 16:22:59.831479

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d8f1a6e2b9'
down_revision: Union[str, None] = 'a7c3e5f19b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('vk_peer_id', sa.String(length=32), nullable=True))
        batch.add_column(sa.Column('vk_link_token', sa.String(length=32), nullable=True))
        batch.add_column(sa.Column('vk_link_token_expires_at', sa.DateTime(timezone=True), nullable=True))
        batch.create_index(batch.f('ix_users_vk_link_token'), ['vk_link_token'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_index(batch.f('ix_users_vk_link_token'))
        batch.drop_column('vk_link_token_expires_at')
        batch.drop_column('vk_link_token')
        batch.drop_column('vk_peer_id')
