"""tutor_student_notes -> tutor_student_settings with a permanent meeting link

Revision ID: f3a91c74e5d2
Revises: a4e8c15f9b73
Create Date: 2026-09-06 10:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a91c74e5d2'
down_revision: Union[str, None] = 'a4e8c15f9b73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Лёгкие описания таблиц для переноса данных: нужны типы (sa.Uuid по-разному лежит в
# SQLite и PostgreSQL), а не отражение реальной схемы.
_settings = sa.table(
    'tutor_student_settings',
    sa.column('id', sa.Uuid()),
    sa.column('tutor_id', sa.Uuid()),
    sa.column('student_id', sa.Uuid()),
    sa.column('note', sa.Text()),
    sa.column('meeting_link', sa.String()),
    sa.column('updated_at', sa.DateTime(timezone=True)),
)
_bookings = sa.table(
    'bookings',
    sa.column('tutor_id', sa.Uuid()),
    sa.column('student_id', sa.Uuid()),
    sa.column('meeting_link', sa.String()),
    sa.column('start_at', sa.DateTime(timezone=True)),
    sa.column('status', sa.String()),
)


def upgrade() -> None:
    # Таблица была только про заметки, теперь это общие настройки пары: к заметке
    # добавляется постоянная ссылка на занятие. Переименование, а не новая таблица -
    # заметки надо сохранить, а две почти одинаковые таблицы про одну и ту же пару
    # только путали бы.
    op.rename_table('tutor_student_notes', 'tutor_student_settings')

    # batch: SQLite не умеет переименовывать колонку и менять nullable через ALTER.
    with op.batch_alter_table('tutor_student_settings') as batch:
        batch.alter_column('text', new_column_name='note', existing_type=sa.Text(), nullable=True)
        batch.add_column(sa.Column('meeting_link', sa.String(length=512), nullable=True))

    # Переносим то, что уже проставлено «постоянной» ссылкой: берём её из последнего
    # запланированного занятия пары. Иначе репетиторам пришлось бы включать опцию
    # заново - а именно от этого и избавляемся.
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(_bookings.c.tutor_id, _bookings.c.student_id, _bookings.c.meeting_link)
        .where(
            _bookings.c.student_id.isnot(None),
            _bookings.c.meeting_link.isnot(None),
            _bookings.c.status == 'scheduled',
        )
        .order_by(_bookings.c.start_at)
    ).fetchall()
    # Более позднее занятие затирает более раннее - остаётся самая свежая ссылка пары.
    links = {(row.tutor_id, row.student_id): row.meeting_link for row in rows}

    existing = {
        (row.tutor_id, row.student_id): row.id
        for row in conn.execute(
            sa.select(_settings.c.id, _settings.c.tutor_id, _settings.c.student_id)
        ).fetchall()
    }

    now = sa.func.now()
    for (tutor_id, student_id), link in links.items():
        settings_id = existing.get((tutor_id, student_id))
        if settings_id is None:
            conn.execute(
                _settings.insert().values(
                    id=uuid.uuid4(),
                    tutor_id=tutor_id,
                    student_id=student_id,
                    note=None,
                    meeting_link=link,
                    updated_at=now,
                )
            )
        else:
            conn.execute(
                _settings.update().where(_settings.c.id == settings_id).values(meeting_link=link)
            )


def downgrade() -> None:
    # Строки, заведённые только ради ссылки, в «заметках» смысла не имеют: там note
    # обязателен.
    op.execute(sa.text("DELETE FROM tutor_student_settings WHERE note IS NULL"))
    with op.batch_alter_table('tutor_student_settings') as batch:
        batch.drop_column('meeting_link')
        batch.alter_column('note', new_column_name='text', existing_type=sa.Text(), nullable=False)
    op.rename_table('tutor_student_settings', 'tutor_student_notes')
