"""recurring series: a series that never got a second week is not weekly

Revision ID: a7c3e5f19b2d
Revises: 9e4d2b7a1c35
Create Date: 2026-11-05 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e5f19b2d'
down_revision: Union[str, None] = '9e4d2b7a1c35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_series = sa.table(
    'recurring_series',
    sa.column('id', sa.Uuid()),
    sa.column('is_active', sa.Boolean()),
    sa.column('stopped_at', sa.DateTime(timezone=True)),
)
_bookings = sa.table(
    'bookings',
    sa.column('id', sa.Uuid()),
    sa.column('recurring_series_id', sa.Uuid()),
)


def upgrade() -> None:
    # Галочка «еженедельно», при которой ни одна следующая неделя не нашлась, всё
    # равно создавала серию, и её единственное занятие числилось еженедельным - в
    # расписании и во вкладке «Ученики». Теперь такая серия сразу выключается
    # (booking_service._after_series_created); здесь - те, что остались с прошлых
    # релизов. Серия создаёт недели сразу при включении, так что одно занятие за всю
    # жизнь значит, что повтора не было ни разу.
    conn = op.get_bind()
    lonely = conn.execute(
        sa.select(_series.c.id)
        .select_from(_series.join(_bookings, _bookings.c.recurring_series_id == _series.c.id))
        .where(_series.c.is_active.is_(True))
        .group_by(_series.c.id)
        .having(sa.func.count(_bookings.c.id) == 1)
    ).scalars().all()
    if not lonely:
        return
    conn.execute(
        _bookings.update().where(_bookings.c.recurring_series_id.in_(lonely)).values(recurring_series_id=None)
    )
    conn.execute(
        _series.update().where(_series.c.id.in_(lonely)).values(is_active=False, stopped_at=sa.func.now())
    )


def downgrade() -> None:
    # Какое занятие было в какой серии, после upgrade уже не восстановить, да и
    # возвращать серии-однодневки незачем.
    pass
