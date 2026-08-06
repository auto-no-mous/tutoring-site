import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import RichTextEditor from "@/components/RichTextEditor.vue";

// Regression test for a stored-XSS finding: modelValue used to be assigned straight
// to the editor's innerHTML on mount and on external updates, with no sanitization -
// content saved via a direct API call (bypassing the editor's own outbound
// sanitizeRichText()) would execute unsanitized in anyone who later opened it in the
// editor (e.g. an admin editing a tutor's "about" field).
describe("RichTextEditor", () => {
  it("sanitizes the initial modelValue before mounting it into the editable div", () => {
    const payload = '<img src="x" onerror="window.xssFired = true"><script>evil()</script><p>ok</p>';
    const wrapper = mount(RichTextEditor, { props: { modelValue: payload } });
    const editorHtml = wrapper.find("[contenteditable]").element.innerHTML;
    expect(editorHtml).not.toContain("onerror");
    expect(editorHtml).not.toContain("<script");
    expect(editorHtml).toContain("ok");
  });

  it("re-sanitizes when modelValue changes from an external source", async () => {
    const wrapper = mount(RichTextEditor, { props: { modelValue: "<p>start</p>" } });
    await wrapper.setProps({ modelValue: '<img src="x" onerror="window.xssFired = true">' });
    const editorHtml = wrapper.find("[contenteditable]").element.innerHTML;
    expect(editorHtml).not.toContain("onerror");
  });
});
