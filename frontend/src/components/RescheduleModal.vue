<script setup lang="ts">
import { X } from "lucide-vue-next";
import { DialogClose, DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui";
import { ArrowLeft } from "lucide-vue-next";
import { ref, watch } from "vue";

import { getRescheduleDates, getRescheduleSlots, rescheduleBooking } from "@/api/bookings";
import BookingCalendar from "@/components/BookingCalendar.vue";
import type { Booking } from "@/types/booking";
import type { Slot } from "@/types/tutor";
import { addDaysIso, formatDateTimeWithMsk, formatTime, todayIso } from "@/utils/time";

const props = defineProps<{ booking: Booking }>();
const emit = defineEmits<{ close: []; rescheduled: [] }>();

const step = ref<1 | 2 | 3>(1);
const availableDates = ref<string[]>([]);
const selectedDate = ref<string | null>(null);
const slots = ref<Slot[]>([]);
const selectedSlot = ref<Slot | null>(null);
const isLoading = ref(true);
const error = ref<string | null>(null);
const isSubmitting = ref(false);

async function loadDates(): Promise<void> {
  isLoading.value = true;
  error.value = null;
  try {
    availableDates.value = await getRescheduleDates(props.booking.id, todayIso(), addDaysIso(todayIso(), 30));
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
    slots.value = await getRescheduleSlots(props.booking.id, date);
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
    await rescheduleBooking(props.booking.id, selectedSlot.value.start_at);
    emit("rescheduled");
  } catch {
    error.value = "Перенос недоступен: время уже занято, либо нарушены сроки/лимит переносов репетитора.";
  } finally {
    isSubmitting.value = false;
  }
}

watch(() => props.booking.id, loadDates, { immediate: true });
</script>

<template>
  <!-- Диалог Reka UI: фокус запирается внутри окна, Escape и клик по подложке
       закрывают его, а фокус возвращается на вызвавшую кнопку. -->
  <DialogRoot :open="true" @update:open="(open) => !open && emit('close')">
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-50 bg-black/40 data-[state=closed]:animate-fade-out data-[state=open]:animate-fade-in"
      />
      <DialogContent
        class="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-5 shadow-xl
          data-[state=closed]:animate-pop-out data-[state=open]:animate-pop-in dark:bg-slate-900"
        :aria-describedby="undefined"
      >
        <div class="flex items-center justify-between gap-4">
          <DialogTitle class="text-lg font-semibold">Перенос занятия</DialogTitle>
          <DialogClose class="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200">
            <X class="h-4 w-4" />
          </DialogClose>
        </div>
        <p class="mt-1 text-sm text-slate-500">Текущее время: {{ formatDateTimeWithMsk(booking.start_at) }}</p>

        <!-- Step 1: date -->
        <div v-if="step === 1" class="mt-4">
          <p v-if="isLoading" class="text-sm text-slate-400">Загрузка дат…</p>
          <p v-else-if="availableDates.length === 0" class="text-sm text-slate-400">
            Нет свободных дат в ближайший месяц.
          </p>
          <BookingCalendar v-else :available-dates="availableDates" @select="pickDate" />
        </div>

        <!-- Step 2: slot -->
        <div v-else-if="step === 2" class="mt-4">
          <button type="button" class="back-link mb-3" @click="step = 1"><ArrowLeft class="h-4 w-4" />Дата</button>
          <p v-if="isLoading" class="text-sm text-slate-400">Загрузка времени…</p>
          <div v-else class="grid max-h-72 grid-cols-3 gap-2 overflow-y-auto sm:grid-cols-4">
            <button
              v-for="slot in slots"
              :key="slot.start_at"
              type="button"
              :disabled="!slot.available"
              class="rounded-lg border px-2 py-2 text-sm font-medium transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-30"
              :class="
                slot.available
                  ? 'border-slate-200 hover:-translate-y-0.5 hover:border-brand-400 hover:bg-brand-50 dark:border-slate-700 dark:hover:border-brand-500 dark:hover:bg-brand-900/20'
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
          <button type="button" class="back-link" @click="step = 2"><ArrowLeft class="h-4 w-4" />Время</button>
          <p class="text-sm">
            Новое время: <span class="font-medium">{{ formatDateTimeWithMsk(selectedSlot.start_at) }}</span>
          </p>
          <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
          <div class="flex gap-2">
            <button
              type="button"
              :disabled="isSubmitting"
              class="btn-primary text-sm"
              @click="confirm"
            >
              Подтвердить перенос
            </button>
            <button type="button" class="rounded-md border border-slate-300 px-4 py-2 text-sm dark:border-slate-700" @click="emit('close')">
              Отмена
            </button>
          </div>
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
