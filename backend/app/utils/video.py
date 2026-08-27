"""Turns a tutor-supplied video link into an embeddable player URL.

Only YouTube, RuTube and VK Video are supported (the three platforms tutors asked
for). The result is rendered as an <iframe src> on the public profile, so nothing
here echoes back the tutor's URL as-is: every branch extracts an id and rebuilds the
URL from a fixed template. An unrecognized link yields None, which the schema layer
turns into a validation error (see schemas/common.VideoUrl).
"""

import re
from urllib.parse import parse_qs, urlparse

# Ids are alphanumeric with - and _ across all three platforms; the length cap keeps a
# pathological path segment out of the generated URL.
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# VK addresses a video by owner id (negative for communities) and video id.
_VK_VIDEO_PATTERN = re.compile(r"^video(-?\d{1,20})_(\d{1,20})$")

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
_RUTUBE_HOSTS = {"rutube.ru", "www.rutube.ru"}
_VK_HOSTS = {"vk.com", "www.vk.com", "m.vk.com", "vkvideo.ru", "www.vkvideo.ru"}

# Path prefixes that carry the id in the following segment, e.g. /embed/<id>.
_YOUTUBE_ID_PREFIXES = ("embed", "shorts", "live", "v")


def _segments(parsed) -> list[str]:
    return [segment for segment in parsed.path.split("/") if segment]


def _youtube_embed(parsed) -> str | None:
    segments = _segments(parsed)
    video_id = None
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        # Short form: the whole path is the id.
        video_id = segments[0] if segments else None
    elif segments and segments[0] in _YOUTUBE_ID_PREFIXES:
        video_id = segments[1] if len(segments) > 1 else None
    elif segments and segments[0] == "watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
    if video_id is None or not _ID_PATTERN.match(video_id):
        return None
    return f"https://www.youtube.com/embed/{video_id}"


def _rutube_embed(parsed) -> str | None:
    segments = _segments(parsed)
    video_id = None
    # /video/<id>/, /shorts/<id>/ and the already-embeddable /play/embed/<id>.
    if len(segments) >= 3 and segments[0] == "play" and segments[1] == "embed":
        video_id = segments[2]
    elif len(segments) >= 2 and segments[0] in ("video", "shorts"):
        video_id = segments[1]
    if video_id is None or not _ID_PATTERN.match(video_id):
        return None
    return f"https://rutube.ru/play/embed/{video_id}"


def _vk_embed(parsed) -> str | None:
    segments = _segments(parsed)
    query = parse_qs(parsed.query)
    # Player links copied from VK's own "share" dialog already carry oid/id.
    if segments and segments[0] == "video_ext.php":
        owner_id, video_id = query.get("oid", [None])[0], query.get("id", [None])[0]
    else:
        # Page links: /video-12345_67890 (optionally under /video/ or a community path).
        match = next((m for s in segments if (m := _VK_VIDEO_PATTERN.match(s))), None)
        if match is None:
            return None
        owner_id, video_id = match.group(1), match.group(2)
    if owner_id is None or video_id is None:
        return None
    if not re.fullmatch(r"-?\d{1,20}", owner_id) or not re.fullmatch(r"\d{1,20}", video_id):
        return None
    return f"https://vk.com/video_ext.php?oid={owner_id}&id={video_id}&hd=2"


def parse_video_embed_url(url: str | None) -> str | None:
    """Embeddable player URL for a YouTube/RuTube/VK Video link, or None if the link
    isn't one of those (or doesn't point at a specific video)."""
    if not url:
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    if host in _YOUTUBE_HOSTS:
        return _youtube_embed(parsed)
    if host in _RUTUBE_HOSTS:
        return _rutube_embed(parsed)
    if host in _VK_HOSTS:
        return _vk_embed(parsed)
    return None
