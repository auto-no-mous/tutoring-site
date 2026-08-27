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


def upgrade() -> None:
    # ondelete CASCADE -> SET NULL: deleting a group must leave its chat thread intact
    # (see services/group_service.py::delete_group), only detached from the group.
    with op.batch_alter_table('chat_threads', naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.add_column(sa.Column('archived_group_name', sa.String(length=255), nullable=True))
        batch_op.drop_constraint(GROUP_FK, type_='foreignkey')
        batch_op.create_foreign_key(GROUP_FK, 'groups', ['group_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('chat_threads', naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint(GROUP_FK, type_='foreignkey')
        batch_op.create_foreign_key(GROUP_FK, 'groups', ['group_id'], ['id'], ondelete='CASCADE')
        batch_op.drop_column('archived_group_name')
