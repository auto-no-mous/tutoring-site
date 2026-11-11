import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import NotificationSettingsEditor from "@/components/NotificationSettingsEditor.vue";
import type { ChannelNotificationSettings, NotificationSettings } from "@/types/user";

function channel(overrides: Partial<ChannelNotificationSettings> = {}): ChannelNotificationSettings {
  return { enabled: true, new_booking: true, schedule_change: true, reminder: true, reminder_lead_minutes: 60, login: true, homework: true, ...overrides };
}

function mountEditor(
  settings: NotificationSettings = { telegram: channel(), email: channel(), vk: channel(), site: channel() },
  available = { telegram: true, email: true, vk: true },
) {
  return mount(NotificationSettingsEditor, {
    props: {
      modelValue: settings,
      available,
      unavailableHint: { telegram: "Telegram не подключён", email: "Почта не указана", vk: "ВКонтакте не подключён" },
    },
  });
}

function block(wrapper: ReturnType<typeof mount>, name: string) {
  return wrapper.find(`[data-channel="${name}"]`);
}

describe("NotificationSettingsEditor", () => {
  it("под включённым каналом показывает его пункты, под выключенным - нет", () => {
    const wrapper = mountEditor({ telegram: channel(), email: channel({ enabled: false }), vk: channel(), site: channel() });

    expect(block(wrapper, "telegram").text()).toContain("Новые записи");
    expect(block(wrapper, "telegram").text()).toContain("Переносы и отмены");
    expect(block(wrapper, "telegram").text()).toContain("Напоминание о занятии за");
    expect(block(wrapper, "email").text()).not.toContain("Новые записи");
  });

  it("меняет только свой канал и свой пункт", async () => {
    const wrapper = mountEditor();

    const [, reschedule] = block(wrapper, "email").findAll('input[type="checkbox"]').slice(1);
    await reschedule.setValue(false);

    const emitted = wrapper.emitted("update:modelValue")!.at(-1)![0] as NotificationSettings;
    expect(emitted.email.schedule_change).toBe(false);
    expect(emitted.email.new_booking).toBe(true);
    expect(emitted.telegram).toEqual(channel());
  });

  it("у каждого канала своё время напоминания", async () => {
    const wrapper = mountEditor();

    await block(wrapper, "telegram").find('input[type="number"]').setValue(15);

    const emitted = wrapper.emitted("update:modelValue")!.at(-1)![0] as NotificationSettings;
    expect(emitted.telegram.reminder_lead_minutes).toBe(15);
    expect(emitted.email.reminder_lead_minutes).toBe(60);
  });

  it("поле минут неактивно, пока напоминание выключено", () => {
    const wrapper = mountEditor({ telegram: channel({ reminder: false }), email: channel(), vk: channel(), site: channel() });

    expect(block(wrapper, "telegram").find('input[type="number"]').attributes("disabled")).toBeDefined();
    expect(block(wrapper, "email").find('input[type="number"]').attributes("disabled")).toBeUndefined();
  });

  it("канал, в который некуда слать, выключен, а его пункты видны, но неактивны", () => {
    const wrapper = mountEditor(undefined, { telegram: false, email: true, vk: true });

    const parent = block(wrapper, "telegram").find('input[type="checkbox"]');
    expect(parent.attributes("disabled")).toBeDefined();
    expect((parent.element as HTMLInputElement).checked).toBe(false);
    expect(block(wrapper, "telegram").text()).toContain("Telegram не подключён");
    expect(block(wrapper, "telegram").text()).toContain("Новые записи");
    expect(block(wrapper, "telegram").find("fieldset").attributes("disabled")).toBeDefined();
  });

  it("кнопка подключения - прямо в блоке канала, вместо подсказки", () => {
    const wrapper = mount(NotificationSettingsEditor, {
      props: {
        modelValue: { telegram: channel(), email: channel(), vk: channel(), site: channel() },
        available: { telegram: true, email: true, vk: false },
        unavailableHint: { telegram: "", email: "", vk: "ВКонтакте не подключён" },
      },
      slots: { "connection-vk": "<button>Подключить ВКонтакте</button>" },
    });

    const vk = block(wrapper, "vk");
    expect(vk.text()).toContain("Подключить ВКонтакте");
    expect(vk.text()).not.toContain("ВКонтакте не подключён");
  });

  it("домашние задания настраиваются в каждом канале, включая чат сайта", () => {
    const wrapper = mountEditor();
    for (const name of ["telegram", "email", "vk", "site"]) {
      expect(block(wrapper, name).text()).toContain("Домашние задания");
    }
    // Подсказку под чатом сайта убрали - она повторяла очевидное.
    expect(block(wrapper, "site").text()).not.toContain("Сюда же приходят");
  });

  it("чат сайта настраивается всегда, но без новых записей и входов", () => {
    const wrapper = mountEditor(undefined, { telegram: false, email: false, vk: false });

    const site = block(wrapper, "site");
    expect(site.find('input[type="checkbox"]').attributes("disabled")).toBeUndefined();
    expect(site.text()).toContain("Переносы и отмены");
    expect(site.text()).toContain("Напоминание о занятии за");
    expect(site.text()).not.toContain("Новые записи");
    expect(site.text()).not.toContain("Входы в аккаунт");
  });

  it("входы в аккаунт выключаются отдельно в Telegram и на почте", async () => {
    const wrapper = mountEditor();
    expect(block(wrapper, "telegram").text()).toContain("Входы в аккаунт");

    const login = block(wrapper, "email")
      .findAll("label")
      .find((l) => l.text() === "Входы в аккаунт")!
      .find("input");
    await login.setValue(false);

    const emitted = wrapper.emitted("update:modelValue")!.at(-1)![0] as NotificationSettings;
    expect(emitted.email.login).toBe(false);
    expect(emitted.telegram.login).toBe(true);
  });
});
