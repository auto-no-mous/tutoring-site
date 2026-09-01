import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import WhiteboardLinks from "@/components/WhiteboardLinks.vue";
import type { Whiteboard } from "@/api/whiteboards";

const markWhiteboardUsed = vi.fn();

vi.mock("@/api/whiteboards", () => ({
  markWhiteboardUsed: (id: string) => markWhiteboardUsed(id),
}));

function board(overrides: Partial<Whiteboard> = {}): Whiteboard {
  return {
    id: "b-1",
    tutor_id: "t-1",
    student_id: "s-1",
    group_id: null,
    url: "https://miro.com/app/board/1",
    title: null,
    last_used_at: "2026-08-01T10:00:00Z",
    ...overrides,
  };
}

describe("WhiteboardLinks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    markWhiteboardUsed.mockResolvedValue({});
  });

  it("показывает последнюю открытую доску, остальные прячет под кнопку", async () => {
    const wrapper = mount(WhiteboardLinks, {
      props: {
        boards: [
          board({ id: "old", title: "Старая", last_used_at: "2026-08-01T10:00:00Z" }),
          board({ id: "fresh", title: "Свежая", last_used_at: "2026-08-30T10:00:00Z" }),
        ],
      },
    });

    // Сверху - открытая последней, независимо от порядка в пропсе.
    const links = wrapper.findAll("a");
    expect(links).toHaveLength(1);
    expect(links[0].text()).toContain("Свежая");
    expect(wrapper.text()).not.toContain("Старая");

    const expander = wrapper.findAll("button").find((b) => b.text().includes("+1"))!;
    await expander.trigger("click");

    expect(wrapper.findAll("a")).toHaveLength(2);
    expect(wrapper.text()).toContain("Старая");
  });

  it("не рисует кнопку разворачивания, когда доска одна", () => {
    const wrapper = mount(WhiteboardLinks, { props: { boards: [board()] } });

    expect(wrapper.findAll("a")).toHaveLength(1);
    // Без названия доска подписывается нейтрально.
    expect(wrapper.find("a").text()).toContain("Доска");
    expect(wrapper.findAll("button")).toHaveLength(0);
  });

  it("отмечает открытие, но не мешает переходу по ссылке", async () => {
    const wrapper = mount(WhiteboardLinks, { props: { boards: [board({ id: "b-9" })] } });

    await wrapper.find("a").trigger("click");

    expect(markWhiteboardUsed).toHaveBeenCalledWith("b-9");
    // Ссылка остаётся обычной ссылкой: открывается в новой вкладке средствами браузера.
    expect(wrapper.find("a").attributes("target")).toBe("_blank");
    expect(wrapper.find("a").attributes("href")).toBe("https://miro.com/app/board/1");
  });

  it("репетитору предлагает завести доску, когда её ещё нет", () => {
    const wrapper = mount(WhiteboardLinks, { props: { boards: [], canManage: true } });

    expect(wrapper.findAll("a")).toHaveLength(0);
    const manage = wrapper.find("button");
    expect(manage.text()).toContain("Доска");

    // Ученику без досок показывать нечего.
    const forStudent = mount(WhiteboardLinks, { props: { boards: [] } });
    expect(forStudent.find("div").exists()).toBe(false);
  });
});
