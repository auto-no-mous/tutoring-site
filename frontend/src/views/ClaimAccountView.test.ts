import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ClaimAccountView from "@/views/ClaimAccountView.vue";

const getClaimPreview = vi.fn();
const claimWithPassword = vi.fn();
const listOAuthProviders = vi.fn();
const startOAuth = vi.fn();

vi.mock("@/api/auth", () => ({
  getClaimPreview: (token: string) => getClaimPreview(token),
  claimWithPassword: (payload: unknown) => claimWithPassword(payload),
  listOAuthProviders: () => listOAuthProviders(),
  startOAuth: (provider: string, redirectTo: string | null, claimToken: string | null) =>
    startOAuth(provider, redirectTo, claimToken),
}));

const applySession = vi.fn();
vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({ applySession }),
}));

const replace = vi.fn();
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { token: "claim-token" } }),
  useRouter: () => ({ replace }),
}));

function mountView() {
  setActivePinia(createPinia());
  return mount(ClaimAccountView, {
    global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
  });
}

describe("ClaimAccountView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimPreview.mockResolvedValue({
      display_name: "Петров Пётр",
      grade: 9,
      tutor_display_name: "Иванов Иван",
    });
    listOAuthProviders.mockResolvedValue([{ provider: "yandex", label: "Яндекс ID", enabled: true }]);
  });

  it("показывает, чей профиль забирают, до выбора способа входа", async () => {
    const wrapper = mountView();
    await flushPromises();

    expect(getClaimPreview).toHaveBeenCalledWith("claim-token");
    expect(wrapper.text()).toContain("Петров Пётр");
    expect(wrapper.text()).toContain("Иванов Иван");
  });

  it("привязывает почту с паролем и впускает в кабинет", async () => {
    claimWithPassword.mockResolvedValue({
      user: { id: "u-1" },
      tokens: { access_token: "a", refresh_token: "r" },
    });

    const wrapper = mountView();
    await flushPromises();

    await wrapper.find("input[type=email]").setValue("student@example.com");
    await wrapper.find("input[type=password]").setValue("supersecret1");

    // Без согласия на обработку ПД запрос не уходит: репетитор, заводя профиль, за
    // человека согласиться не мог.
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    expect(claimWithPassword).not.toHaveBeenCalled();

    await wrapper.find("input[type=checkbox]").setValue(true);
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(claimWithPassword).toHaveBeenCalledWith({
      token: "claim-token",
      email: "student@example.com",
      password: "supersecret1",
      pd_consent: true,
    });
    expect(applySession).toHaveBeenCalledWith({ access_token: "a", refresh_token: "r" }, { id: "u-1" });
    expect(replace).toHaveBeenCalledWith("/cabinet");
  });

  it("уводит к провайдеру вместе с токеном приглашения", async () => {
    // jsdom не умеет переходить по адресу и шумит в stderr - подменяем location.
    Object.defineProperty(window, "location", { value: { href: "" }, writable: true });
    startOAuth.mockResolvedValue("https://oauth.yandex.ru/authorize?x=1");
    const wrapper = mountView();
    await flushPromises();

    await wrapper.findAll("button").at(-1)!.trigger("click");
    await flushPromises();

    // Без claim_token провайдер завёл бы новый аккаунт вместо привязки к профилю.
    expect(startOAuth).toHaveBeenCalledWith("yandex", "/cabinet", "claim-token");
  });

  it("объясняет недействительную ссылку вместо формы", async () => {
    getClaimPreview.mockRejectedValue(new Error("нет такой ссылки"));

    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain("Ссылка не работает");
    expect(wrapper.find("input[type=email]").exists()).toBe(false);
  });
});
