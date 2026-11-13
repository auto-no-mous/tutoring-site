import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel.vue";
import { useAuthStore } from "@/stores/auth";

const listThreads = vi.fn();
const openSupportThread = vi.fn();
const listMessages = vi.fn(async () => []);

vi.mock("@/api/chat", () => ({
  listThreads: () => listThreads(),
  listMessages: () => listMessages(),
  listMessageableStudents: vi.fn(async () => []),
  openThreadWithStudent: vi.fn(),
  openSupportThread: () => openSupportThread(),
  sendMessage: vi.fn(),
}));
vi.mock("@/api/notifications", () => ({
  listSystemNotifications: vi.fn(async () => []),
  markSystemNotificationsRead: vi.fn(),
}));
vi.mock("@/stores/notifications", () => ({ useNotificationsStore: () => ({ refresh: vi.fn() }) }));

function thread(overrides: Record<string, unknown> = {}) {
  return {
    id: "t-1",
    type: "individual",
    tutor_id: "tp-1",
    student_id: "u-1",
    group_id: null,
    display_title: "Иванова Анна",
    unread_count: 0,
    last_message_preview: null,
    last_message_at: null,
    ...overrides,
  };
}

function mountPanel(user: Record<string, unknown>, props: Record<string, unknown> = {}) {
  setActivePinia(createPinia());
  useAuthStore().user = { id: "u-1", role: "student", answers_support: false, ...user } as never;
  return mount(ChatPanel, { props, global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } } });
}

describe("ChatPanel: поддержка", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listThreads.mockResolvedValue([thread()]);
  });

  it("у пользователя закреплена «Поддержка»; первое открытие создаёт обращение", async () => {
    openSupportThread.mockResolvedValue(thread({ id: "s-1", type: "support", tutor_id: null, display_title: "Поддержка" }));
    const wrapper = mountPanel({});
    await flushPromises();

    const entry = wrapper.find("[data-support-entry]");
    expect(entry.text()).toContain("Поддержка");
    await entry.trigger("click");
    await flushPromises();

    expect(openSupportThread).toHaveBeenCalledTimes(1);
    expect(wrapper.find("[data-support-hint]").exists()).toBe(true);
  });

  it("своё обращение не дублируется в общем списке", async () => {
    listThreads.mockResolvedValue([
      thread(),
      thread({ id: "s-1", type: "support", tutor_id: null, display_title: "Поддержка", unread_count: 2 }),
    ]);
    const wrapper = mountPanel({});
    await flushPromises();

    expect(wrapper.findAll("button").filter((b) => b.text().includes("Поддержка"))).toHaveLength(1);
    expect(wrapper.find("[data-support-entry]").text()).toContain("2");
  });

  it("отвечающий в поддержке видит обращения списком, без закреплённого пункта", async () => {
    listThreads.mockResolvedValue([
      thread({ id: "s-9", type: "support", tutor_id: null, student_id: "u-9", display_title: "Поддержка: Петров Пётр" }),
    ]);
    const wrapper = mountPanel({ role: "tutor", answers_support: true });
    await flushPromises();

    expect(wrapper.find("[data-support-entry]").exists()).toBe(false);
    expect(wrapper.text()).toContain("Поддержка: Петров Пётр");
  });

  it("в админке - только обращения, без системных уведомлений", async () => {
    listThreads.mockResolvedValue([]);
    const wrapper = mountPanel({ role: "admin", answers_support: true }, { supportOnly: true });
    await flushPromises();

    expect(wrapper.text()).not.toContain("Системные уведомления");
    expect(wrapper.text()).toContain("Обращений пока нет.");
  });
});
