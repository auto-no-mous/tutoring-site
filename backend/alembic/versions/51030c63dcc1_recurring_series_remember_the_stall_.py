"""recurring series: remember the stall warning

Revision ID: 51030c63dcc1
Revises: c8d5b2a71f94
Create Date: 2026-09-14 18:30:23.087184

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51030c63dcc1'
down_revision: Union[str, None] = 'c8d5b2a71f94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Отметка о том, что репетитору уже сообщили о непродлеваемой серии: ежедневное
    # продление иначе повторяло бы одно и то же уведомление каждые сутки.
    with op.batch_alter_table('recurring_series') as batch:
        batch.add_column(sa.Column('stall_notified_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('recurring_series') as batch:
        batch.drop_column('stall_notified_at')
