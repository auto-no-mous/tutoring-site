import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import SanitizedHtml

MAX_SUMMARY_LENGTH = 400


class BlogPostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: SanitizedHtml = ""
    summary: str = Field(default="", max_length=MAX_SUMMARY_LENGTH)
    cover_image_url: str | None = Field(default=None, max_length=512)
    # Slug is optional: left empty, the service transliterates the title. Supplied
    # explicitly, it lets an admin keep a URL stable after renaming the article.
    slug: str | None = Field(default=None, max_length=64)
    is_published: bool = False


class BlogPostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: SanitizedHtml | None = None
    summary: str | None = Field(default=None, max_length=MAX_SUMMARY_LENGTH)
    cover_image_url: str | None = Field(default=None, max_length=512)
    slug: str | None = Field(default=None, max_length=64)
    is_published: bool | None = None


class BlogPostListItemOut(BaseModel):
    """Card view - no `body`, so listing 50 articles doesn't ship 50 full texts."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    summary: str
    cover_image_url: str | None
    published_at: dt.datetime | None


class BlogPostOut(BlogPostListItemOut):
    body: str
    author_name: str | None = None


class BlogPostAdminOut(BlogPostOut):
    """Adds the fields only the admin list needs - drafts are invisible publicly, so
    `is_published` never appears in the public schemas."""

    is_published: bool
    created_at: dt.datetime
    updated_at: dt.datetime


class BlogPostPageOut(BaseModel):
    items: list[BlogPostListItemOut]
    total: int
    page: int
    page_size: int
