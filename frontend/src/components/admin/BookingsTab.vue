<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { deleteBooking, listBookings, listTutors } from "@/api/admin";
import AdminRescheduleModal from "@/components/admin/AdminRescheduleModal.vue";
import type { Booking } from "@/types/booking";
import type { TutorProfile } from "@/types/tutor";
import { formatDateTimeWithMsk } from "@/utils/time";

const PAGE_SIZE = 20;

const bookings = ref<Booking[]>([]);
const total = ref(0);
const page = ref(1);
const tutors = ref<TutorProfile[]>([]);
const isLoading = ref(true);
const reschedulingBooking = ref<Booking | null>(null);

const tutorFilter = ref("");
const subjectFilter = ref("");
const directionFilter = ref("");
const gradeFilter = ref<number | null>(null);
const rangePreset = ref<"all" | "today" | "tomorrow" | "this_week" | "next_week" | "next_30_days">("all");

const statusLabels: Record<string, string> = {
  scheduled: "запланировано",
  cancelled_by_student: "отменено учеником",
  cancelled_by_tutor: "отменено репетитором",
  rescheduled: "перенесено",
  completed: "проведено",
};

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)));

const subjectOptions = computed(() => {
  const map = new Map<string, string>();
  for (const t of tutors.value) {
    for (const s of t.subjects ?? []) map.set(s.subject_id, s.subject_name);
  }
  return [...map.entries()].map(([id, name]) => ({ id, name }));
});

const directionOptions = computed(() => {
  if (!subjectFilter.value) return [];
  const map = new Map<string, string>();
  for (const t of tutors.value) {
    const subject = (t.subjects ?? []).find((s) => s.subject_id === subjectFilter.value);
    for (const d of subject?.directions ?? []) map.set(d.id, d.name);
  }
  return [...map.entries()].map(([id, name]) => ({ id, name }));
});

watch(subjectFilter, () => {
  directionFilter.value = "";
});

function rangeBounds(preset: typeof rangePreset.value): { from: Date; to: Date } | null {
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const addDays = (d: Date, days: number) => {
    const copy = new Date(d);
    copy.setDate(copy.getDate() + days);
    return copy;
  };
  const mondayOf = (d: Date) => {
    const dow = d.getDay(); // 0=Sunday..6=Saturday
    return addDays(d, dow === 0 ? -6 : 1 - dow);
  };
  const today = startOfDay(new Date());
  switch (preset) {
    case "today":
      return { from: today, to: addDays(today, 1) };
    case "tomorrow":
      return { from: addDays(today, 1), to: addDays(today, 2) };
    case "this_week": {
      const monday = mondayOf(today);
      return { from: monday, to: addDays(monday, 7) };
    }
    case "next_week": {
      const nextMonday = addDays(mondayOf(today), 7);
      return { from: nextMonday, to: addDays(nextMonday, 7) };
    }
    case "next_30_days":
      return { from: new Date(), to: addDays(new Date(), 30) };
    default:
      return null;
  }
}

async function load(targetPage = 1): Promise<void> {
  isLoading.value = true;
  try {
    const bounds = rangeBounds(rangePreset.value);
    const result = await listBookings({
      tutor_id: tutorFilter.value || undefined,
      subject_id: subjectFilter.value || undefined,
      direction_id: directionFilter.value || undefined,
      grade: gradeFilter.value ?? undefined,
      date_from: bounds?.from.toISOString(),
      date_to: bounds?.to.toISOString(),
      page: targetPage,
      page_size: PAGE_SIZE,
    });
    bookings.value = result.items;
    total.value = result.total;
    page.value = result.page;
  } finally {
    isLoading.value = false;
  }
}

function goToPage(target: number): void {
  if (target < 1 || target > totalPages.value || target === page.value) return;
  load(target);
}

async function remove(booking: Booking): Promise<void> {
  if (!window.confirm("Удалить запись безвозвратно?")) return;
  await deleteBooking(booking.id);
  await load(page.value);
}

function openReschedule(booking: Booking): void {
  reschedulingBooking.value = booking;
}

async function onRescheduled(): Promise<void> {
  reschedulingBooking.value = null;
  await load(page.value);
}

watch([tutorFilter, subjectFilter, directionFilter, gradeFilter, rangePreset], () => load(1));

onMounted(async () => {
  tutors.value = await listTutors();
  await load();
});
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex flex-wrap items-end gap-2 rounded-md border border-slate-200 p-3 dark:border-slate-800">
      <label class="flex flex-col gap-1 text-xs">
        Период
        <select v-model="rangePreset" class="w-40 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700">
          <option value="all">Все</option>
          <option value="today">Сегодня</option>
          <option value="tomorrow">Завтра</option>
          <option value="this_week">Эта неделя</option>
          <option value="next_week">Следующая неделя</option>
          <option value="next_30_days">Ближайшие 30 дней</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-xs">
        Репетитор
        <select v-model="tutorFilter" class="w-48 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700">
          <option value="">Все</option>
          <option v-for="t in tutors" :key="t.id" :value="t.id">{{ t.display_name }}</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-xs">
        Предмет
        <select v-model="subjectFilter" class="w-48 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700">
          <option value="">Все</option>
          <option v-for="s in subjectOptions" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-xs">
        Направление
        <select
          v-model="directionFilter"
          :disabled="!subjectFilter"
          class="w-48 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm disabled:opacity-50 dark:border-slate-700"
        >
          <option value="">Все</option>
          <option v-for="d in directionOptions" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-xs">
        Класс
        <select v-model.number="gradeFilter" class="w-32 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700">
          <option :value="null">Все</option>
          <option v-for="n in 11" :key="n" :value="n">{{ n }}-й</option>
        </select>
      </label>
    </div>

    <p v-if="isLoading" class="text-sm text-slate-400">Загрузка…</p>
    <p v-else-if="bookings.length === 0" class="text-sm text-slate-400">Занятий по заданным фильтрам не найдено.</p>
    <div class="flex flex-col gap-2">
      <div v-for="booking in bookings" :key="booking.id" class="rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
        <div class="flex items-center justify-between">
          <div>
            <div class="font-medium">{{ formatDateTimeWithMsk(booking.start_at) }}</div>
            <div class="text-slate-500">
              {{ booking.tutor_display_name ?? "—" }} ·
              {{ booking.student_display_name ?? (booking.is_manual_block ? "Личная блокировка" : "—") }}
              · {{ statusLabels[booking.status] ?? booking.status }}
            </div>
          </div>
          <div class="flex shrink-0 gap-2">
            <button
              v-if="booking.status === 'scheduled'"
              type="button"
              class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700"
              @click="openReschedule(booking)"
            >
              Перенести
            </button>
            <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="remove(booking)">
              Удалить
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!isLoading && totalPages > 1" class="flex items-center justify-center gap-2">
      <button
        type="button"
        class="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-slate-700"
        :disabled="page <= 1"
        @click="goToPage(page - 1)"
      >
        ← Назад
      </button>
      <span class="text-sm text-slate-500">Страница {{ page }} из {{ totalPages }} ({{ total }} занятий)</span>
      <button
        type="button"
        class="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-slate-700"
        :disabled="page >= totalPages"
        @click="goToPage(page + 1)"
      >
        Вперёд →
      </button>
    </div>

    <AdminRescheduleModal v-if="reschedulingBooking" :booking="reschedulingBooking" @close="reschedulingBooking = null" @rescheduled="onRescheduled" />
  </div>
</template>
