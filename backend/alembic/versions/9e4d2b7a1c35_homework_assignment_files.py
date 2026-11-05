"""homework assignments: several material files instead of one

Revision ID: 9e4d2b7a1c35
Revises: 3c59e2ed4a4b
Create Date: 2026-11-05 10:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e4d2b7a1c35'
down_revision: Union[str, None] = '3c59e2ed4a4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_files = sa.table(
    'homework_assignment_files',
    sa.column('id', sa.Uuid()),
    sa.column('assignment_id', sa.Uuid()),
    sa.column('file_path', sa.String()),
    sa.column('position', sa.Integer()),
)
_assignments = sa.table(
    'homework_assignments',
    sa.column('id', sa.Uuid()),
    sa.column('content_file_path', sa.String()),
)


def upgrade() -> None:
    op.create_table(
        'homework_assignment_files',
        sa.Column('assignment_id', sa.Uuid(), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['assignment_id'], ['homework_assignments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_homework_assignment_files_assignment_id'),
        'homework_assignment_files',
        ['assignment_id'],
        unique=False,
    )

    # Материал уже выданных заданий переезжает в новую таблицу - ученик должен
    # по-прежнему его видеть.
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(_assignments.c.id, _assignments.c.content_file_path).where(
            _assignments.c.content_file_path.isnot(None)
        )
    ).fetchall()
    if rows:
        conn.execute(
            _files.insert(),
            [
                {'id': uuid.uuid4(), 'assignment_id': row.id, 'file_path': row.content_file_path, 'position': 0}
                for row in rows
            ],
        )

    with op.batch_alter_table('homework_assignments') as batch:
        batch.drop_column('content_file_path')


def downgrade() -> None:
    with op.batch_alter_table('homework_assignments') as batch:
        batch.add_column(sa.Column('content_file_path', sa.String(length=512), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.select(_files.c.assignment_id, _files.c.file_path).order_by(_files.c.position.desc())
    ).fetchall()
    # В одну колонку помещается только один файл - оставляем первый приложенный
    # (сортировка по убыванию, так что последним записывается первый).
    first = {row.assignment_id: row.file_path for row in rows}
    for assignment_id, file_path in first.items():
        conn.execute(
            _assignments.update()
            .where(_assignments.c.id == assignment_id)
            .values(content_file_path=file_path)
        )

    op.drop_index(
        op.f('ix_homework_assignment_files_assignment_id'), table_name='homework_assignment_files'
    )
    op.drop_table('homework_assignment_files')
