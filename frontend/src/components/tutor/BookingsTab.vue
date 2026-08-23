<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { createManualBooking, listTutorBookings, setBookingOutcome } from "@/api/bookings";
import { createOccurrence, listMyGroups } from "@/api/groups";
import { getMyStudentsHomeworkStatus } from "@/api/homework";
import { getManualBookingDates, getManualBookingSlots, getMyLessonTypes, getMyStudents } from "@/api/tutors";
import BookingCard from "@/components/BookingCard.vue";
import BookingScheduleGroups from "@/components/BookingScheduleGroups.vue";
import RescheduleModal from "@/components/RescheduleModal.vue";
import { useToastStore } from "@/stores/toast";
import type { Booking } from "@/types/booking";
import type { Group } from "@/types/group";
import type { LessonType, Slot, TutorStudent } from "@/types/tutor";
import { addDaysIso, formatDate, formatDateTimeWithMsk, formatMskTime, formatTime, mskDateTimeToUtcIso, todayIso } from "@/utils/time";
import { groupByWeekAndDay } from "@/utils/scheduleGrouping";

const toast = useToastStore();

const bookings = ref<Booking[]>([]);
const homeworkStatusByStudent = ref<Record<string, string>>({});
const showForm = ref(false);
const error = ref("");
const reschedulingBooking = ref<Booking | null>(null);

// --- Student/group picker --------------------------------------------------------

const students = ref<TutorStudent[]>([]);
const groups = ref<Group[]>([]);
const lessonTypes = ref<LessonType[]>([]);
const visibleCount = ref(20);
const selectedKey = ref(""); // "" = <Пусто> (personal time block)

interface PickerEntry {
  key: string;
  label: string;
  recencyMs: number;
  kind: "student" | "group";
  id: string;
}

function studentLabel(student: TutorStudent): string {
  const name = `${student.last_name} ${student.first_name}`.trim();
  return student.grade ? `${name}, ${student.grade}-й класс` : name;
}

// Sorted most-recently-worked-with first: students by their last lesson, groups by
// when they were created (groups have no "last session" concept exposed yet).
const pickerEntries = computed<PickerEntry[]>(() => {
  const studentEntries: PickerEntry[] = students.value.map((s) => ({
    key: `student:${s.id}`,
    label: studentLabel(s),
    recencyMs: s.last_lesson_at ? new Date(s.last_lesson_at).getTime() : 0,
    kind: "student",
    id: s.id,
  }));
  const groupEntries: PickerEntry[] = groups.value.map((g) => ({
    key: `group:${g.id}`,
    label: `Группа ${g.name}`,
    recencyMs: new Date(g.created_at).getTime(),
    kind: "group",
    id: g.id,
  }));
  return [...studentEntries, ...groupEntries].sort((a, b) => b.recencyMs - a.recencyMs);
});

const visibleEntries = computed(() => pickerEntries.value.slice(0, visibleCount.value));
const hasMoreEntries = computed(() => visibleCount.value < pickerEntries.value.length);
const selectedEntry = computed(() => pickerEntries.value.find((e) => e.key === selectedKey.value) ?? null);
const isGroupSelected = computed(() => selectedEntry.value?.kind === "group");

function loadMoreEntries(): void {
  visibleCount.value += 20;
}

// --- Duration ----------------------------------------------------------------------

const CUSTOM_DURATION = "custom";
const durationSelection = ref<string>(CUSTOM_DURATION);
const customDurationMinutes = ref(60);

const standardDurations = computed(() => {
  const set = new Set(lessonTypes.value.map((t) => t.duration_minutes));
  return Array.from(set).sort((a, b) => a - b);
});

const effectiveDuration = computed(() =>
  durationSelection.value === CUSTOM_DURATION ? customDurationMinutes.value : Number(durationSelection.value),
);

// Picking a group pre-fills its own lesson type's duration - still overridable, just a
// sensible default instead of forcing the tutor to look it up.
watch(selectedEntry, (entry) => {
  if (entry?.kind !== "group") return;
  const group = groups.value.find((g) => g.id === entry.id);
  const lessonType = group ? lessonTypes.value.find((t) => t.id === group.lesson_type_id) : undefined;
  if (!lessonType) return;
  if (standardDurations.value.includes(lessonType.duration_minutes)) {
    durationSelection.value = String(lessonType.duration_minutes);
  } else {
    durationSelection.value = CUSTOM_DURATION;
    customDurationMinutes.value = lessonType.duration_minutes;
  }
});

// --- Date / time picker --------------------------------------------------------------

const date = ref("");
const manualDate = ref("");
const manualTime = ref("");
const selectedStartAtIso = ref<string | null>(null);
const showDatePanel = ref(false);
const showTimePanel = ref(false);
const availableDates = ref<string[]>([]);
const availableSlots = ref<Slot[]>([]);
const isDatesLoading = ref(false);
const isSlotsLoading = ref(false);

