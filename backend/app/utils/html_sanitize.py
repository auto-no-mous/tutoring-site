"""Server-side backstop for the tutor "about" rich-text field, mirroring the same
allow-list as frontend/src/utils/richText.ts. The frontend already sanitizes on every
render and edit path (see RichTextEditor.vue), but the backend shouldn't rely on the
frontend as the only trust boundary for HTML that later gets rendered - a value could
reach the database via a direct API call that never touched the frontend at all.
Uses only the stdlib (html.parser) rather than adding a new dependency."""

import html as html_module
from html.parser import HTMLParser

ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "a", "br", "div", "p", "span", "img", "ul", "ol", "li", "h2", "h3"}
VOID_TAGS = {"br", "img"}
ALLOWED_ATTRS: dict[str, set[str]] = {
    "a": {"href"},
    "img": {"src", "alt", "class"},
}
SAFE_URL_PREFIXES = ("http://", "https://", "mailto:")
SAFE_IMG_SRC_PREFIX = "/files/"
IMG_ALIGN_CLASSES = {"rt-img-left", "rt-img-center", "rt-img-right", "rt-img-full"}


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        # Tracks which open tags we actually emitted, so a disallowed tag's closing
        # tag can be silently dropped too (unwrapped, not just its opening tag).
        self._open_stack: list[str] = []

    def _attrs_dict(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {name: (value or "") for name, value in attrs}

    def _open(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ALLOWED_TAGS:
            self._open_stack.append(tag)
            return

        raw = self._attrs_dict(attrs)
        kept: dict[str, str] = {k: v for k, v in raw.items() if k in ALLOWED_ATTRS.get(tag, set())}

        if tag == "a":
            href = kept.get("href", "").strip()
            if href.lower().startswith(SAFE_URL_PREFIXES):
                kept["href"] = href
            else:
                kept.pop("href", None)
            kept["target"] = "_blank"
            kept["rel"] = "noopener noreferrer"

        if tag == "img":
            src = kept.get("src", "").strip()
            if not src.startswith(SAFE_IMG_SRC_PREFIX):
                # Same as the frontend sanitizer: an image with an untrusted src is
                # dropped entirely, not just stripped of attributes.
                self._open_stack.append(tag)
                return
            cls = kept.get("class")
            if cls not in IMG_ALIGN_CLASSES:
                kept.pop("class", None)

        attr_str = "".join(f' {name}="{html_module.escape(value, quote=True)}"' for name, value in kept.items())
        self.out.append(f"<{tag}{attr_str}>")
        self._open_stack.append(tag if tag in VOID_TAGS else f"open:{tag}")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if not self._open_stack:
            return
        top = self._open_stack.pop()
        if top == f"open:{tag}":
            self.out.append(f"</{tag}>")
        # Any other mismatch (disallowed tag, or a dropped-img placeholder) is just
        # unwound silently - nothing was emitted for its opening tag either.

    def handle_data(self, data: str) -> None:
        self.out.append(html_module.escape(data))


def sanitize_rich_text(value: str) -> str:
    parser = _Sanitizer()
    parser.feed(value)
    parser.close()
    return "".join(parser.out)


class _TextExtractor(HTMLParser):
    """Discards every tag, keeps only the text - used for the plain-text "about"
    snippet shown on catalog cards (tutor_service.search_catalog)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def strip_html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return " ".join("".join(parser.parts).split())
