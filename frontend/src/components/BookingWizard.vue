<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { createBooking } from "@/api/bookings";
import { getAvailableDates, getDaySlots } from "@/api/tutors";
import { useAuthStore } from "@/stores/auth";
import type { LessonType, Slot } from "@/types/tutor";
import { addDaysIso, formatDate, formatDateTimeWithMsk, formatTime, todayIso } from "@/utils/time";

const props = defineProps<{
  tutorId: string;
  tutorName: string;
  lessonTypes: LessonType[];
}>();

const auth = useAuthStore();

const step = ref<1 | 2 | 3 | 4>(1);
const selectedType = ref<LessonType | null>(null);
const availableDates = ref<string[]>([]);
const selectedDate = ref<string | null>(null);
const slots = ref<Slot[]>([]);
const selectedSlot = ref<Slot | null>(null);
const repeatWeekly = ref(false);
const isLoading = ref(false);
const error = ref<string | null>(null);
const success = ref(false);

const individualTypes = computed(() => props.lessonTypes.filter((t) => t.format === "individual" && t.is_active));

async function pickType(type: LessonType): Promise<void> {
  selectedType.value = type;
  step.value = 2;
  isLoading.value = true;
  error.value = null;
  try {
    availableDates.value = await getAvailableDates(props.tutorId, type.id, todayIso(), addDaysIso(todayIso(), 30));
  } finally {
    isLoading.value = false;
  }
}

async function pickDate(date: string): Promise<void> {
  selectedDate.value = date;
  step.value = 3;
  isLoading.value = true;
  error.value = null;
  try {
    slots.value = await getDaySlots(props.tutorId, selectedType.value!.id, date);
  } finally {
    isLoading.value = false;
  }
}

function pickSlot(slot: Slot): void {
  if (!slot.available) return;
  selectedSlot.value = slot;
  step.value = 4;
}

async function confirm(): Promise<void> {
  if (!auth.isAuthenticated) return;
  isLoading.value = true;
  error.value = null;
  try {
    await createBooking({
      tutor_id: props.tutorId,
      lesson_type_id: selectedType.value!.id,
      start_at: selectedSlot.value!.start_at,
      repeat_weekly: repeatWeekly.value,
    });
    success.value = true;
  } catch {
    error.value = "Не удалось записаться. Возможно, время уже занято — попробуйте выбрать другое.";
  } finally {
    isLoading.value = false;
  }
}

function restart(): void {
  step.value = 1;
  selectedType.value = null;
  selectedDate.value = null;
  selectedSlot.value = null;
  repeatWeekly.value = false;
  success.value = false;
  error.value = null;
}

watch(() => props.tutorId, restart);
</script>

<template>
  <div class="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
    <h2 class="text-lg font-medium">Записаться на занятие</h2>

    <div v-if="success" class="mt-4 text-sm text-green-600 dark:text-green-400">
      Вы записаны на занятие! Подробности — в личном кабинете.
      <button type="button" class="mt-2 block underline" @click="restart">Записаться ещё раз</button>
    </div>

    <template v-else>
      <!-- Step 1: lesson type -->
      <div v-if="step === 1" class="mt-4">
        <p v-if="individualTypes.length === 0" class="text-sm text-slate-400">
          У репетитора пока нет индивидуальных типов занятий.
        </p>
        <div v-else class="flex flex-col gap-2">
          <button
            v-for="type in individualTypes"
            :key="type.id"
            type="button"
            class="rounded-md border border-slate-300 px-3 py-2 text-left text-sm hover:border-slate-500 dark:border-slate-700"
            @click="pickType(type)"
          >
            <div class="font-medium">{{ type.name }}</div>
            <div class="text-slate-500">{{ type.duration_minutes }} мин · {{ type.price }} ₽</div>
          </button>
        </div>
      </div>

      <!-- Step 2: date -->
      <div v-else-if="step === 2" class="mt-4">
        <button type="button" class="mb-3 text-sm text-slate-500 underline" @click="step = 1">← Тип занятия</button>
        <p v-if="isLoading" class="text-sm text-slate-400">Загрузка дат…</p>
        <p v-else-if="availableDates.length === 0" class="text-sm text-slate-400">
          Нет свободных дат в ближайший месяц.
        </p>
        <div v-else class="flex flex-wrap gap-2">
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

      <!-- Step 3: slot -->
      <div v-else-if="step === 3" class="mt-4">
        <button type="button" class="mb-3 text-sm text-slate-500 underline" @click="step = 2">← Дата</button>
        <p v-if="isLoading" class="text-sm text-slate-400">Загрузка времени…</p>
        <div v-else class="grid grid-cols-3 gap-2 sm:grid-cols-4">
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

      <!-- Step 4: confirm -->
      <div v-else-if="step === 4 && selectedSlot" class="mt-4 flex flex-col gap-3">
        <button type="button" class="text-sm text-slate-500 underline" @click="step = 3">← Время</button>
        <dl class="text-sm">
          <div><dt class="inline font-medium">Репетитор: </dt><dd class="inline">{{ tutorName }}</dd></div>
          <div>
            <dt class="inline font-medium">Занятие: </dt>
            <dd class="inline">{{ selectedType?.name }} ({{ selectedType?.duration_minutes }} мин, {{ selectedType?.price }} ₽)</dd>
          </div>
          <div><dt class="inline font-medium">Время: </dt><dd class="inline">{{ formatDateTimeWithMsk(selectedSlot.start_at) }}</dd></div>
        </dl>
        <label class="flex items-center gap-2 text-sm">
          <input v-model="repeatWeekly" type="checkbox" />
          Повторять каждую неделю
        </label>
        <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
        <button
          v-if="auth.isAuthenticated"
          type="button"
          :disabled="isLoading"
          class="rounded-md bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"
          @click="confirm"
        >
          Записаться
        </button>
        <RouterLink v-else to="/login" class="rounded-md bg-slate-900 px-4 py-2 text-center text-sm text-white dark:bg-white dark:text-slate-900">
          Войдите, чтобы записаться
        </RouterLink>
      </div>
    </template>
  </div>
</template>
