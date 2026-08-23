import { RouterLinkStub, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import BlogPostCard from "@/components/blog/BlogPostCard.vue";
import type { BlogPostListItem } from "@/types/blog";

function post(overrides: Partial<BlogPostListItem> = {}): BlogPostListItem {
  return {
    id: "1",
    slug: "kak-gotovitsya-k-ege",
    title: "Как готовиться к ЕГЭ",
    summary: "Разбираем план подготовки.",
    cover_image_url: null,
    published_at: "2026-08-23T09:00:00Z",
    ...overrides,
  };
}

function mountCard(item: BlogPostListItem) {
  return mount(BlogPostCard, {
    props: { post: item },
    global: { stubs: { RouterLink: RouterLinkStub } },
  });
}

describe("BlogPostCard", () => {
  it("links to the article by slug and shows its title, summary and date", () => {
    const wrapper = mountCard(post());

    expect(wrapper.findComponent(RouterLinkStub).props().to).toBe("/blog/kak-gotovitsya-k-ege");
    expect(wrapper.text()).toContain("Как готовиться к ЕГЭ");
    expect(wrapper.text()).toContain("Разбираем план подготовки.");
    expect(wrapper.text()).toContain("23 августа 2026");
    expect(wrapper.find("time").attributes("datetime")).toBe("2026-08-23T09:00:00Z");
  });

  it("shows the cover when there is one", () => {
    const wrapper = mountCard(post({ cover_image_url: "/files/blog-images/cover.png" }));
    expect(wrapper.find("img").attributes("src")).toBe("/files/blog-images/cover.png");
  });

  it("falls back to a brand strip instead of an image when there is no cover", () => {
    const wrapper = mountCard(post({ cover_image_url: null }));
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find("div.bg-gradient-to-r").exists()).toBe(true);
  });

  it("renders no date line for a post that was never published", () => {
    const wrapper = mountCard(post({ published_at: null }));
    expect(wrapper.find("time").exists()).toBe(false);
  });
});
