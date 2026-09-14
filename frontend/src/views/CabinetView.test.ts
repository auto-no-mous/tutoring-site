import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { reactive } from "vue";

import CabinetView from "@/views/CabinetView.vue";
import { useAuthStore } from "@/stores/auth";

const replace = vi.fn();
const route = reactive({ query: {} as Record<string, string> });

vi.mock("vue-router", () => ({
  useRoute: () => route,
  useRouter: () => ({ replace }),
}));

vi.mock("@/api/groups", () => ({
  myMemberships: vi.fn(async () => []),
}));

const notificationsState = { total: 0, unreadChat: 0, unreadSystem: 0, homeworkPending: 0 };

vi.mock("@/stores/notifications", () => ({
  useNotificationsStore: () => notificationsState,
}));

function mountCabinet(role: "tutor" | "student" = "tutor") {
  setActivePinia(createPinia());
  useAuthStore().user = { id: "u-1", role, first_name: "Иван", last_name: "Иванов" } as never;
  // shallow: дочерние вкладки для этой проверки не нужны, а их зависимости тянули бы
  // за собой половину приложения.
  return mount(CabinetView, { shallow: true });
}

function clickTab(wrapper: ReturnType<typeof mountCabinet>, label: string) {
  return wrapper.findAll("button").find((b) => b.text().includes(label))!.trigger("click");
}

describe("CabinetView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    route.query = {};
    notificationsState.total = 0;
    notificationsState.homeworkPending = 0;
  });

  it("показывает бейдж с числом невыполненных ДЗ у вкладки «ДЗ»", async () => {
    // Домашку было не видно, пока не откроешь вкладку: счётчик работает так же, как
    // у непрочитанных сообщений в чате.
    notificationsState.homeworkPending = 3;
    const wrapper = mountCabinet();
    await flushPromises();

    const tab = wrapper.findAll("button").find((b) => b.text().startsWith("ДЗ"))!;
    expect(tab.text()).toBe("ДЗ 3");
  });

  it("записывает выбранную вкладку в адрес", async () => {
    // Регрессия: вкладка жила только в состоянии компонента, поэтому обновление
    // страницы возвращало на ту, с которой в кабинет вошли по ссылке из меню.
    route.query = { tab: "chat" };
    const wrapper = mountCabinet();
    await flushPromises();

    await clickTab(wrapper, "Занятия");

    expect(replace).toHaveBeenCalledWith({ query: { tab: "bookings" } });
  });

  it("убирает ссылку на диалог при уходе из чата", async () => {
    route.query = { tab: "chat", thread: "th-1" };
    const wrapper = mountCabinet();
    await flushPromises();

    await clickTab(wrapper, "Настройки");

    expect(replace).toHaveBeenCalledWith({ query: { tab: "settings" } });
  });

  it("не трогает адрес, когда вкладка в нём уже та самая", async () => {
    route.query = { tab: "bookings" };
    const wrapper = mountCabinet();
    await flushPromises();

    await clickTab(wrapper, "Занятия");

    expect(replace).not.toHaveBeenCalled();
  });

  it("по-прежнему слушает адрес: ссылка из меню переключает вкладку", async () => {
    const wrapper = mountCabinet();
    await flushPromises();

    route.query = { tab: "settings" };
    await flushPromises();

    const settings = wrapper.findAll("button").find((b) => b.text().includes("Настройки"))!;
    // Активная вкладка подсвечивается - у неё своя рамка снизу.
    expect(settings.classes().join(" ")).toContain("border-brand-500");
  });
});
