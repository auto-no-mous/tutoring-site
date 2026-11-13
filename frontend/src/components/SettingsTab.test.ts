import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SettingsTab from "@/components/SettingsTab.vue";
import { useAuthStore } from "@/stores/auth";
import type { User } from "@/types/user";

const updateMySettings = vi.fn(async (payload: Record<string, unknown>) => ({ ...user(), ...payload }));

vi.mock("@/api/auth", () => ({
  listOAuthProviders: vi.fn(async () => []),
  startOAuth: vi.fn(),
  unlinkOAuthProvider: vi.fn(),
}));
vi.mock("@/api/bookings", () => ({ listMyRecurringSeries: vi.fn(async () => []), stopSeries: vi.fn() }));
vi.mock("@/api/tutors", () => ({ getMyProfile: vi.fn(async () => null), updateMyProfile: vi.fn() }));
const getVkLink = vi.fn(async () => ({ code: "ABCD2345", link: "https://vk.me/mytutorru?ref=ABCD2345" }));
const disconnectVk = vi.fn(async () => user({ vk_connected: false }));
const disconnectTelegram = vi.fn(async () => user({ telegram_chat_id: null }));

vi.mock("@/api/users", () => ({
  deleteMyPhoto: vi.fn(),
  disconnectTelegram: () => disconnectTelegram(),
  disconnectVk: () => disconnectVk(),
  getTelegramLinkToken: vi.fn(),
  getVkLink: () => getVkLink(),
  resendVerificationEmail: vi.fn(),
  updateMySettings: (payload: Record<string, unknown>) => updateMySettings(payload),
  uploadMyPhoto: vi.fn(),
}));

function channel() {
  return { enabled: true, new_booking: true, schedule_change: true, reminder: true, reminder_lead_minutes: 60, login: true, homework: true };
}

function user(overrides: Partial<User> = {}): User {
  return {
    id: "u-1",
    email: "student@example.com",
    display_name: "Петров Пётр",
    first_name: "Пётр",
    last_name: "Петров",
    patronymic: null,
    grade: 7,
    photo_url: null,
    role: "student",
    email_verified: true,
    is_active: true,
    timezone: "Europe/Moscow",
    telegram_chat_id: "123",
    vk_connected: false,
    answers_support: false,
    notification_settings: { telegram: channel(), email: channel(), vk: channel(), site: channel() },
    auth_providers: ["password"],
    created_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

describe("SettingsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setActivePinia(createPinia());
  });

  it.each(["student", "tutor"] as const)("открывается у пользователя с ролью %s", async (role) => {
    // Пользователь в сторе - реактивный объект; копия настроек для формы не должна
    // на нём падать (structuredClone на прокси Vue бросает DataCloneError, и вкладка
    // не отображалась вовсе).
    useAuthStore().user = user({ role });
    const wrapper = mount(SettingsTab);
    await flushPromises();

    expect(wrapper.text()).toContain("Уведомления");
    expect(wrapper.find('[data-channel="telegram"]').exists()).toBe(true);
    expect(wrapper.find('[data-channel="email"]').exists()).toBe(true);
  });

  it("правки в форме не трогают пользователя в сторе до сохранения, а сохранение их отправляет", async () => {
    const auth = useAuthStore();
    auth.user = user();
    const wrapper = mount(SettingsTab);
    await flushPromises();

    await wrapper.find('[data-channel="email"] input[type="checkbox"]').setValue(false);
    expect(auth.user!.notification_settings.email.enabled).toBe(true);

    await wrapper.findAll("button").find((b) => b.text() === "Сохранить")!.trigger("click");
    await flushPromises();

    const sent = updateMySettings.mock.calls[0][0] as { notification_settings: User["notification_settings"] };
    expect(sent.notification_settings.email.enabled).toBe(false);
    expect(sent.notification_settings.telegram.enabled).toBe(true);
  });

  it("подключает ВКонтакте: открывает диалог с сообществом и показывает код на случай, если ссылка его не донесла", async () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    useAuthStore().user = user();
    const wrapper = mount(SettingsTab);
    await flushPromises();

    // Кнопка - в блоке ВКонтакте настроек уведомлений, а не отдельно над ними.
    const vk = wrapper.find('[data-channel="vk"]');
    await vk.findAll("button").find((b) => b.text() === "Подключить ВКонтакте")!.trigger("click");
    await flushPromises();

    expect(open).toHaveBeenCalledWith("https://vk.me/mytutorru?ref=ABCD2345", "_blank");
    expect(wrapper.find('[data-channel="vk"]').text()).toContain("ABCD2345");
    open.mockRestore();
    wrapper.unmount();
  });

  it("сама замечает, что бот привязал аккаунт, без обновления страницы", async () => {
    vi.useFakeTimers();
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    const auth = useAuthStore();
    auth.user = user();
    let linked = false;
    const fetchCurrentUser = vi.spyOn(auth, "fetchCurrentUser").mockImplementation(async () => {
      auth.user = user({
        vk_connected: linked,
        notification_settings: { telegram: channel(), email: channel(), vk: { ...channel(), enabled: linked }, site: channel() },
      });
    });
    const wrapper = mount(SettingsTab);
    await flushPromises();

    await wrapper.find('[data-channel="vk"]').findAll("button").find((b) => b.text() === "Подключить ВКонтакте")!.trigger("click");
    await flushPromises();

    // Бот ещё не привязал - кнопка на месте.
    vi.advanceTimersByTime(3000);
    await flushPromises();
    expect(wrapper.find('[data-channel="vk"]').text()).toContain("Подключить ВКонтакте");

    // Человек нажал «Начать» в ВК - через несколько секунд блок переключается сам.
    linked = true;
    vi.advanceTimersByTime(3000);
    await flushPromises();
    const vk = wrapper.find('[data-channel="vk"]');
    expect(vk.text()).toContain("Подключён");
    expect(vk.find("fieldset").attributes("disabled")).toBeUndefined();

    // И больше не опрашивает.
    const calls = fetchCurrentUser.mock.calls.length;
    vi.advanceTimersByTime(30000);
    await flushPromises();
    expect(fetchCurrentUser.mock.calls.length).toBe(calls);

    wrapper.unmount();
    open.mockRestore();
    vi.useRealTimers();
  });

  it("подключённый ВКонтакте можно отключить", async () => {
    useAuthStore().user = user({ vk_connected: true });
    const wrapper = mount(SettingsTab);
    await flushPromises();

    const vk = () => wrapper.find('[data-channel="vk"]');
    expect(vk().text()).toContain("Подключён");
    await vk().findAll("button").find((b) => b.text() === "Отключить")!.trigger("click");
    await flushPromises();

    expect(disconnectVk).toHaveBeenCalled();
    expect(vk().text()).toContain("Подключить ВКонтакте");
  });

  it("Telegram отключается отдельным запросом, а не правкой настроек", async () => {
    useAuthStore().user = user();
    const wrapper = mount(SettingsTab);
    await flushPromises();

    const tg = () => wrapper.find('[data-channel="telegram"]');
    await tg().findAll("button").find((b) => b.text() === "Отключить")!.trigger("click");
    await flushPromises();

    expect(disconnectTelegram).toHaveBeenCalled();
    expect(updateMySettings).not.toHaveBeenCalled();
    expect(tg().text()).toContain("Подключить Telegram");
  });
});
