import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";
import { defineComponent, ref } from "vue";

import { usePageMeta, type PageMeta } from "@/utils/pageMeta";

const DEFAULT_TITLE = "my-tutor.ru — репетиторы онлайн";
const DEFAULT_DESCRIPTION = "Каталог репетиторов";

function description(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="description"]')!.content;
}

function jsonLd(): string | null {
  return document.querySelector('script[type="application/ld+json"]')?.textContent ?? null;
}

function mountWithMeta(source: () => PageMeta) {
  return mount(defineComponent({ setup: () => usePageMeta(source), template: "<div />" }));
}

describe("usePageMeta", () => {
  beforeEach(() => {
    document.head.innerHTML = `<meta name="description" content="${DEFAULT_DESCRIPTION}">`;
    document.title = DEFAULT_TITLE;
  });

  it("appends the site name to the title and restores everything on unmount", () => {
    const wrapper = mountWithMeta(() => ({ title: "Как готовиться к ЕГЭ", description: "Разбор" }));

    expect(document.title).toBe("Как готовиться к ЕГЭ — my-tutor.ru");
    expect(description()).toBe("Разбор");

    wrapper.unmount();
    expect(document.title).toBe(DEFAULT_TITLE);
    expect(description()).toBe(DEFAULT_DESCRIPTION);
  });

  it("keeps the default title and description when the page supplies none", () => {
    mountWithMeta(() => ({ jsonLd: { "@type": "FAQPage" } }));
    expect(document.title).toBe(DEFAULT_TITLE);
    expect(description()).toBe(DEFAULT_DESCRIPTION);
  });

  it("publishes structured data and removes it on unmount", () => {
    const wrapper = mountWithMeta(() => ({ jsonLd: { "@type": "Article", headline: "Заголовок" } }));

    expect(JSON.parse(jsonLd()!)).toEqual({ "@type": "Article", headline: "Заголовок" });

    wrapper.unmount();
    expect(jsonLd()).toBeNull();
  });

  it("follows reactive sources, so meta filled in after a fetch still lands", async () => {
    const post = ref<{ title: string } | null>(null);
    const wrapper = mountWithMeta(() => ({ title: post.value?.title }));

    expect(document.title).toBe(DEFAULT_TITLE);

    post.value = { title: "Загруженная статья" };
    await wrapper.vm.$nextTick();
    expect(document.title).toBe("Загруженная статья — my-tutor.ru");
  });

  it("replaces its own structured data instead of stacking a second script", async () => {
    const type = ref("Article");
    const wrapper = mountWithMeta(() => ({ jsonLd: { "@type": type.value } }));

    type.value = "BlogPosting";
    await wrapper.vm.$nextTick();

    expect(document.querySelectorAll('script[type="application/ld+json"]')).toHaveLength(1);
    expect(JSON.parse(jsonLd()!)["@type"]).toBe("BlogPosting");
  });
});
