"""refresh tutor welcome template

Revision ID: e7a3c15d9b28
Revises: d5b7e2c81f43
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a3c15d9b28'
down_revision: Union[str, None] = 'd5b7e2c81f43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# notification_templates rows are seeded once and never refreshed afterwards
# (system_notification_service.ensure_default_templates only inserts what's missing),
# so a wording change in DEFAULT_TEMPLATES would otherwise never reach a database that
# already has the row. Both statements below match on the exact previous text, which
# means an admin who edited the template in the UI keeps their own version.

OLD_TUTOR_BODY = (
    "Добро пожаловать, {name}! Ваш профиль репетитора создан. Заполните раздел «Профиль» "
    "и настройте расписание во вкладке «Расписание», чтобы ученики могли записываться на занятия."
)

NEW_TUTOR_BODY = (
    "Добро пожаловать, {name}! Ваш профиль репетитора создан. Заполните раздел «Профиль» "
    "и настройте расписание во вкладке «Расписание», чтобы ученики могли записываться на занятия.\n\n"
    "Важно: my-tutor.ru — это прежде всего инструмент для ведения занятий: расписание, группы, "
    "домашние задания, напоминания и чат. Каталог сайта пока не продвигается среди учеников, "
    "поэтому просто ждать заявок из него не стоит. Разместите ссылку на свою страницу там, где вас "
    "уже находят, — в соцсетях, мессенджерах, объявлениях: ученик откроет её, увидит ваше "
    "расписание и запишется сам. Адрес страницы настраивается в разделе «Профиль»."
)

# Seeded before the rebrand and left behind by it (v0.5.0 renamed the site) - the
# titles still greet new users with the old domain.
OLD_TITLE = "Добро пожаловать на it-tutor.pro"
NEW_TITLE = "Добро пожаловать на my-tutor.ru"


def _update(column: str, old: str, new: str, role: str) -> None:
    op.execute(
        sa.text(
            f"UPDATE notification_templates SET {column} = :new "  # noqa: S608 - column is a literal above
            "WHERE event_type = 'welcome' AND role = :role AND " + column + " = :old"
        ).bindparams(new=new, old=old, role=role)
    )


def upgrade() -> None:
    _update("body", OLD_TUTOR_BODY, NEW_TUTOR_BODY, "tutor")
    for role in ("tutor", "student"):
        _update("title", OLD_TITLE, NEW_TITLE, role)


def downgrade() -> None:
    _update("body", NEW_TUTOR_BODY, OLD_TUTOR_BODY, "tutor")
    for role in ("tutor", "student"):
        _update("title", NEW_TITLE, OLD_TITLE, role)
