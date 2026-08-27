import datetime as dt
from typing import Annotated
from urllib.parse import urlparse

from pydantic import AfterValidator

from app.utils.html_sanitize import sanitize_rich_text
from app.utils.time import to_utc
from app.utils.video import parse_video_embed_url

# Use for every datetime accepted from a client. See app.utils.time.to_utc for why:
# SQLite storage doesn't convert offsets, so anything not already normalized to UTC
# before it reaches the DB would be persisted as the wrong instant.
UTCDateTime = Annotated[dt.datetime, AfterValidator(to_utc)]

# Use for any client-supplied rich-text field that later gets rendered as HTML (e.g.
# TutorProfileUpdate.about). The frontend already sanitizes on every render/edit path
# (see RichTextEditor.vue), but the backend shouldn't rely on that as the only trust
# boundary - a value could reach the DB via a direct API call that never touched the
# frontend sanitizer at all.
SanitizedHtml = Annotated[str, AfterValidator(sanitize_rich_text)]

_MAX_PROFILE_URL_LENGTH = 512


def _validate_profile_url(value: str) -> str:
    """Validates a tutor-supplied contact link (Telegram/VK/YouTube/extra links) -
    must be an absolute http(s) URL so it's safe to render as an <a href> and can't
    be used for a javascript:/data: URL injection."""
    value = value.strip()
    if len(value) > _MAX_PROFILE_URL_LENGTH:
        raise ValueError("Ссылка слишком длинная")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Ссылка должна начинаться с http:// или https://")
    return value


# Use for any client-supplied link meant to be rendered as an <a href> on a public
# profile - see TutorProfileUpdate.telegram_url/vk_url/youtube_url and TutorExtraLink.
ProfileUrl = Annotated[str, AfterValidator(_validate_profile_url)]


def _validate_video_url(value: str) -> str:
    """Stricter than _validate_profile_url: this link ends up as an <iframe src>, so it
    must be a link to a particular video on one of the supported platforms rather than
    any http(s) address."""
    value = _validate_profile_url(value)
    if parse_video_embed_url(value) is None:
        raise ValueError(
            "Поддерживаются ссылки на видео с YouTube, RuTube или VK Видео "
            "(например, https://youtu.be/xxxxxxxxxxx)"
        )
    return value


# Use for the tutor's profile video (TutorProfileUpdate.video_url).
VideoUrl = Annotated[str, AfterValidator(_validate_video_url)]
