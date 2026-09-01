import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.utils.time import utcnow


class Whiteboard(UUIDPKMixin, Base):
    """Ссылка на онлайн-доску, которую репетитор ведёт с учеником или с группой.

    Доска живёт дольше одного занятия: с одним учеником месяцами работают на той же
    Miro/Excalidraw, поэтому привязка идёт к паре репетитор-ученик (или к группе), а
    не к записи в расписании - иначе ссылку пришлось бы вбивать к каждому занятию.
    Досок у пары обычно одна, изредка несколько (по темам), и карточка занятия
    показывает ту, которую открывали последней, пряча остальные под кнопку.
    """

    __tablename__ = "whiteboards"
    __table_args__ = (
        # Ровно одна привязка: либо ученик, либо группа. Доска "ничья" или сразу для
        # обоих не имеет смысла и сломала бы выборку для карточек.
        CheckConstraint(
            "(student_id IS NOT NULL AND group_id IS NULL) "
            "OR (student_id IS NULL AND group_id IS NOT NULL)",
            name="ck_whiteboards_exactly_one_owner",
        ),
    )

    tutor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True, nullable=True
    )

    url: Mapped[str] = mapped_column(String(512), nullable=False)
    # Подпись вроде «Алгебра» или «Черновики» - нужна, только когда досок несколько;
    # у единственной доски её обычно нет, и карточка пишет просто «Доска».
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # По нему сортируется список: сверху та доска, которую открывали последней.
    # Обновляется при переходе по ссылке из карточки занятия - и у репетитора, и у
    # ученика: «последняя открытая» - свойство их общей работы, а не одной стороны.
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
