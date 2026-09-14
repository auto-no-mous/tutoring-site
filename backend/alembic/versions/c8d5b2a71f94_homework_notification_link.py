"""homework notification: link to the ДЗ tab

Revision ID: c8d5b2a71f94
Revises: b2c9f41d8e07
Create Date: 2026-09-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d5b2a71f94'
down_revision: Union[str, None] = 'b2c9f41d8e07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Шаблоны засеваются один раз, поэтому правка DEFAULT_TEMPLATES до существующей базы
# сама не доедет. Меняем по точному совпадению со старым текстом: правленный админом
# шаблон остаётся как есть.

OLD_BODY = (
    "Репетитор задал новое домашнее задание: «{homework_title}». Посмотреть его можно "
    "во вкладке «Домашние задания»."
)

NEW_BODY = (
    "Репетитор задал новое домашнее задание: «{homework_title}». Открыть и сдать "
    "его можно во вкладке «ДЗ»: {homework_url}"
)


def _swap(old: str, new: str) -> None:
    op.execute(
        sa.text(
            "UPDATE notification_templates SET body = :new "
            "WHERE event_type = 'homework_assigned' AND role = 'student' AND body = :old"
        ).bindparams(new=new, old=old)
    )


def upgrade() -> None:
    _swap(OLD_BODY, NEW_BODY)


def downgrade() -> None:
    _swap(NEW_BODY, OLD_BODY)
