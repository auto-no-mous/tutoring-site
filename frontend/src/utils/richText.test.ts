import { describe, expect, it } from "vitest";

import { sanitizeRichText } from "@/utils/richText";

describe("sanitizeRichText", () => {
  it("keeps whitelisted formatting tags", () => {
    expect(sanitizeRichText("<p><b>Жирный</b> и <i>курсив</i></p>")).toBe("<p><b>Жирный</b> и <i>курсив</i></p>");
  });

  it("strips the script tag itself, so nothing executable survives", () => {
    const result = sanitizeRichText('<p>Привет</p><script>alert("xss")</script>');
    expect(result).not.toContain("<script>");
    expect(result).not.toContain("</script>");
  });

  it("strips onerror and other event-handler attributes", () => {
    const result = sanitizeRichText('<img src="x" onerror="alert(1)">');
    expect(result).not.toContain("onerror");
  });

  it("strips a javascript: link href but keeps the anchor text", () => {
    const result = sanitizeRichText('<a href="javascript:alert(1)">click</a>');
    expect(result).not.toContain("javascript:");
    expect(result).toContain("click");
  });

  it("keeps a safe https link and adds rel=noopener", () => {
    const result = sanitizeRichText('<a href="https://example.com">site</a>');
    expect(result).toContain('href="https://example.com"');
    expect(result).toContain('rel="noopener noreferrer"');
    expect(result).toContain('target="_blank"');
  });

  it("drops disallowed tags like style while unwrapping their content", () => {
    const result = sanitizeRichText("<style>body{color:red}</style><p>text</p>");
    expect(result).not.toContain("<style>");
    expect(result).toContain("<p>text</p>");
  });

  it("keeps an uploaded image (served from /files) with a whitelisted alignment class", () => {
    const result = sanitizeRichText('<img src="/files/tutor-about-images/abc.png" class="rt-img-center" alt="">');
    expect(result).toContain('src="/files/tutor-about-images/abc.png"');
    expect(result).toContain('class="rt-img-center"');
  });

  it("strips an image whose src isn't from our own /files upload prefix", () => {
    const result = sanitizeRichText('<img src="https://evil.example.com/tracker.png">');
    expect(result).not.toContain("<img");
  });

  it("strips an arbitrary class on an image instead of the alignment whitelist", () => {
    const result = sanitizeRichText('<img src="/files/tutor-about-images/abc.png" class="totally-not-alignment">');
    expect(result).toContain('src="/files/tutor-about-images/abc.png"');
    expect(result).not.toContain("totally-not-alignment");
  });

  it("keeps headings and lists added for the extended editor", () => {
    const result = sanitizeRichText("<h2>Заголовок</h2><ul><li>Пункт</li></ul>");
    expect(result).toBe("<h2>Заголовок</h2><ul><li>Пункт</li></ul>");
  });
});
