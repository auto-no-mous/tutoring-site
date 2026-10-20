import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import NotificationSettingsEditor from "@/components/NotificationSettingsEditor.vue";
import type { ChannelNotificationSettings, NotificationSettings } from "@/types/user";

function channel(overrides: Partial<ChannelNotificationSettings> = {}): ChannelNotificationSettings {
  return { enabled: true, new_booking: true, schedule_change: true, reminder: true, reminder_lead_minutes: 60, ...overrides };
}

function mountEditor(
  settings: NotificationSettings = { telegram: channel(), email: channel() },
  available = { telegram: true, email: true },
) {
  return mount(NotificationSettingsEditor, {
    props: {
      modelValue: settings,
      available,
      unavailableHint: { telegram: "Telegram не подключён", email: "Почта не указана" },
    },
  });
}

function block(wrapper: ReturnType<typeof mount>, name: string) {
  return wrapper.find(`[data-channel="${name}"]`);
}

describe("NotificationSettingsEditor", () => {
  it("под включённым каналом показывает его пункты, под выключенным - нет", () => {
    const wrapper = mountEditor({ telegram: channel(), email: channel({ enabled: false }) });

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
    const wrapper = mountEditor({ telegram: channel({ reminder: false }), email: channel() });

    expect(block(wrapper, "telegram").find('input[type="number"]').attributes("disabled")).toBeDefined();
    expect(block(wrapper, "email").find('input[type="number"]').attributes("disabled")).toBeUndefined();
  });

  it("канал, в который некуда слать, выключен и объясняет почему", () => {
    const wrapper = mountEditor(undefined, { telegram: false, email: true });

    const parent = block(wrapper, "telegram").find('input[type="checkbox"]');
    expect(parent.attributes("disabled")).toBeDefined();
    expect((parent.element as HTMLInputElement).checked).toBe(false);
    expect(block(wrapper, "telegram").text()).toContain("Telegram не подключён");
    expect(block(wrapper, "telegram").text()).not.toContain("Новые записи");
  });
});
