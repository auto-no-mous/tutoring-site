// Whitelist-based sanitizer for the tutor "about" rich text field (bold/italic/
// underline/links/images/headings/lists). Applied both when the editor emits changes
// and again at render time on the public profile (defense in depth against a client
// that calls the API directly with hand-crafted HTML).
const ALLOWED_TAGS = new Set([
  "B", "STRONG", "I", "EM", "U", "A", "BR", "DIV", "P", "SPAN", "IMG", "UL", "OL", "LI", "H2", "H3",
]);
const SAFE_URL = /^(https?:|mailto:)/i;
// Uploaded images are always served from our own /files mount (see
// api/v1/tutors.py::upload_about_image + app.main's StaticFiles) - restricting src to
// that prefix rules out embedding arbitrary/tracking third-party images or data: URIs.
const SAFE_IMG_SRC = /^\/files\//;
// Alignment is expressed as one of these classes (see style.css's .rt-img-* rules)
// rather than a free-form style attribute, so there's no CSS value to sanitize.
export const IMG_ALIGN_CLASSES = ["rt-img-left", "rt-img-center", "rt-img-right", "rt-img-full"] as const;
const IMG_ALIGN_CLASS_SET = new Set<string>(IMG_ALIGN_CLASSES);

const ALLOWED_ATTRS: Record<string, Set<string>> = {
  A: new Set(["href", "target", "rel"]),
  IMG: new Set(["src", "alt", "class"]),
};

export function sanitizeRichText(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  unwrapDisallowedTags(doc.body);
  cleanAttributes(doc.body);
  return doc.body.innerHTML;
}

function unwrapDisallowedTags(root: HTMLElement): void {
  for (const el of Array.from(root.querySelectorAll("*"))) {
    if (ALLOWED_TAGS.has(el.tagName)) continue;
    const parent = el.parentNode;
    if (!parent) continue;
    while (el.firstChild) parent.insertBefore(el.firstChild, el);
    parent.removeChild(el);
  }
}

function cleanAttributes(root: HTMLElement): void {
  for (const el of Array.from(root.querySelectorAll("*"))) {
    const allowed = ALLOWED_ATTRS[el.tagName] ?? new Set<string>();
    for (const attr of Array.from(el.attributes)) {
      if (!allowed.has(attr.name)) el.removeAttribute(attr.name);
    }
    if (el.tagName === "A") {
      const href = (el.getAttribute("href") ?? "").trim();
      if (!SAFE_URL.test(href)) {
        el.removeAttribute("href");
      }
      el.setAttribute("target", "_blank");
      el.setAttribute("rel", "noopener noreferrer");
    }
    if (el.tagName === "IMG") {
      const src = (el.getAttribute("src") ?? "").trim();
      if (!SAFE_IMG_SRC.test(src)) {
        el.remove();
        continue;
      }
      const cls = el.getAttribute("class");
      if (cls && !IMG_ALIGN_CLASS_SET.has(cls)) el.removeAttribute("class");
    }
  }
}
