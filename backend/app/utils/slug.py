"""Turns a human title into a URL slug. Used for blog post URLs (/blog/<slug>), which
admins type in Russian - a Cyrillic slug would end up percent-encoded and unreadable
in links and search results, so titles are transliterated rather than URL-escaped."""

import re

# Практическая транслитерация (не ГОСТ): цель - читаемый латинский URL, а не
# обратимость. Совпадает с тем, как принято писать русские слова латиницей.
_RU_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}

MAX_SLUG_LENGTH = 64


def slugify(value: str) -> str:
    """Returns a lowercase a-z0-9-hyphen slug, or "" if nothing usable is left (e.g. a
    title made entirely of emoji) - callers decide what to fall back to."""
    transliterated = "".join(_RU_TO_LAT.get(ch, ch) for ch in value.strip().lower())
    slug = re.sub(r"[^a-z0-9]+", "-", transliterated).strip("-")
    if len(slug) <= MAX_SLUG_LENGTH:
        return slug
    # Обрезаем по границе слова, чтобы не оставлять обрубок вроде "podgotovk".
    return slug[:MAX_SLUG_LENGTH].rsplit("-", 1)[0].strip("-") or slug[:MAX_SLUG_LENGTH].strip("-")
