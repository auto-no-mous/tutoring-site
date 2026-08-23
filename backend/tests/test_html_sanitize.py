from app.utils.html_sanitize import sanitize_rich_text, strip_html_to_text


def test_strips_script_tags_and_event_handlers() -> None:
    result = sanitize_rich_text('<img src="x" onerror="alert(1)"><script>evil()</script><p>ok</p>')
    assert "onerror" not in result
    assert "<script" not in result
    assert "<p>ok</p>" in result


def test_strips_javascript_uri_from_link_href() -> None:
    result = sanitize_rich_text('<a href="javascript:alert(1)">click</a>')
    assert "javascript:" not in result
    assert "href" not in result


def test_keeps_safe_link_and_forces_noopener() -> None:
    result = sanitize_rich_text('<a href="https://example.com">click</a>')
    assert 'href="https://example.com"' in result
    assert 'target="_blank"' in result
    assert 'rel="noopener noreferrer"' in result


def test_drops_image_with_untrusted_src() -> None:
    result = sanitize_rich_text('<img src="https://evil.example/tracker.png" onerror="alert(1)">')
    assert "<img" not in result
    assert "evil.example" not in result


def test_keeps_image_served_from_own_files_mount() -> None:
    result = sanitize_rich_text('<img src="/files/tutor-about-images/x.png" class="rt-img-center" onerror="alert(1)">')
    assert 'src="/files/tutor-about-images/x.png"' in result
    assert "onerror" not in result


def test_strips_disallowed_alignment_class_but_keeps_image() -> None:
    result = sanitize_rich_text('<img src="/files/tutor-about-images/x.png" class="not-a-real-class">')
    assert "<img" in result
    assert "not-a-real-class" not in result


def test_unwraps_disallowed_tags_but_keeps_text_content() -> None:
    result = sanitize_rich_text("<div>keep <marquee>this</marquee> text</div>")
    assert "<marquee" not in result
    assert "this" in result
    assert "text" in result


def test_preserves_allowed_formatting() -> None:
    result = sanitize_rich_text("<p>Hello <b>world</b>, <i>this</i> is <u>ok</u></p>")
    assert result == "<p>Hello <b>world</b>, <i>this</i> is <u>ok</u></p>"


def test_strip_html_to_text_separates_blocks_but_not_inline_tags() -> None:
    # Соседние блоки не должны склеиваться в "абзац.Второй".
    assert strip_html_to_text("<p>Первый абзац.</p><p>Второй абзац.</p>") == "Первый абзац. Второй абзац."
    assert strip_html_to_text("Строка<br>Другая") == "Строка Другая"
    assert strip_html_to_text("<ul><li>Раз</li><li>Два</li></ul>") == "Раз Два"
    # А инлайновое выделение внутри слова не должно его разрывать.
    assert strip_html_to_text("<p>Сло<b>во</b></p>") == "Слово"
