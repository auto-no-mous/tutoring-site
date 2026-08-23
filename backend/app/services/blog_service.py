import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blog import BlogPost
from app.models.user import User
from app.schemas.blog import MAX_SUMMARY_LENGTH, BlogPostCreate, BlogPostUpdate
from app.utils.html_sanitize import strip_html_to_text
from app.utils.slug import slugify
from app.utils.time import utcnow

_SLUG_FALLBACK = "post"


async def _unique_slug(db: AsyncSession, desired: str, exclude_id: uuid.UUID | None = None) -> str:
    """Appends -2, -3, ... until the slug is free. Cheaper and friendlier than making
    the admin resolve a 409 by hand, and two articles legitimately share a title often
    enough (e.g. "Итоги года") to be worth handling."""
    base = slugify(desired) or _SLUG_FALLBACK
    candidate = base
    suffix = 2
    while True:
        query = select(BlogPost.id).where(BlogPost.slug == candidate)
        if exclude_id is not None:
            query = query.where(BlogPost.id != exclude_id)
        if (await db.execute(query)).first() is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def _auto_summary(body: str) -> str:
    """Falls back to the opening of the article when the admin left the summary empty -
    an empty card on the home page would look broken."""
    text = strip_html_to_text(body)
    if len(text) <= MAX_SUMMARY_LENGTH:
        return text
    return text[:MAX_SUMMARY_LENGTH].rsplit(" ", 1)[0] + "…"


async def create_post(db: AsyncSession, payload: BlogPostCreate, author_id: uuid.UUID) -> BlogPost:
    post = BlogPost(
        slug=await _unique_slug(db, payload.slug or payload.title),
        title=payload.title,
        summary=payload.summary.strip() or _auto_summary(payload.body),
        cover_image_url=payload.cover_image_url,
        body=payload.body,
        is_published=payload.is_published,
        published_at=utcnow() if payload.is_published else None,
        author_id=author_id,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


async def get_post_or_404(db: AsyncSession, post_id: uuid.UUID) -> BlogPost:
    post = await db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Статья не найдена")
    return post


async def get_published_by_slug(db: AsyncSession, slug: str) -> BlogPost:
    result = await db.execute(
        select(BlogPost).where(BlogPost.slug == slug, BlogPost.is_published.is_(True))
    )
    post = result.scalar_one_or_none()
    if post is None:
        # Черновик отдаём как 404, а не 403: существование неопубликованной статьи -
        # тоже информация, и по URL её быть не должно видно.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Статья не найдена")
    return post


async def update_post(db: AsyncSession, post: BlogPost, payload: BlogPostUpdate) -> BlogPost:
    data = payload.model_dump(exclude_unset=True)

    if "slug" in data:
        # Пустой slug в форме означает "пересобрать из заголовка", а не "стереть".
        data["slug"] = await _unique_slug(db, data["slug"] or data.get("title") or post.title, post.id)
    if "summary" in data:
        body = data.get("body", post.body)
        data["summary"] = (data["summary"] or "").strip() or _auto_summary(body)
    if data.get("is_published") and post.published_at is None:
        # Дата публикации проставляется один раз - снятие и повторная публикация
        # статьи не должны поднимать её наверх ленты как новую.
        data["published_at"] = utcnow()

    for field, value in data.items():
        setattr(post, field, value)

    await db.commit()
    await db.refresh(post)
    return post


async def delete_post(db: AsyncSession, post: BlogPost) -> None:
    await db.delete(post)
    await db.commit()


async def list_admin_posts(db: AsyncSession) -> list[BlogPost]:
    """Everything including drafts, newest first - drafts on top since they're the ones
    still being worked on."""
    result = await db.execute(select(BlogPost).order_by(BlogPost.created_at.desc()))
    return list(result.scalars().all())


async def list_published(db: AsyncSession, page: int, page_size: int) -> tuple[list[BlogPost], int]:
    base = select(BlogPost).where(BlogPost.is_published.is_(True))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    result = await db.execute(
        base.order_by(BlogPost.published_at.desc(), BlogPost.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_author_names(db: AsyncSession, posts: list[BlogPost]) -> dict[uuid.UUID, str]:
    author_ids = {p.author_id for p in posts if p.author_id is not None}
    if not author_ids:
        return {}
    result = await db.execute(select(User.id, User.display_name).where(User.id.in_(author_ids)))
    return {user_id: display_name for user_id, display_name in result.all()}
