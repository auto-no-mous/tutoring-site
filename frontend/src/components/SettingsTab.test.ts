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
vi.mock("@/api/users", () => ({
  deleteMyPhoto: vi.fn(),
  getTelegramLinkToken: vi.fn(),
  resendVerificationEmail: vi.fn(),
  updateMySettings: (payload: Record<string, unknown>) => updateMySettings(payload),
  uploadMyPhoto: vi.fn(),
}));

function channel() {
  return { enabled: true, new_booking: true, schedule_change: true, reminder: true, reminder_lead_minutes: 60 };
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
    notification_settings: { telegram: channel(), email: channel() },
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
});
