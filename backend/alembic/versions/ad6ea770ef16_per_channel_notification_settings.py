"""per-channel notification settings and per-channel reminder tracking

Revision ID: ad6ea770ef16
Revises: b3e7f3261f6d
Create Date: 2026-10-20 18:00:00.000000

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad6ea770ef16'
down_revision: Union[str, None] = 'b3e7f3261f6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHANNELS = ('telegram', 'email')


def _channel(enabled: bool, lead: int) -> dict:
    return {
        'enabled': enabled,
        'new_booking': True,
        'schedule_change': True,
        'reminder': True,
        'reminder_lead_minutes': lead,
    }


def upgrade() -> None:
    op.add_column('users', sa.Column('notification_settings', sa.JSON(), nullable=False, server_default='{}'))

    # Перенос прежнего переключателя «почта / мессенджер / оба / никуда» и общего
    # «за сколько минут»: каналы включаются по нему, все события в них - как раньше.
    conn = op.get_bind()
    users = conn.execute(sa.text('SELECT id, notification_channel, reminder_lead_minutes FROM users')).all()
    for user_id, channel, lead in users:
        settings = {
            'telegram': _channel(channel in ('telegram', 'both'), lead or 60),
            'email': _channel(channel in ('email', 'both'), lead or 60),
        }
        conn.execute(
            sa.text('UPDATE users SET notification_settings = :settings WHERE id = :id'),
            {'settings': json.dumps(settings), 'id': user_id},
        )

    op.drop_column('users', 'notification_channel')
    op.drop_column('users', 'reminder_lead_minutes')

    op.create_table(
        'booking_reminders',
        sa.Column('booking_id', sa.Uuid(), sa.ForeignKey('bookings.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('channel', sa.String(length=16), primary_key=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Напоминания по ещё не прошедшим занятиям, которые уже ушли по старой схеме,
    # отмечаем отправленными во все каналы - иначе после обновления они пришли бы
    # второй раз.
    for sent_column, user_select in (
        ('reminder_sent_at', 'SELECT tp.user_id FROM tutor_profiles tp WHERE tp.id = b.tutor_id'),
        ('student_reminder_sent_at', 'SELECT b.student_id'),
    ):
        for channel in CHANNELS:
            conn.execute(
                sa.text(
                    f'INSERT INTO booking_reminders (booking_id, user_id, channel, sent_at) '
                    f'SELECT b.id, ({user_select}), :channel, b.{sent_column} FROM bookings b '
                    f'WHERE b.{sent_column} IS NOT NULL AND b.start_at > CURRENT_TIMESTAMP '
                    f'AND ({user_select}) IS NOT NULL'
                ),
                {'channel': channel},
            )


def downgrade() -> None:
    op.drop_table('booking_reminders')
    op.add_column('users', sa.Column('notification_channel', sa.String(length=16), nullable=False, server_default='both'))
    op.add_column('users', sa.Column('reminder_lead_minutes', sa.Integer(), nullable=False, server_default='60'))

    conn = op.get_bind()
    users = conn.execute(sa.text('SELECT id, notification_settings FROM users')).all()
    for user_id, raw in users:
        settings = (json.loads(raw) if isinstance(raw, str) else raw) or {}
        telegram = settings.get('telegram', {}).get('enabled', True)
        email = settings.get('email', {}).get('enabled', True)
        channel = 'both' if telegram and email else 'telegram' if telegram else 'email' if email else 'off'
        lead = settings.get('email', {}).get('reminder_lead_minutes') or settings.get('telegram', {}).get('reminder_lead_minutes') or 60
        conn.execute(
            sa.text('UPDATE users SET notification_channel = :channel, reminder_lead_minutes = :lead WHERE id = :id'),
            {'channel': channel, 'lead': lead, 'id': user_id},
        )

    op.drop_column('users', 'notification_settings')
