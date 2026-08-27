import pytest

from app.utils.video import parse_video_embed_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/embed/dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "https://www.youtube.com/embed/dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=42", "https://www.youtube.com/embed/dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "https://www.youtube.com/embed/dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "https://www.youtube.com/embed/dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "https://www.youtube.com/embed/dQw4w9WgXcQ"),
    ],
)
def test_youtube_forms(url: str, expected: str) -> None:
    assert parse_video_embed_url(url) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://rutube.ru/video/abc123def456/", "https://rutube.ru/play/embed/abc123def456"),
        ("https://rutube.ru/play/embed/abc123def456", "https://rutube.ru/play/embed/abc123def456"),
        ("https://www.rutube.ru/shorts/abc123def456/", "https://rutube.ru/play/embed/abc123def456"),
    ],
)
def test_rutube_forms(url: str, expected: str) -> None:
    assert parse_video_embed_url(url) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://vk.com/video-12345_67890", "https://vk.com/video_ext.php?oid=-12345&id=67890&hd=2"),
        ("https://vkvideo.ru/video-12345_67890", "https://vk.com/video_ext.php?oid=-12345&id=67890&hd=2"),
        ("https://vk.com/video12345_67890", "https://vk.com/video_ext.php?oid=12345&id=67890&hd=2"),
        (
            "https://vk.com/video_ext.php?oid=-12345&id=67890&hash=abc",
            "https://vk.com/video_ext.php?oid=-12345&id=67890&hd=2",
        ),
    ],
)
def test_vk_forms(url: str, expected: str) -> None:
    assert parse_video_embed_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "not a url",
        "javascript:alert(1)",
        # Right platform, but not a link to a particular video.
        "https://www.youtube.com/@some-channel",
        "https://rutube.ru/",
        "https://vk.com/some_group",
        # Unsupported platforms must not be embedded at all.
        "https://vimeo.com/123456",
        "https://evil.example.com/video/1",
        # Lookalike hostnames must not pass as YouTube.
        "https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ",
        "https://notyoutube.com/watch?v=dQw4w9WgXcQ",
    ],
)
def test_rejects_anything_else(url: str | None) -> None:
    assert parse_video_embed_url(url) is None


def test_id_is_rebuilt_not_echoed() -> None:
    """The id goes through a strict character class, so a crafted path can't smuggle
    extra URL parts into the generated iframe src."""
    assert parse_video_embed_url('https://www.youtube.com/embed/"><script>') is None
    assert parse_video_embed_url("https://rutube.ru/video/..%2F..%2Fadmin/") is None
