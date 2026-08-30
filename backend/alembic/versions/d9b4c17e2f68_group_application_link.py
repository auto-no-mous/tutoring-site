"""group application notification: link to the groups tab

Revision ID: d9b4c17e2f68
Revises: c7d2e91a4b60
Create Date: 2026-08-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9b4c17e2f68'
down_revision: Union[str, None] = 'c7d2e91a4b60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Шаблоны засеваются один раз (ensure_default_templates только добавляет
# недостающие), поэтому правка DEFAULT_TEMPLATES сама по себе до существующей базы не
# доедет. Обновляем по точному совпадению с прежним текстом: если админ правил шаблон
# в интерфейсе, его версия остаётся нетронутой.

OLD_BODY = (
    "{student_name} подал(а) заявку на участие в группе «{group_name}». "
    "Рассмотрите её во вкладке «Группы»."
)

NEW_BODY = (
    "{student_name} подал(а) заявку на участие в группе «{group_name}». "
    "Принять или отклонить её можно во вкладке «Группы» — заявка ждёт вверху "
    "страницы: {groups_url}"
)


def _swap(old: str, new: str) -> None:
    op.execute(
        sa.text(
            "UPDATE notification_templates SET body = :new "
            "WHERE event_type = 'group_application_received' AND role = 'tutor' AND body = :old"
        ).bindparams(new=new, old=old)
    )


def upgrade() -> None:
    _swap(OLD_BODY, NEW_BODY)


def downgrade() -> None:
    _swap(NEW_BODY, OLD_BODY)