// Changing duration invalidates whatever date/time was picked, since availability
// depends on it - simplest to just make the tutor re-pick rather than silently reuse a
// slot that might no longer fit.
watch(effectiveDuration, () => {
  date.value = "";
  selectedStartAtIso.value = null;
  showDatePanel.value = false;
  showTimePanel.value = false;
});

async function toggleDatePanel(): Promise<void> {
  showTimePanel.value = false;
  showDatePanel.value = !showDatePanel.value;
  if (!showDatePanel.value) return;
  isDatesLoading.value = true;
  try {
    availableDates.value = await getManualBookingDates(effectiveDuration.value, todayIso(), addDaysIso(todayIso(), 30));
  } finally {
    isDatesLoading.value = false;
  }
}

function pickAvailableDate(pickedDate: string): void {
  date.value = pickedDate;
  selectedStartAtIso.value = null;
  showDatePanel.value = false;
}

function useManualDate(): void {
  if (!manualDate.value) return;
  date.value = manualDate.value;
  selectedStartAtIso.value = null;
  showDatePanel.value = false;
}

async function toggleTimePanel(): Promise<void> {
  if (!date.value) return;
  showDatePanel.value = false;
  showTimePanel.value = !showTimePanel.value;
  if (!showTimePanel.value) return;
  isSlotsLoading.value = true;
  try {
    availableSlots.value = await getManualBookingSlots(effectiveDuration.value, date.value);
  } finally {
    isSlotsLoading.value = false;
  }
}

function pickAvailableSlot(slot: Slot): void {
  if (!slot.available) return;
  selectedStartAtIso.value = slot.start_at;
  showTimePanel.value = false;
}

function useManualTime(): void {
  if (!date.value || !manualTime.value) return;
  selectedStartAtIso.value = mskDateTimeToUtcIso(date.value, manualTime.value);
  showTimePanel.value = false;
}

// --- Booking cards / history ---------------------------------------------------------

const meetingLink = ref("");
const notes = ref("");

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

// The ДЗ badge reflects one aggregate status per student, not per lesson - showing it
// on every upcoming card for a student with a recurring series was misleading (looked
// like each lesson had its own homework). Show it only on that student's earliest
// upcoming card; once that lesson passes without being marked done, it naturally
// drops out of `upcoming` and the badge reappears on the next one instead.
const firstUpcomingBookingIdByStudent = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {};
  for (const booking of upcoming.value) {
    if (booking.student_id && !(booking.student_id in map)) {
      map[booking.student_id] = booking.id;
    }
  }
  return map;
});

function homeworkStatusFor(booking: Booking): "none" | "pending" | "done" {
  if (!booking.student_id) return "none";
  if (firstUpcomingBookingIdByStudent.value[booking.student_id] !== booking.id) return "none";
  return (homeworkStatusByStudent.value[booking.student_id] as "pending" | "done" | undefined) ?? "none";
}

async function load(): Promise<void> {
  const [bookingsData, homeworkStatusData, studentsData, groupsData, lessonTypesData] = await Promise.all([
    listTutorBookings(),
    getMyStudentsHomeworkStatus(),
    getMyStudents(),
    listMyGroups(),
    getMyLessonTypes(),
  ]);
  bookings.value = bookingsData;
  homeworkStatusByStudent.value = homeworkStatusData;
  students.value = studentsData;
  groups.value = groupsData;
  lessonTypes.value = lessonTypesData;
  if (standardDurations.value.length > 0) {
    durationSelection.value = String(standardDurations.value[0]);
  }
}

function resetForm(): void {
  selectedKey.value = "";
  visibleCount.value = 20;
  date.value = "";
  manualDate.value = "";
  manualTime.value = "";
  selectedStartAtIso.value = null;
  showDatePanel.value = false;
  showTimePanel.value = false;
  meetingLink.value = "";
  notes.value = "";
  durationSelection.value = standardDurations.value.length > 0 ? String(standardDurations.value[0]) : CUSTOM_DURATION;
}

