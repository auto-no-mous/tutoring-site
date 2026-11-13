"""blog_posts: database defaults for created_at/updated_at

Revision ID: e5f0b3c8a2d4
Revises: d4e9a2b7c1f3
Create Date: 2026-11-13 19:57:11.388891

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f0b3c8a2d4'
down_revision: Union[str, None] = 'd4e9a2b7c1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Модель (TimestampMixin) рассчитывает, что даты подставит база, а миграция
    # b8d3f60a2c19 создала колонки без значения по умолчанию - на PostgreSQL
    # сохранение любой статьи падало с NOT NULL ("Не удалось сохранить статью").
    with op.batch_alter_table('blog_posts') as batch:
        batch.alter_column(
            'created_at', existing_type=sa.DateTime(timezone=True), existing_nullable=False, server_default=sa.func.now()
        )
        batch.alter_column(
            'updated_at', existing_type=sa.DateTime(timezone=True), existing_nullable=False, server_default=sa.func.now()
        )


def downgrade() -> None:
    with op.batch_alter_table('blog_posts') as batch:
        batch.alter_column('created_at', existing_type=sa.DateTime(timezone=True), existing_nullable=False, server_default=None)
        batch.alter_column('updated_at', existing_type=sa.DateTime(timezone=True), existing_nullable=False, server_default=None)
