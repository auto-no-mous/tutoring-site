<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { createManualBooking, listTutorBookings, setBookingOutcome } from "@/api/bookings";
import { getMyStudentsHomeworkStatus } from "@/api/homework";
import BookingCard from "@/components/BookingCard.vue";
import BookingScheduleGroups from "@/components/BookingScheduleGroups.vue";
import RescheduleModal from "@/components/RescheduleModal.vue";
import { useToastStore } from "@/stores/toast";
import type { Booking } from "@/types/booking";
import { formatDateTimeWithMsk } from "@/utils/time";
import { groupByWeekAndDay } from "@/utils/scheduleGrouping";

const toast = useToastStore();

const bookings = ref<Booking[]>([]);
const homeworkStatusByStudent = ref<Record<string, string>>({});
const showForm = ref(false);
const studentId = ref("");
const date = ref("");
const time = ref("");
const durationMinutes = ref(60);
const meetingLink = ref("");
const notes = ref("");
const error = ref("");
const reschedulingBooking = ref<Booking | null>(null);

const OUTCOME_OPTIONS = [
  { value: "conducted", label: "Проведено успешно" },
  { value: "student_no_show", label: "Ученик не явился" },
  { value: "tutor_no_show", label: "Репетитор не явился" },
];

const STATUS_LABELS: Record<string, string> = {
  cancelled_by_student: "Отменено учеником",
  cancelled_by_tutor: "Отменено репетитором",
  rescheduled: "Перенесено",
};

function isOutcomeEditable(booking: Booking): boolean {
  return booking.status === "scheduled" && !!booking.student_id && new Date(booking.end_at) < new Date();
}

function pastStatusLabel(booking: Booking): string {
  return STATUS_LABELS[booking.status] ?? booking.status;
}

// The tutor cabinet always shows MSK regardless of the tutor's own location
// (project_description.md section 2.3), so "today"/week boundaries for grouping
// use MSK too, not the browser's local timezone.
const MSK = "Europe/Moscow";

const upcoming = computed(() =>
  bookings.value
    .filter((b) => b.status === "scheduled" && new Date(b.start_at) >= new Date())
    .sort((a, b) => a.start_at.localeCompare(b.start_at)),
);
const past = computed(() =>
  bookings.value
    .filter((b) => b.status !== "scheduled" || new Date(b.start_at) < new Date())
    .sort((a, b) => b.start_at.localeCompare(a.start_at))
    .slice(0, 20),
);

const weeks = computed(() => groupByWeekAndDay(upcoming.value, (b) => b.start_at, MSK));

function homeworkStatusFor(booking: Booking): "none" | "pending" | "done" {
  if (!booking.student_id) return "none";
  return (homeworkStatusByStudent.value[booking.student_id] as "pending" | "done" | undefined) ?? "none";
}

async function load(): Promise<void> {
  [bookings.value, homeworkStatusByStudent.value] = await Promise.all([
    listTutorBookings(),
    getMyStudentsHomeworkStatus(),
  ]);
}

async function createBlock(): Promise<void> {
  error.value = "";
  try {
    const start = new Date(`${date.value}T${time.value}:00`);
    const end = new Date(start.getTime() + durationMinutes.value * 60000);
    await createManualBooking({
      student_id: studentId.value || null,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      meeting_link: meetingLink.value || null,
      notes: notes.value || null,
    });
    showForm.value = false;
    studentId.value = "";
    notes.value = "";
    meetingLink.value = "";
    await load();
  } catch {
    error.value = "Не удалось создать запись — время может пересекаться с существующей.";
  }
}

function openReschedule(booking: Booking): void {
  reschedulingBooking.value = booking;
}

async function onRescheduled(): Promise<void> {
  reschedulingBooking.value = null;
  await load();
  toast.show("Занятие перенесено");
}

async function onOutcomeChange(booking: Booking, event: Event): Promise<void> {
  const outcome = (event.target as HTMLSelectElement).value;
  await setBookingOutcome(booking.id, outcome);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex max-w-2xl flex-col gap-6">
    <div>
      <button type="button" class="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700" @click="showForm = !showForm">
        {{ showForm ? "Отмена" : "+ Резерв / запись вручную" }}
      </button>
      <form v-if="showForm" class="mt-3 flex flex-wrap items-end gap-2 rounded-lg border border-slate-200 p-4 dark:border-slate-800" @submit.prevent="createBlock">
        <label class="flex flex-col gap-1 text-sm">
          ID ученика (необязательно)
          <input v-model="studentId" placeholder="оставьте пустым для личной блокировки" class="w-56 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Дата
          <input v-model="date" type="date" required class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Время
          <input v-model="time" type="time" required class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Длительность, мин
          <input v-model.number="durationMinutes" type="number" min="1" class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Ссылка на занятие
          <input v-model="meetingLink" class="w-48 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Заметка
          <input v-model="notes" class="w-48 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <button type="submit" class="rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white dark:bg-white dark:text-slate-900">Создать</button>
      </form>
      <p v-if="error" class="mt-2 text-sm text-red-600 dark:text-red-400">{{ error }}</p>
    </div>

    <section>
      <BookingScheduleGroups :weeks="weeks">
        <template #default="{ item: booking }">
          <BookingCard
            :booking="booking"
            role="tutor"
            :homework-status="homeworkStatusFor(booking)"
            @changed="load"
            @reschedule-requested="openReschedule"
          />
        </template>
      </BookingScheduleGroups>
    </section>

    <section>
      <h2 class="text-lg font-medium">История</h2>
      <div v-for="booking in past" :key="booking.id" class="mt-2 flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-500 dark:border-slate-800">
        <div>{{ formatDateTimeWithMsk(booking.start_at) }} · {{ booking.student_display_name ?? "—" }}</div>
        <select
          v-if="isOutcomeEditable(booking)"
          :value="booking.outcome ?? 'conducted'"
          class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-xs dark:border-slate-700"
          @change="onOutcomeChange(booking, $event)"
        >
          <option v-for="opt in OUTCOME_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <div v-else>{{ pastStatusLabel(booking) }}</div>
      </div>
    </section>

    <RescheduleModal
      v-if="reschedulingBooking"
      :booking="reschedulingBooking"
      @close="reschedulingBooking = null"
      @rescheduled="onRescheduled"
    />
  </div>
</template>