async function createBlock(): Promise<void> {
  error.value = "";
  if (!selectedStartAtIso.value) {
    error.value = "Укажите дату и время";
    return;
  }
  const start = new Date(selectedStartAtIso.value);
  const end = new Date(start.getTime() + effectiveDuration.value * 60000);
  try {
    if (selectedEntry.value?.kind === "group") {
      await createOccurrence(selectedEntry.value.id, start.toISOString(), end.toISOString());
    } else {
      await createManualBooking({
        student_id: selectedEntry.value?.kind === "student" ? selectedEntry.value.id : null,
        start_at: start.toISOString(),
        end_at: end.toISOString(),
        meeting_link: meetingLink.value || null,
        notes: notes.value || null,
      });
    }
    resetForm();
    showForm.value = false;
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
      <form v-if="showForm" class="mt-3 flex flex-col gap-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800" @submit.prevent="createBlock">
        <div class="flex flex-wrap items-end gap-2">
          <label class="flex flex-col gap-1 text-sm">
            Ученик / группа
            <select v-model="selectedKey" class="w-64 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700">
              <option value="">&lt;Пусто&gt; (для блока времени)</option>
              <option v-for="entry in visibleEntries" :key="entry.key" :value="entry.key">{{ entry.label }}</option>
            </select>
            <button
              v-if="hasMoreEntries"
              type="button"
              class="self-start text-xs text-slate-500 underline"
              @click="loadMoreEntries"
            >
              Показать ещё 20
            </button>
          </label>

          <label class="flex flex-col gap-1 text-sm">
            Длительность
            <div class="flex gap-2">
              <select v-model="durationSelection" class="w-40 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700">
                <option v-for="d in standardDurations" :key="d" :value="String(d)">{{ d }} мин</option>
                <option :value="CUSTOM_DURATION">Другое (вручную)</option>
              </select>
              <input
                v-if="durationSelection === CUSTOM_DURATION"
                v-model.number="customDurationMinutes"
                type="number"
                min="1"
                class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
              />
            </div>
          </label>
        </div>

        <div class="flex flex-wrap items-start gap-2">
          <div class="flex flex-col gap-1 text-sm">
            Дата
            <button
              type="button"
              class="w-48 rounded-md border border-slate-300 px-2 py-1.5 text-left dark:border-slate-700"
              @click="toggleDatePanel"
            >
              {{ date ? formatDate(date + "T00:00:00Z") : "Выбрать дату…" }}
            </button>
            <div v-if="showDatePanel" class="w-72 rounded-md border border-slate-200 p-3 dark:border-slate-800">
              <p v-if="isDatesLoading" class="text-xs text-slate-400">Загрузка дат…</p>
              <p v-else-if="availableDates.length === 0" class="text-xs text-slate-400">Нет свободных дат в ближайший месяц.</p>
              <div v-else class="flex max-h-48 flex-wrap gap-1.5 overflow-y-auto">
                <button
                  v-for="d in availableDates"
                  :key="d"
                  type="button"
                  class="rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-brand-400 dark:border-slate-700"
                  @click="pickAvailableDate(d)"
                >
                  {{ formatDate(d + "T00:00:00Z") }}
                </button>
              </div>
              <div class="mt-3 flex items-end gap-2 border-t border-slate-200 pt-3 dark:border-slate-800">
                <label class="flex flex-col gap-1 text-xs">
                  Другая дата
                  <input v-model="manualDate" type="date" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
                </label>
                <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="useManualDate">
                  Выбрать
                </button>
              </div>
            </div>
          </div>

          <div class="flex flex-col gap-1 text-sm">
            Время
            <button
              type="button"
              class="w-48 rounded-md border border-slate-300 px-2 py-1.5 text-left disabled:opacity-40 dark:border-slate-700"
              :disabled="!date"
              @click="toggleTimePanel"
            >
              {{ selectedStartAtIso ? `${formatMskTime(selectedStartAtIso)} (МСК)` : "Выбрать время…" }}
            </button>
            <div v-if="showTimePanel" class="w-72 rounded-md border border-slate-200 p-3 dark:border-slate-800">
              <p v-if="isSlotsLoading" class="text-xs text-slate-400">Загрузка времени…</p>
              <div v-else class="grid max-h-48 grid-cols-3 gap-1.5 overflow-y-auto">
                <button
                  v-for="slot in availableSlots"
                  :key="slot.start_at"
                  type="button"
                  :disabled="!slot.available"
                  class="rounded-md border px-2 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-30"
                  :class="
                    slot.available
                      ? 'border-slate-300 hover:border-brand-400 dark:border-slate-700'
                      : 'border-slate-200 dark:border-slate-800'
                  "
                  @click="pickAvailableSlot(slot)"
                >
                  {{ formatTime(slot.start_at) }}
                </button>
              </div>
              <div class="mt-3 flex items-end gap-2 border-t border-slate-200 pt-3 dark:border-slate-800">
                <label class="flex flex-col gap-1 text-xs">
                  Другое время (МСК)
                  <input v-model="manualTime" type="time" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
                </label>
                <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="useManualTime">
                  Выбрать
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!isGroupSelected" class="flex flex-wrap items-end gap-2">
          <label class="flex flex-col gap-1 text-sm">
            Ссылка на занятие
            <input v-model="meetingLink" class="w-48 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
          </label>
          <label class="flex flex-col gap-1 text-sm">
            Заметка
            <input v-model="notes" class="w-48 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
          </label>
        </div>

        <button type="submit" class="self-start rounded-md bg-brand-500 px-3 py-1.5 text-sm text-white">
          Создать
        </button>
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
