<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { getAdminRescheduleDates, getAdminRescheduleSlots, rescheduleBooking } from "@/api/admin";
import type { Booking } from "@/types/booking";
import type { Slot } from "@/types/tutor";
import { addDaysIso, formatDate, formatDateTimeWithMsk, formatTime, todayIso } from "@/utils/time";

const props = defineProps<{ booking: Booking }>();
const emit = defineEmits<{ close: []; rescheduled: [] }>();

const step = ref<1 | 2 | 3>(1);
const currentDuration = Math.round((new Date(props.booking.end_at).getTime() - new Date(props.booking.start_at).getTime()) / 60000);
const duration = ref(currentDuration);
const availableDates = ref<string[]>([]);
const selectedDate = ref<string | null>(null);
const slots = ref<Slot[]>([]);
const selectedSlot = ref<Slot | null>(null);
const isLoading = ref(true);
const error = ref<string | null>(null);
const isSubmitting = ref(false);

const durationChanged = computed(() => duration.value !== currentDuration);

async function loadDates(): Promise<void> {
  isLoading.value = true;
  error.value = null;
  selectedDate.value = null;
  selectedSlot.value = null;
  step.value = 1;
  try {
    availableDates.value = await getAdminRescheduleDates(props.booking.id, todayIso(), addDaysIso(todayIso(), 60), duration.value);
  } finally {
    isLoading.value = false;
  }
}

async function pickDate(date: string): Promise<void> {
  selectedDate.value = date;
  step.value = 2;
  isLoading.value = true;
  error.value = null;
  try {
    slots.value = await getAdminRescheduleSlots(props.booking.id, date, duration.value);
  } finally {
    isLoading.value = false;
  }
}

function pickSlot(slot: Slot): void {
  if (!slot.available) return;
  selectedSlot.value = slot;
  step.value = 3;
}

async function confirm(): Promise<void> {
  if (!selectedSlot.value) return;
  isSubmitting.value = true;
  error.value = null;
  try {
    await rescheduleBooking(props.booking.id, selectedSlot.value.start_at, durationChanged.value ? duration.value : undefined);
    emit("rescheduled");
  } catch {
    error.value = "Перенос недоступен: время уже занято.";
  } finally {
    isSubmitting.value = false;
  }
}

watch(duration, loadDates);
loadDates();
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="emit('close')">
    <div class="w-full max-w-md rounded-lg bg-white p-4 shadow-xl dark:bg-slate-900">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-medium">Перенос занятия</h2>
        <button type="button" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200" @click="emit('close')">✕</button>
      </div>
      <p class="mt-1 text-sm text-slate-500">Текущее время: {{ formatDateTimeWithMsk(booking.start_at) }}</p>

      <label class="mt-3 flex items-center gap-2 text-sm">
        Длительность, мин
        <input
          v-model.number="duration"
          type="number"
          min="5"
          step="5"
          class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700"
        />
      </label>

      <!-- Step 1: date -->
      <div v-if="step === 1" class="mt-4">
        <p v-if="isLoading" class="text-sm text-slate-400">Загрузка дат…</p>
        <p v-else-if="availableDates.length === 0" class="text-sm text-slate-400">
          Нет свободных дат в ближайшие 2 месяца при такой длительности.
        </p>
        <div v-else class="flex max-h-72 flex-wrap gap-2 overflow-y-auto">
          <button
            v-for="date in availableDates"
            :key="date"
            type="button"
            class="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:border-slate-500 dark:border-slate-700"
            @click="pickDate(date)"
          >
            {{ formatDate(date + "T00:00:00Z") }}
          </button>
        </div>
      </div>

      <!-- Step 2: slot -->
      <div v-else-if="step === 2" class="mt-4">
        <button type="button" class="mb-3 text-sm text-slate-500 underline" @click="step = 1">← Дата</button>
        <p v-if="isLoading" class="text-sm text-slate-400">Загрузка времени…</p>
        <p v-else-if="slots.length === 0" class="text-sm text-slate-400">В этот день нет доступного времени.</p>
        <div v-else class="grid max-h-72 grid-cols-3 gap-2 overflow-y-auto sm:grid-cols-4">
          <button
            v-for="slot in slots"
            :key="slot.start_at"
            type="button"
            :disabled="!slot.available"
            class="rounded-md border px-2 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-30"
            :class="
              slot.available
                ? 'border-slate-300 hover:border-slate-500 dark:border-slate-700'
                : 'border-slate-200 dark:border-slate-800'
            "
            @click="pickSlot(slot)"
          >
            {{ formatTime(slot.start_at) }}
          </button>
        </div>
      </div>

      <!-- Step 3: confirm -->
      <div v-else-if="step === 3 && selectedSlot" class="mt-4 flex flex-col gap-3">
        <button type="button" class="text-sm text-slate-500 underline" @click="step = 2">← Время</button>
        <p class="text-sm">
          Новое время: <span class="font-medium">{{ formatDateTimeWithMsk(selectedSlot.start_at) }}</span>
          <span v-if="durationChanged"> ({{ duration }} мин)</span>
        </p>
        <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
        <div class="flex gap-2">
          <button
            type="button"
            :disabled="isSubmitting"
            class="rounded-md bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"
            @click="confirm"
          >
            Подтвердить перенос
          </button>
          <button type="button" class="rounded-md border border-slate-300 px-4 py-2 text-sm dark:border-slate-700" @click="emit('close')">
            Отмена
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
