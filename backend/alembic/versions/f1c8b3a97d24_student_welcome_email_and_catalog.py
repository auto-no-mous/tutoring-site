"""student welcome: confirm email reminder and catalog link

Revision ID: f1c8b3a97d24
Revises: e7a3c15d9b28
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1c8b3a97d24'
down_revision: Union[str, None] = 'e7a3c15d9b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Строки notification_templates засеваются один раз и потом не обновляются
# (ensure_default_templates только добавляет недостающие), поэтому правка текста в
# DEFAULT_TEMPLATES сама по себе до существующей базы не доедет. Совпадение по точному
# прежнему тексту: если админ правил шаблон в интерфейсе, его версия останется.

OLD_BODY = (
    "Добро пожаловать, {name}! Теперь вы можете найти репетитора в каталоге и записаться "
    "на первое занятие."
)

NEW_BODY = (
    "Добро пожаловать, {name}! Каталог репетиторов: {catalog_url} — выбирайте преподавателя, "
    "смотрите свободное время и записывайтесь на первое занятие.\n\n"
    "И подтвердите, пожалуйста, почту: мы отправили письмо со ссылкой на указанный при "
    "регистрации адрес. Без подтверждения не будут приходить напоминания о занятиях и "
    "письмо для восстановления пароля. Если письмо не пришло, запросите новое в «Настройках»."
)


def _swap(old: str, new: str) -> None:
    op.execute(
        sa.text(
            "UPDATE notification_templates SET body = :new "
            "WHERE event_type = 'welcome' AND role = 'student' AND body = :old"
        ).bindparams(new=new, old=old)
    )


def upgrade() -> None:
    _swap(OLD_BODY, NEW_BODY)


def downgrade() -> None:
    _swap(NEW_BODY, OLD_BODY)
