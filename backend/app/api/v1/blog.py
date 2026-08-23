from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.schemas.blog import BlogPostListItemOut, BlogPostOut, BlogPostPageOut
from app.services import blog_service

router = APIRouter(prefix="/blog", tags=["blog"])


@router.get("", response_model=BlogPostPageOut)
async def list_posts(db: DbSession, page: int = 1, page_size: int = 10) -> BlogPostPageOut:
    """Published articles only, newest first. Used both by the home page section (which
    asks for the first few) and by the full /blog listing."""
    if page < 1 or not (1 <= page_size <= 50):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Некорректные параметры страницы")
    posts, total = await blog_service.list_published(db, page=page, page_size=page_size)
    return BlogPostPageOut(
        items=[BlogPostListItemOut.model_validate(p, from_attributes=True) for p in posts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{slug}", response_model=BlogPostOut)
async def get_post(slug: str, db: DbSession) -> BlogPostOut:
    post = await blog_service.get_published_by_slug(db, slug)
    authors = await blog_service.get_author_names(db, [post])
    return BlogPostOut.model_validate(post, from_attributes=True).model_copy(
        update={"author_name": authors.get(post.author_id) if post.author_id else None}
    )
