import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OAuthCallbackView from "@/views/OAuthCallbackView.vue";

const finishOAuth = vi.fn();
const completeOAuthSignup = vi.fn();

vi.mock("@/api/auth", () => ({
  finishOAuth: (...args: unknown[]) => finishOAuth(...args),
  completeOAuthSignup: (...args: unknown[]) => completeOAuthSignup(...args),
}));

const applySession = vi.fn();
const fetchCurrentUser = vi.fn();

vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({ applySession, fetchCurrentUser }),
}));

const replace = vi.fn();
let query: Record<string, string> = {};

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { provider: "vk" }, query }),
  useRouter: () => ({ replace }),
}));

function mountView() {
  setActivePinia(createPinia());
  return mount(OAuthCallbackView, {
    global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
  });
}

describe("OAuthCallbackView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    query = { code: "auth-code", state: "state-1", device_id: "device-1" };
  });

  it("обменивает код и уводит вошедшего пользователя по redirect_to", async () => {
    finishOAuth.mockResolvedValue({
      status: "authenticated",
      user: { id: "u-1" },
      tokens: { access_token: "a", refresh_token: "r" },
      redirect_to: "/cabinet?tab=bookings",
    });

    mountView();
    await flushPromises();

    // device_id из колбэка VK обязан дойти до бэкенда - без него обмен кода не проходит.
    expect(finishOAuth).toHaveBeenCalledWith("vk", {
      code: "auth-code",
      state: "state-1",
      device_id: "device-1",
    });
    expect(applySession).toHaveBeenCalledWith({ access_token: "a", refresh_token: "r" }, { id: "u-1" });
    expect(replace).toHaveBeenCalledWith("/cabinet?tab=bookings");
  });

  it("после привязки обновляет пользователя и возвращает в настройки", async () => {
    finishOAuth.mockResolvedValue({ status: "linked", redirect_to: null });

    mountView();
    await flushPromises();

    expect(fetchCurrentUser).toHaveBeenCalled();
    expect(replace).toHaveBeenCalledWith("/cabinet?tab=settings");
  });

  it("для нового аккаунта спрашивает только роль, класс и согласие", async () => {
    finishOAuth.mockResolvedValue({
      status: "signup_required",
      signup_token: "signup-token",
      prefill: {
        email: "petr@yandex.ru",
        first_name: "Пётр",
        last_name: "Петров",
        avatar_url: "https://avatars.yandex.net/get-yapic/abc/islands-200",
      },
      redirect_to: null,
    });

    const wrapper = mountView();
    await flushPromises();

    // Имя и почта пришли от провайдера - показываем их, но не спрашиваем заново.
    expect(wrapper.text()).toContain("Петров Пётр");
    expect(wrapper.text()).toContain("petr@yandex.ru");
    expect(wrapper.find("input[placeholder]").exists()).toBe(false);
    expect(wrapper.find("img").attributes("src")).toContain("avatars.yandex.net");
    expect(replace).not.toHaveBeenCalled();

    // Без согласия на обработку ПД форма не уходит на сервер.
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    expect(completeOAuthSignup).not.toHaveBeenCalled();

    await wrapper.find("select").setValue(9);
    await wrapper.find("input[type=checkbox]").setValue(true);
    completeOAuthSignup.mockResolvedValue({
      user: { id: "u-2" },
      tokens: { access_token: "a2", refresh_token: "r2" },
    });
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(completeOAuthSignup).toHaveBeenCalledWith({
      signup_token: "signup-token",
      role: "student",
      grade: 9,
      first_name: null,
      last_name: null,
      pd_consent: true,
    });
    expect(replace).toHaveBeenCalledWith("/cabinet");
  });

  it("у репетитора класс не спрашивает и не отправляет", async () => {
    finishOAuth.mockResolvedValue({
      status: "signup_required",
      signup_token: "signup-token",
      prefill: { email: null, first_name: "Пётр", last_name: "Петров", avatar_url: null },
      redirect_to: null,
    });
    completeOAuthSignup.mockResolvedValue({
      user: { id: "u-3" },
      tokens: { access_token: "a3", refresh_token: "r3" },
    });

    const wrapper = mountView();
    await flushPromises();

    const [, tutorButton] = wrapper.findAll("form button[type=button]");
    await tutorButton.trigger("click");
    expect(wrapper.find("select").exists()).toBe(false);

    await wrapper.find("input[type=checkbox]").setValue(true);
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(completeOAuthSignup).toHaveBeenCalledWith(
      expect.objectContaining({ role: "tutor", grade: null }),
    );
  });

  it("спрашивает ФИО, только если провайдер его не отдал", async () => {
    finishOAuth.mockResolvedValue({
      status: "signup_required",
      signup_token: "signup-token",
      prefill: { email: null, first_name: null, last_name: null, avatar_url: null },
      redirect_to: null,
    });
    completeOAuthSignup.mockResolvedValue({
      user: { id: "u-4" },
      tokens: { access_token: "a4", refresh_token: "r4" },
    });

    const wrapper = mountView();
    await flushPromises();

    const inputs = wrapper.findAll("input[placeholder]");
    expect(inputs).toHaveLength(2);
    await inputs[0].setValue("Иванова");
    await inputs[1].setValue("Мария");
    await wrapper.find("input[type=checkbox]").setValue(true);
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(completeOAuthSignup).toHaveBeenCalledWith(
      expect.objectContaining({ first_name: "Мария", last_name: "Иванова" }),
    );
  });

  it("показывает отказ провайдера вместо запроса к бэкенду", async () => {
    query = { error: "access_denied", error_description: "Пользователь отказал в доступе" };

    const wrapper = mountView();
    await flushPromises();

    expect(finishOAuth).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("Пользователь отказал в доступе");
  });
});
