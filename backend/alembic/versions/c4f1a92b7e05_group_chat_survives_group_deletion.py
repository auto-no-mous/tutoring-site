"""group chat survives group deletion

Revision ID: c4f1a92b7e05
Revises: b8d3f60a2c19
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f1a92b7e05'
down_revision: Union[str, None] = 'b8d3f60a2c19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The initial schema created chat_threads' foreign keys unnamed, and SQLite can't drop
# an unnamed constraint. Batch mode applies this convention to the reflected table so
# the group_id FK gets a deterministic name to address below.
NAMING_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
GROUP_FK = "fk_chat_threads_group_id_groups"


def _existing_group_fk(bind) -> str:
    """Как ограничение называется в этой базе прямо сейчас.

    В SQLite оно безымянное, и batch-режим сам даст ему имя из NAMING_CONVENTION при
    пересборке таблицы. PostgreSQL же именует внешние ключи по-своему
    (chat_threads_group_id_fkey), batch-режим для него - обычный ALTER TABLE, и
    попытка снять ограничение по нашему имени падает с "constraint does not exist".
    Поэтому имя спрашиваем у самой базы.
    """
    if bind.dialect.name == "sqlite":
        return GROUP_FK
    for fk in sa.inspect(bind).get_foreign_keys("chat_threads"):
        if fk["referred_table"] == "groups" and fk.get("name"):
            return fk["name"]
    return GROUP_FK


def upgrade() -> None:
    # ondelete CASCADE -> SET NULL: deleting a group must leave its chat thread intact
    # (see services/group_service.py::delete_group), only detached from the group.
    existing_fk = _existing_group_fk(op.get_bind())
    with op.batch_alter_table('chat_threads', naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.add_column(sa.Column('archived_group_name', sa.String(length=255), nullable=True))
        batch_op.drop_constraint(existing_fk, type_='foreignkey')
        batch_op.create_foreign_key(GROUP_FK, 'groups', ['group_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    existing_fk = _existing_group_fk(op.get_bind())
    with op.batch_alter_table('chat_threads', naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint(existing_fk, type_='foreignkey')
        batch_op.create_foreign_key(GROUP_FK, 'groups', ['group_id'], ['id'], ondelete='CASCADE')
        batch_op.drop_column('archived_group_name')
