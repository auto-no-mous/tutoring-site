"""replace email_notifications_enabled with notification_channel

Revision ID: f4c2a71b9e33
Revises: e3b1c8d94a52
Create Date: 2026-08-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4c2a71b9e33'
down_revision: Union[str, None] = 'e3b1c8d94a52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('notification_channel', sa.String(length=16), nullable=False, server_default='both'),
    )
    # Перенос прежней настройки: галочка стояла - оба канала, снята - только
    # мессенджер (почтовые уведомления пользователь отключал сознательно).
    op.execute(
        "UPDATE users SET notification_channel = CASE "
        "WHEN email_notifications_enabled THEN 'both' ELSE 'telegram' END"
    )
    op.drop_column('users', 'email_notifications_enabled')


def downgrade() -> None:
    op.add_column(
        'users',
        sa.Column('email_notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.execute(
        "UPDATE users SET email_notifications_enabled = CASE "
        "WHEN notification_channel IN ('email', 'both') THEN true ELSE false END"
    )
    op.drop_column('users', 'notification_channel')
