import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class BlogPost(UUIDPKMixin, TimestampMixin, Base):
    """An article published by an administrator. Only admins can write; everyone reads
    the published ones on / and /blog.

    `body` holds the same sanitized rich-text HTML as TutorProfile.about, produced by
    the same editor (RichTextEditor.vue) and passed through the same allow-list on
    both sides (utils/richText.ts, utils/html_sanitize.py)."""

    __tablename__ = "blog_posts"

    # Часть публичного URL (/blog/<slug>), поэтому уникален и индексирован: выборка
    # статьи идёт только по нему, id наружу не светится.
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Plain text, not HTML: shown in the card on the home page and used as the meta
    # description, where markup would only get in the way.
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cover_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Проставляется при первой публикации и дальше не двигается: это дата статьи для
    # читателя и порядок сортировки, а не время последней правки (для него updated_at).
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
