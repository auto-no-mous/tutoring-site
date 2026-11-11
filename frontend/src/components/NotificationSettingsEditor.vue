<script setup lang="ts">
import type {
  ChannelNotificationSettings,
  NotificationChannel,
  NotificationSettings,
  NotificationTarget,
} from "@/types/user";

// Иерархические настройки уведомлений: канал - родительский пункт, под ним - что
// именно в него слать. Раньше был один переключатель из четырёх кнопок («почта и
// мессенджер / только почта / только мессенджер / не присылать»), и каждый новый
// канал умножал бы число вариантов.
const props = defineProps<{
  modelValue: NotificationSettings;
  // Куда слать: без привязанного Telegram или без почты канал включить нельзя.
  available: Record<NotificationChannel, boolean>;
  unavailableHint: Record<NotificationChannel, string>;
}>();
const emit = defineEmits<{ "update:modelValue": [NotificationSettings] }>();

type EventKey = "new_booking" | "schedule_change" | "homework" | "login";

// У каждого канала - только те пункты, которые в него действительно приходят. В чат
// сайта не пишутся ни новые записи, ни входы в аккаунт: о входе там прочитает лишь
// тот, кто уже вошёл, - поэтому он идёт только в мессенджеры и на почту.
const CHANNELS: { value: NotificationTarget; label: string; events: EventKey[] }[] = [
  { value: "telegram", label: "Telegram", events: ["new_booking", "schedule_change", "homework", "login"] },
  { value: "email", label: "Почта", events: ["new_booking", "schedule_change", "homework", "login"] },
  { value: "vk", label: "ВКонтакте", events: ["new_booking", "schedule_change", "homework", "login"] },
  { value: "site", label: "На сайте — «Системные уведомления» в чате", events: ["schedule_change", "homework"] },
];

const EVENT_LABELS: Record<EventKey, string> = {
  new_booking: "Новые записи",
  schedule_change: "Переносы и отмены",
  homework: "Домашние задания",
  login: "Входы в аккаунт",
};

function update(channel: NotificationTarget, patch: Partial<ChannelNotificationSettings>): void {
  emit("update:modelValue", { ...props.modelValue, [channel]: { ...props.modelValue[channel], ...patch } });
}

// Чат сайта есть у всех: адреса, которого может не быть, у него нет.
function isAvailable(channel: NotificationTarget): boolean {
  return channel === "site" || props.available[channel];
}

function isOn(channel: NotificationTarget): boolean {
  return isAvailable(channel) && props.modelValue[channel].enabled;
}

function onLeadInput(channel: NotificationTarget, event: Event): void {
  const value = (event.target as HTMLInputElement).valueAsNumber;
  if (Number.isFinite(value)) update(channel, { reminder_lead_minutes: value });
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div
      v-for="channel in CHANNELS"
      :key="channel.value"
      :data-channel="channel.value"
      class="rounded-lg border border-slate-200 p-3 dark:border-slate-800"
    >
      <div class="flex flex-wrap items-center justify-between gap-2">
        <label class="flex items-center gap-2 font-medium" :class="isAvailable(channel.value) ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'">
          <input
            type="checkbox"
            class="h-4 w-4"
            :checked="isOn(channel.value)"
            :disabled="!isAvailable(channel.value)"
            @change="update(channel.value, { enabled: ($event.target as HTMLInputElement).checked })"
          />
          {{ channel.label }}
        </label>
        <!-- Подключение мессенджера - прямо в его блоке: «Подключён · Отключить» или
             кнопка «Подключить». Раньше эти кнопки стояли выше, отдельно от пунктов, к
             которым относятся. -->
        <slot :name="`connection-${channel.value}`" />
      </div>
      <p
        v-if="channel.value !== 'site' && !available[channel.value] && !$slots[`connection-${channel.value}`]"
        class="mt-1 pl-6 text-xs text-slate-400"
      >
        {{ unavailableHint[channel.value] }}
      </p>

      <!-- Пока канал не подключён, его пункты видны, но неактивны: видно, что будет
           приходить после подключения. Выключенный самим человеком канал - свёрнут. -->
      <fieldset
        v-if="isOn(channel.value) || !isAvailable(channel.value)"
        :disabled="!isAvailable(channel.value)"
        class="mt-2 flex flex-col gap-2 border-l-2 border-slate-200 pl-4 text-sm disabled:opacity-50 dark:border-slate-700"
      >
        <label v-for="key in channel.events" :key="key" class="flex items-center gap-2">
          <input
            type="checkbox"
            class="h-4 w-4"
            :checked="modelValue[channel.value][key]"
            @change="update(channel.value, { [key]: ($event.target as HTMLInputElement).checked })"
          />
          {{ EVENT_LABELS[key] }}
        </label>
        <div class="flex flex-wrap items-center gap-2">
          <label class="flex items-center gap-2">
            <input
              type="checkbox"
              class="h-4 w-4"
              :checked="modelValue[channel.value].reminder"
              @change="update(channel.value, { reminder: ($event.target as HTMLInputElement).checked })"
            />
            Напоминание о занятии за
          </label>
          <input
            type="number"
            min="1"
            max="10080"
            :value="modelValue[channel.value].reminder_lead_minutes"
            :disabled="!modelValue[channel.value].reminder"
            :aria-label="`За сколько минут напоминать о занятии: ${channel.label}`"
            class="w-20 rounded-md border border-slate-300 bg-transparent px-2 py-1 disabled:opacity-50 dark:border-slate-700"
            @input="onLeadInput(channel.value, $event)"
          />
          минут
        </div>
      </fieldset>
    </div>
  </div>
</template>
