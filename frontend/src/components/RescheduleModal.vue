<script setup lang="ts">
import { X } from "lucide-vue-next";
import { DialogClose, DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui";
import { ArrowLeft } from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import { getRescheduleDates, getRescheduleSlots, rescheduleBooking } from "@/api/bookings";
import { getMyLessonTypes } from "@/api/tutors";
import BookingCalendar from "@/components/BookingCalendar.vue";
import { useAuthStore } from "@/stores/auth";
import type { Booking } from "@/types/booking";
import type { LessonType, Slot } from "@/types/tutor";
import { addDaysIso, formatDateTimeWithMsk, formatTime, todayIso } from "@/utils/time";

const props = defineProps<{ booking: Booking }>();
const emit = defineEmits<{ close: []; rescheduled: [] }>();

const auth = useAuthStore();
// Репетитору правила переноса не писаны: ему доступны любой день (включая
// прошедшие) и любое время, даже занятое другим занятием - см. backend
// booking_service.reschedule_booking. Отсюда и другой вид окна.
const isTutor = computed(() => auth.user?.role === "tutor");

// Насколько далеко назад репетитор может листать даты. Ограничение эндпоинта -
// 60 дней на запрос, поэтому 30 назад и 30 вперёд это ровно потолок.
const PAST_DAYS = 30;
const FUTURE_DAYS = 30;

const lessonTypes = ref<LessonType[]>([]);
const lessonTypeId = ref<string | null>(props.booking.lesson_type_id);
const durationMinutes = ref<number>(
  Math.round(
    (new Date(props.booking.end_at).getTime() - new Date(props.booking.start_at).getTime()) / 60000,
  ),
);

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
    const from = isTutor.value ? addDaysIso(todayIso(), -PAST_DAYS) : todayIso();
    availableDates.value = await getRescheduleDates(
      props.booking.id,
      from,
      addDaysIso(todayIso(), FUTURE_DAYS),
    );
    if (isTutor.value && lessonTypes.value.length === 0) {
      lessonTypes.value = (await getMyLessonTypes()).filter((t) => t.format === "individual");
    }
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
    slots.value = await getRescheduleSlots(
      props.booking.id,
      date,
      isTutor.value ? durationMinutes.value : null,
    );
  } finally {
    isLoading.value = false;
  }
}

function pickSlot(slot: Slot): void {
  if (!slot.available) return;
  selectedSlot.value = slot;
  step.value = 3;
}

// Смена типа подставляет его длительность, но не запирает её: поле минут остаётся
// доступным для разового отклонения.
function onLessonTypeChange(id: string): void {
  lessonTypeId.value = id;
  const chosen = lessonTypes.value.find((t) => t.id === id);
  if (chosen) durationMinutes.value = chosen.duration_minutes;
}

async function confirm(): Promise<void> {
  if (!selectedSlot.value) return;
  isSubmitting.value = true;
  error.value = null;
  try {
    await rescheduleBooking(
      props.booking.id,
      selectedSlot.value.start_at,
      isTutor.value ? { lessonTypeId: lessonTypeId.value, durationMinutes: durationMinutes.value } : {},
    );
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
          <BookingCalendar v-else :available-dates="availableDates" :allow-past="isTutor" @select="pickDate" />
        </div>

        <!-- Step 2: slot -->
        <div v-else-if="step === 2" class="mt-4">
          <button type="button" class="back-link mb-3" @click="step = 1"><ArrowLeft class="h-4 w-4" />Дата</button>
          <p v-if="isLoading" class="text-sm text-slate-400">Загрузка времени…</p>
          <template v-else>
            <p v-if="isTutor" class="mb-2 text-xs text-slate-500">
              Показаны все отрезки дня. Красным отмечено время, уже занятое другим занятием, —
              выбрать его можно, занятия просто наложатся.
            </p>
            <div class="grid max-h-72 grid-cols-3 gap-2 overflow-y-auto sm:grid-cols-4">
              <button
                v-for="slot in slots"
                :key="slot.start_at"
                type="button"
                :disabled="!slot.available"
                :title="slot.busy ? 'Время занято другим занятием — перенос всё равно возможен' : undefined"
                class="rounded-lg border px-2 py-2 text-sm font-medium transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-30"
                :class="
                  slot.busy
                    ? 'border-red-300 bg-red-50 text-red-700 hover:-translate-y-0.5 hover:border-red-400 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300'
                    : slot.available
                      ? 'border-slate-200 hover:-translate-y-0.5 hover:border-brand-400 hover:bg-brand-50 dark:border-slate-700 dark:hover:border-brand-500 dark:hover:bg-brand-900/20'
                      : 'border-slate-200 dark:border-slate-800'
                "
                @click="pickSlot(slot)"
              >
                {{ formatTime(slot.start_at) }}
              </button>
            </div>
          </template>
        </div>

        <!-- Step 3: confirm -->
        <div v-else-if="step === 3 && selectedSlot" class="mt-4 flex flex-col gap-3">
          <button type="button" class="back-link" @click="step = 2"><ArrowLeft class="h-4 w-4" />Время</button>
          <p class="text-sm">
            Новое время: <span class="font-medium">{{ formatDateTimeWithMsk(selectedSlot.start_at) }}</span>
          </p>
          <template v-if="isTutor">
            <label class="flex flex-col gap-1 text-sm">
              Тип занятия
              <select
                :value="lessonTypeId ?? ''"
                class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
                @change="onLessonTypeChange(($event.target as HTMLSelectElement).value)"
              >
                <option v-for="type in lessonTypes" :key="type.id" :value="type.id">
                  {{ type.name }} ({{ type.duration_minutes }} мин, {{ type.price }} ₽)
                </option>
              </select>
            </label>
            <label class="flex flex-col gap-1 text-sm">
              Длительность, мин
              <input
                v-model.number="durationMinutes"
                type="number"
                min="1"
                max="480"
                class="w-28 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
              />
              <span class="text-xs text-slate-500">
                Подставляется из типа занятия, но её можно изменить для этого занятия.
              </span>
            </label>
          </template>
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
