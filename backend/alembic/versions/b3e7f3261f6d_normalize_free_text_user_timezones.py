"""normalize free-text user timezones

Revision ID: b3e7f3261f6d
Revises: 51030c63dcc1
Create Date: 2026-09-15 09:46:30.225068

"""
from typing import Sequence, Union
from zoneinfo import available_timezones

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3e7f3261f6d'
down_revision: Union[str, None] = '51030c63dcc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Что имели в виду те, кто вписывал город руками. Список короткий намеренно: это
# разовая чистка того, что реально оказалось в базе, а не справочник городов.
_GUESSES = {
    'Chelyabinsk': 'Asia/Yekaterinburg',
    'Челябинск': 'Asia/Yekaterinburg',
    'Yekaterinburg': 'Asia/Yekaterinburg',
    'Екатеринбург': 'Asia/Yekaterinburg',
    'Москва': 'Europe/Moscow',
    'Moscow': 'Europe/Moscow',
    'MSK': 'Europe/Moscow',
    'МСК': 'Europe/Moscow',
}
_FALLBACK = 'Europe/Moscow'

_users = sa.table('users', sa.column('id', sa.Uuid()), sa.column('timezone', sa.String()))


def upgrade() -> None:
    """Поле часового пояса было свободным текстом и ни на что не влияло, поэтому в нём
    осели значения вроде "Chelyabinsk". Теперь по нему считается разница с Москвой -
    и всё, что не является именем зоны IANA, надо привести в порядок один раз."""
    conn = op.get_bind()
    known = available_timezones()
    rows = conn.execute(sa.select(_users.c.id, _users.c.timezone)).fetchall()
    for row in rows:
        if row.timezone in known:
            continue
        replacement = _GUESSES.get((row.timezone or '').strip(), _FALLBACK)
        conn.execute(_users.update().where(_users.c.id == row.id).values(timezone=replacement))


def downgrade() -> None:
    # Исходный текст не сохранён: он и был мусором, восстанавливать нечего.
    pass
