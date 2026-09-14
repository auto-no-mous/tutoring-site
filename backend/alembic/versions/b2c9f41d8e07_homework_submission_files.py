"""homework submissions: several files instead of one

Revision ID: b2c9f41d8e07
Revises: f3a91c74e5d2
Create Date: 2026-09-07 10:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c9f41d8e07'
down_revision: Union[str, None] = 'f3a91c74e5d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_files = sa.table(
    'homework_submission_files',
    sa.column('id', sa.Uuid()),
    sa.column('submission_id', sa.Uuid()),
    sa.column('file_path', sa.String()),
    sa.column('uploaded_at', sa.DateTime(timezone=True)),
)
_submissions = sa.table(
    'homework_submissions',
    sa.column('id', sa.Uuid()),
    sa.column('file_path', sa.String()),
    sa.column('submitted_at', sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.create_table(
        'homework_submission_files',
        sa.Column('submission_id', sa.Uuid(), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['submission_id'], ['homework_submissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_homework_submission_files_submission_id'),
        'homework_submission_files',
        ['submission_id'],
        unique=False,
    )

    # Уже сданные файлы переезжают в новую таблицу: ученик должен видеть их там же,
    # где будет видеть добавленные позже.
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(_submissions.c.id, _submissions.c.file_path, _submissions.c.submitted_at).where(
            _submissions.c.file_path.isnot(None)
        )
    ).fetchall()
    if rows:
        conn.execute(
            _files.insert(),
            [
                {
                    'id': uuid.uuid4(),
                    'submission_id': row.id,
                    'file_path': row.file_path,
                    # У старых сдач время отправки известно; если нет - берём текущее,
                    # порядок внутри одной сдачи от этого не пострадает.
                    'uploaded_at': row.submitted_at or sa.func.now(),
                }
                for row in rows
            ],
        )

    with op.batch_alter_table('homework_submissions') as batch:
        batch.drop_column('file_path')


def downgrade() -> None:
    with op.batch_alter_table('homework_submissions') as batch:
        batch.add_column(sa.Column('file_path', sa.String(length=512), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.select(_files.c.submission_id, _files.c.file_path).order_by(_files.c.uploaded_at)
    ).fetchall()
    # В одну колонку помещается только один файл - оставляем последний приложенный.
    latest = {row.submission_id: row.file_path for row in rows}
    for submission_id, file_path in latest.items():
        conn.execute(
            _submissions.update()
            .where(_submissions.c.id == submission_id)
            .values(file_path=file_path)
        )

    op.drop_index(
        op.f('ix_homework_submission_files_submission_id'), table_name='homework_submission_files'
    )
    op.drop_table('homework_submission_files')
