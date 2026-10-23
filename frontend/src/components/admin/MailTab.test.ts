import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MailTab from "@/components/admin/MailTab.vue";
import type { EmailLogDetail, EmailLogEntry } from "@/types/email";

const getEmail = vi.fn();

function entry(overrides: Partial<EmailLogEntry> = {}): EmailLogEntry {
  return {
    id: "e-1",
    direction: "inbound",
    kind: "inbound",
    status: "received",
    address_from: "noreply@spamhaus.example",
    address_to: "info@my-tutor.ru",
    subject: "Подтвердите заявку",
    body_preview: "Перейдите по ссылке https://check.example/confirm?t=1 чтобы",
    user_id: null,
    sent_by_id: null,
    error: null,
    created_at: "2026-10-23T10:00:00Z",
    ...overrides,
  };
}

const entries: EmailLogEntry[] = [entry(), entry({ id: "e-old", subject: "Старое", body_preview: "только начало" })];

vi.mock("@/api/admin", () => ({
  listEmails: vi.fn(async () => ({ entries, total: entries.length, page: 1, page_size: 50 })),
  getEmailStats: vi.fn(async () => ({ sent: 0, failed: 0, received: 0, by_kind: {}, window_days: 30 })),
  listStudents: vi.fn(async () => []),
  listTutors: vi.fn(async () => []),
  sendAdminEmail: vi.fn(),
  getEmail: (id: string) => getEmail(id),
}));

function detail(overrides: Partial<EmailLogDetail> = {}): EmailLogDetail {
  return { ...entry(), body_text: null, ...overrides };
}

const card = (wrapper: ReturnType<typeof mount>, subject: string) =>
  wrapper.findAll(".surface-card").find((c) => c.text().includes(subject))!;
const button = (el: ReturnType<ReturnType<typeof mount>["find"]>, text: string) =>
  el.findAll("button").find((b) => b.text().includes(text))!;

describe("MailTab: чтение письма", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setActivePinia(createPinia());
  });

  it("ссылки в превью кликабельны", async () => {
    const wrapper = mount(MailTab);
    await flushPromises();

    const link = card(wrapper, "Подтвердите заявку").find("a");
    expect(link.attributes("href")).toBe("https://check.example/confirm?t=1");
    expect(link.attributes("target")).toBe("_blank");
    expect(link.attributes("rel")).toContain("noopener");
  });

  it("подгружает полный текст по кнопке и сворачивает обратно", async () => {
    const full = "Здравствуйте!\n\nПерейдите по ссылке https://check.example/confirm?t=1 чтобы подтвердить.\n\nКонец письма.";
    getEmail.mockResolvedValue(detail({ body_text: full }));
    const wrapper = mount(MailTab);
    await flushPromises();
    const item = card(wrapper, "Подтвердите заявку");

    await button(item, "Показать полностью").trigger("click");
    await flushPromises();

    expect(getEmail).toHaveBeenCalledWith("e-1");
    const text = item.find("[data-full-text]");
    expect(text.text()).toContain("Конец письма.");
    expect(text.find("a").attributes("href")).toBe("https://check.example/confirm?t=1");

    await button(item, "Свернуть").trigger("click");
    expect(item.find("[data-full-text]").exists()).toBe(false);
  });

  it("разметку из письма показывает как текст, а не как HTML", async () => {
    getEmail.mockResolvedValue(detail({ body_text: '<img src=x onerror="alert(1)"> <b>жирный</b>' }));
    const wrapper = mount(MailTab);
    await flushPromises();
    const item = card(wrapper, "Подтвердите заявку");

    await button(item, "Показать полностью").trigger("click");
    await flushPromises();

    const text = item.find("[data-full-text]");
    expect(text.find("img").exists()).toBe(false);
    expect(text.find("b").exists()).toBe(false);
    expect(text.text()).toContain("<b>жирный</b>");
  });

  it("у старого письма без полного текста показывает начало и объясняет почему", async () => {
    getEmail.mockResolvedValue(detail({ id: "e-old", subject: "Старое", body_preview: "только начало", body_text: null }));
    const wrapper = mount(MailTab);
    await flushPromises();
    const item = card(wrapper, "Старое");

    await button(item, "Показать полностью").trigger("click");
    await flushPromises();

    expect(item.find("[data-full-text]").text()).toContain("только начало");
    expect(item.text()).toContain("Полный текст этого письма не сохранялся");
  });
});
