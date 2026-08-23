<script setup lang="ts">
import { ArrowLeft, CircleCheck, Clock } from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import { createBooking } from "@/api/bookings";
import BookingCalendar from "@/components/BookingCalendar.vue";
import { getAvailableDates, getDaySlots } from "@/api/tutors";
import { useAuthStore } from "@/stores/auth";
import type { LessonType, Slot } from "@/types/tutor";
import { addDaysIso, formatDateTimeWithMsk, formatTime, todayIso } from "@/utils/time";

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

const STEPS = [
  { n: 1, label: "Занятие" },
  { n: 2, label: "Дата" },
  { n: 3, label: "Время" },
  { n: 4, label: "Подтверждение" },
] as const;

watch(() => props.tutorId, restart);
</script>

<template>
  <div class="surface-card p-5 sm:p-6">
    <h2 class="text-xl font-semibold">Записаться на занятие</h2>

    <!-- Полоса шагов: показывает, где ученик находится в записи. -->
    <ol v-if="!success" class="mt-4 flex items-center gap-2">
      <li v-for="s in STEPS" :key="s.n" class="flex flex-1 flex-col gap-1.5">
        <span
          class="h-1.5 rounded-full transition-colors duration-300"
          :class="step >= s.n ? 'bg-brand-500' : 'bg-slate-200 dark:bg-slate-800'"
        ></span>
        <span
          class="text-xs font-medium transition-colors duration-300"
          :class="step >= s.n ? 'text-brand-700 dark:text-brand-300' : 'text-slate-400'"
        >
          {{ s.label }}
        </span>
      </li>
    </ol>

    <div v-if="success" class="animate-pop-in mt-5 rounded-xl bg-brand-50 p-4 text-base text-brand-900 dark:bg-brand-900/40 dark:text-brand-100">
      <div class="flex items-center gap-2 text-lg font-semibold">
        <CircleCheck class="h-5 w-5" />
        Вы записаны на занятие!
      </div>
      <p class="mt-1">Подробности — в личном кабинете.</p>
      <button type="button" class="btn-outline mt-3 text-base" @click="restart">Записаться ещё раз</button>
    </div>

    <template v-else>
      <Transition name="step" mode="out-in">
        <!-- Step 1: lesson type -->
        <div v-if="step === 1" key="1" class="mt-5">
          <p v-if="individualTypes.length === 0" class="text-base text-slate-400">
            У репетитора пока нет индивидуальных типов занятий.
          </p>
          <div v-else class="flex flex-col gap-2.5">
            <button
              v-for="type in individualTypes"
              :key="type.id"
              type="button"
              class="group rounded-xl border border-slate-200 px-4 py-3 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-400 hover:bg-brand-50/60 hover:shadow-md dark:border-slate-700 dark:hover:border-brand-500 dark:hover:bg-brand-900/20"
              @click="pickType(type)"
            >
              <div class="text-base font-semibold">{{ type.name }}</div>
              <div class="flex items-center gap-1.5 text-base text-slate-500 dark:text-slate-400">
                <Clock class="h-4 w-4" />
                {{ type.duration_minutes }} мин ·
                <span class="font-medium text-brand-700 dark:text-brand-300">{{ type.price }} ₽</span>
              </div>
            </button>
          </div>
        </div>

        <!-- Step 2: date -->
        <div v-else-if="step === 2" key="2" class="mt-5">
          <button type="button" class="back-link" @click="step = 1"><ArrowLeft class="h-4 w-4" />Тип занятия</button>
          <p v-if="isLoading" class="mt-3 text-base text-slate-400">Загрузка дат…</p>
          <p v-else-if="availableDates.length === 0" class="mt-3 text-base text-slate-400">
            Нет свободных дат в ближайший месяц.
          </p>
          <BookingCalendar v-else class="mt-3" :available-dates="availableDates" @select="pickDate" />
        </div>

        <!-- Step 3: slot -->
        <div v-else-if="step === 3" key="3" class="mt-5">
          <button type="button" class="back-link" @click="step = 2"><ArrowLeft class="h-4 w-4" />Дата</button>
          <p v-if="isLoading" class="mt-3 text-base text-slate-400">Загрузка времени…</p>
          <div v-else class="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
            <button
              v-for="slot in slots"
              :key="slot.start_at"
              type="button"
              :disabled="!slot.available"
              class="rounded-lg border px-2 py-2 text-sm font-medium transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-30"
              :class="
                slot.available
                  ? 'border-slate-200 hover:-translate-y-0.5 hover:border-brand-400 hover:bg-brand-50 hover:shadow-sm dark:border-slate-700 dark:hover:border-brand-500 dark:hover:bg-brand-900/20'
                  : 'border-slate-200 dark:border-slate-800'
              "
              @click="pickSlot(slot)"
            >
              {{ formatTime(slot.start_at) }}
            </button>
          </div>
        </div>

        <!-- Step 4: confirm -->
        <div v-else-if="step === 4 && selectedSlot" key="4" class="mt-5 flex flex-col gap-4">
          <button type="button" class="back-link self-start" @click="step = 3"><ArrowLeft class="h-4 w-4" />Время</button>
          <dl class="flex flex-col gap-1 rounded-xl bg-slate-50 p-4 text-base dark:bg-slate-800/50">
            <div><dt class="inline font-semibold">Репетитор: </dt><dd class="inline">{{ tutorName }}</dd></div>
            <div>
              <dt class="inline font-semibold">Занятие: </dt>
              <dd class="inline">{{ selectedType?.name }} ({{ selectedType?.duration_minutes }} мин, {{ selectedType?.price }} ₽)</dd>
            </div>
            <div>
              <dt class="inline font-semibold">Время: </dt>
              <dd class="inline text-brand-700 dark:text-brand-300">{{ formatDateTimeWithMsk(selectedSlot.start_at) }}</dd>
            </div>
          </dl>
          <label class="flex items-center gap-2 text-base">
            <input v-model="repeatWeekly" type="checkbox" class="h-4 w-4 accent-brand-500" />
            Повторять каждую неделю
          </label>
          <p v-if="error" class="text-base text-red-600 dark:text-red-400">{{ error }}</p>
          <button v-if="auth.isAuthenticated" type="button" :disabled="isLoading" class="btn-primary self-start text-base" @click="confirm">
            Записаться
          </button>
          <RouterLink v-else to="/login" class="btn-primary self-start text-base">Войдите, чтобы записаться</RouterLink>
        </div>
      </Transition>
    </template>
  </div>
</template>
