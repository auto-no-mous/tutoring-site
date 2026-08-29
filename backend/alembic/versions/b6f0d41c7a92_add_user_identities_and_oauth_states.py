"""add user_identities and oauth_states, drop users.vk_id

Revision ID: b6f0d41c7a92
Revises: f1c8b3a97d24
Create Date: 2026-08-29 12:00:00.000000

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6f0d41c7a92'
down_revision: Union[str, None] = 'f1c8b3a97d24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Лёгкие описания таблиц для переноса данных: нужны именно типы (sa.Uuid в SQLite -
# это CHAR(32) без дефисов), чтобы значения записались в том же виде, в каком их
# читает приложение.
_users = sa.table(
    'users',
    sa.column('id', sa.Uuid()),
    sa.column('vk_id', sa.String()),
    sa.column('email', sa.String()),
)
_identities = sa.table(
    'user_identities',
    sa.column('id', sa.Uuid()),
    sa.column('user_id', sa.Uuid()),
    sa.column('provider', sa.String()),
    sa.column('provider_user_id', sa.String()),
    sa.column('email', sa.String()),
    sa.column('created_at', sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.create_table(
        'user_identities',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('provider', sa.String(length=16), nullable=False),
        sa.Column('provider_user_id', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_user_id', name='uq_user_identities_provider_user'),
    )
    op.create_index(op.f('ix_user_identities_user_id'), 'user_identities', ['user_id'], unique=False)

    op.create_table(
        'oauth_states',
        sa.Column('state', sa.String(length=64), nullable=False),
        sa.Column('provider', sa.String(length=16), nullable=False),
        sa.Column('code_verifier', sa.String(length=128), nullable=False),
        sa.Column('redirect_to', sa.String(length=512), nullable=True),
        sa.Column('link_user_id', sa.Uuid(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['link_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_oauth_states_state'), 'oauth_states', ['state'], unique=True)

    # Переносим прежние VK-привязки. Их, скорее всего, нет (вход через VK жил только
    # в API и не был выведен в интерфейс), но миграция обязана быть корректной и на
    # базе, где они есть.
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(_users.c.id, _users.c.vk_id, _users.c.email).where(_users.c.vk_id.isnot(None))
    ).fetchall()
    if rows:
        conn.execute(
            _identities.insert(),
            [
                {
                    'id': uuid.uuid4(),
                    'user_id': row.id,
                    'provider': 'vk',
                    'provider_user_id': row.vk_id,
                    'email': row.email,
                    'created_at': datetime.now(timezone.utc),
                }
                for row in rows
            ],
        )

    # Индекс сносим отдельно и первым: SQLite отказывается удалять колонку, на которую
    # ссылается индекс.
    op.drop_index(op.f('ix_users_vk_id'), table_name='users')
    op.drop_column('users', 'vk_id')


def downgrade() -> None:
    op.add_column('users', sa.Column('vk_id', sa.String(length=64), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.select(_identities.c.user_id, _identities.c.provider_user_id).where(
            _identities.c.provider == 'vk'
        )
    ).fetchall()
    for row in rows:
        conn.execute(
            _users.update().where(_users.c.id == row.user_id).values(vk_id=row.provider_user_id)
        )

    op.create_index(op.f('ix_users_vk_id'), 'users', ['vk_id'], unique=True)
    op.drop_index(op.f('ix_oauth_states_state'), table_name='oauth_states')
    op.drop_table('oauth_states')
    op.drop_index(op.f('ix_user_identities_user_id'), table_name='user_identities')
    op.drop_table('user_identities')
