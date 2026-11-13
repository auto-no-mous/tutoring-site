import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/ChatPanel.vue";
import { useAuthStore } from "@/stores/auth";

const listThreads = vi.fn();
const openSupportThread = vi.fn();
const listMessages = vi.fn(async (): Promise<unknown[]> => []);
const listMessageableTutors = vi.fn(async (): Promise<unknown[]> => []);
const openThreadWithTutor = vi.fn();
const sendMessage = vi.fn();

vi.mock("@/api/chat", () => ({
  listThreads: () => listThreads(),
  listMessages: () => listMessages(),
  listMessageableStudents: vi.fn(async () => []),
  listMessageableTutors: () => listMessageableTutors(),
  openThreadWithStudent: vi.fn(),
  openThreadWithTutor: (id: string) => openThreadWithTutor(id),
  openSupportThread: () => openSupportThread(),
  sendMessage: (threadId: string, content?: string) => sendMessage(threadId, content),
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

function message(id: string, content: string, senderId = "u-1") {
  return { id, thread_id: "t-1", sender_id: senderId, sender_display_name: "", content, file_path: null, created_at: "2026-11-13T10:00:00Z" };
}

describe("ChatPanel: новый чат и отправка", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listThreads.mockResolvedValue([thread()]);
    listMessages.mockResolvedValue([]);
  });

  it("ученик начинает чат с репетитором, к которому записывался", async () => {
    listMessageableTutors.mockResolvedValue([{ id: "tp-2", display_name: "Смирнов Пётр" }]);
    openThreadWithTutor.mockResolvedValue(thread({ id: "t-2", tutor_id: "tp-2", display_title: "Смирнов Пётр" }));
    const wrapper = mountPanel({});
    await flushPromises();

    await wrapper.findAll("button").find((b) => b.text() === "+ Новый чат")!.trigger("click");
    await flushPromises();
    await wrapper.find("[data-new-chat-contact]").trigger("click");
    await flushPromises();

    expect(openThreadWithTutor).toHaveBeenCalledWith("tp-2");
  });

  it("отправленное показывается сразу и не задваивается, когда ответ опроса пришёл посреди отправки", async () => {
    vi.useFakeTimers();
    const wrapper = mountPanel({});
    await flushPromises();

    let finishSend!: (value: unknown) => void;
    sendMessage.mockReturnValue(new Promise((resolve) => (finishSend = resolve)));
    await wrapper.find('input[placeholder="Сообщение…"]').setValue("Привет");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    // До ответа сервера сообщение уже в ленте - бледное, «отправляется…».
    expect(wrapper.find('[data-message^="pending-"]').text()).toContain("Привет");

    // Сервер уже сохранил сообщение, и очередной опрос его видит, хотя ответ на саму
    // отправку ещё не пришёл.
    listMessages.mockResolvedValue([message("m-1", "Привет")]);
    vi.advanceTimersByTime(4000);
    await flushPromises();
    const visible = () => wrapper.findAll("[data-message]").filter((m) => m.text().includes("Привет"));
    expect(visible()).toHaveLength(1);

    // Теперь пришёл ответ на отправку - и всё равно одно сообщение.
    finishSend(message("m-1", "Привет"));
    await flushPromises();
    expect(visible()).toHaveLength(1);
    expect(wrapper.find('[data-message^="pending-"]').exists()).toBe(false);
    wrapper.unmount();
    vi.useRealTimers();
  });

  it("опрос, начатый до отправки, не стирает только что отправленное", async () => {
    vi.useFakeTimers();
    const wrapper = mountPanel({});
    await flushPromises();

    // Опрос стартовал, когда сообщения ещё не было, и отвечает медленно.
    let finishPoll!: (value: unknown[]) => void;
    listMessages.mockReturnValueOnce(new Promise((resolve) => (finishPoll = resolve)));
    vi.advanceTimersByTime(4000);

    sendMessage.mockResolvedValue(message("m-2", "Вопрос"));
    await wrapper.find('input[placeholder="Сообщение…"]').setValue("Вопрос");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    finishPoll([]);
    await flushPromises();
    expect(wrapper.findAll("[data-message]").filter((m) => m.text().includes("Вопрос"))).toHaveLength(1);
    wrapper.unmount();
    vi.useRealTimers();
  });
});
