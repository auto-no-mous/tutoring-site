<script setup lang="ts">
import type { ChannelNotificationSettings, NotificationChannel, NotificationSettings } from "@/types/user";

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

const CHANNELS: { value: NotificationChannel; label: string }[] = [
  { value: "telegram", label: "Telegram" },
  { value: "email", label: "Почта" },
];

const EVENTS: { key: "new_booking" | "schedule_change"; label: string }[] = [
  { key: "new_booking", label: "Новые записи" },
  { key: "schedule_change", label: "Переносы и отмены" },
];

function update(channel: NotificationChannel, patch: Partial<ChannelNotificationSettings>): void {
  emit("update:modelValue", { ...props.modelValue, [channel]: { ...props.modelValue[channel], ...patch } });
}

function isOn(channel: NotificationChannel): boolean {
  return props.available[channel] && props.modelValue[channel].enabled;
}

function onLeadInput(channel: NotificationChannel, event: Event): void {
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
      <label class="flex items-center gap-2 font-medium" :class="available[channel.value] ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'">
        <input
          type="checkbox"
          class="h-4 w-4"
          :checked="isOn(channel.value)"
          :disabled="!available[channel.value]"
          @change="update(channel.value, { enabled: ($event.target as HTMLInputElement).checked })"
        />
        {{ channel.label }}
      </label>
      <p v-if="!available[channel.value]" class="mt-1 pl-6 text-xs text-slate-400">{{ unavailableHint[channel.value] }}</p>

      <div v-if="isOn(channel.value)" class="mt-2 flex flex-col gap-2 border-l-2 border-slate-200 pl-4 text-sm dark:border-slate-700">
        <label v-for="event in EVENTS" :key="event.key" class="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            class="h-4 w-4"
            :checked="modelValue[channel.value][event.key]"
            @change="update(channel.value, { [event.key]: ($event.target as HTMLInputElement).checked })"
          />
          {{ event.label }}
        </label>
        <div class="flex flex-wrap items-center gap-2">
          <label class="flex cursor-pointer items-center gap-2">
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
      </div>
    </div>
  </div>
</template>
