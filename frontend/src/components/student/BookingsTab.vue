<script setup lang="ts">
import { CalendarDays, List } from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";

import { listMyBookings } from "@/api/bookings";
import { myOccurrences } from "@/api/groups";
import { listMyWhiteboards, type Whiteboard } from "@/api/whiteboards";
import BookingCard from "@/components/BookingCard.vue";
import BookingScheduleGroups from "@/components/BookingScheduleGroups.vue";
import GroupOccurrenceCard from "@/components/GroupOccurrenceCard.vue";
import RescheduleModal from "@/components/RescheduleModal.vue";
import ScheduleWeekGrid from "@/components/ScheduleWeekGrid.vue";
import ScheduleItemModal from "@/components/student/ScheduleItemModal.vue";
import { useToastStore } from "@/stores/toast";
import type { Booking } from "@/types/booking";
import type { StudentGroupOccurrence } from "@/types/group";
import { formatDateTimeWithMsk, formatTime, MSK_TIMEZONE } from "@/utils/time";
import { groupByWeekAndDay, groupIntoCalendarWeeks, isBeforeToday } from "@/utils/scheduleGrouping";

const toast = useToastStore();

const bookings = ref<Booking[]>([]);
const occurrences = ref<StudentGroupOccurrence[]>([]);
// Доски привязаны к паре с репетитором или к группе, поэтому грузятся один раз на
// вкладку, а карточки разбирают список сами.
const whiteboards = ref<Whiteboard[]>([]);
const reschedulingBooking = ref<Booking | null>(null);

// Дни группируются по московскому календарю, как и само время занятий (раздел 6):
// по местному календарю занятие в 23:00 МСК уехало бы под заголовок следующего дня.
const scheduleTimeZone = MSK_TIMEZONE;

// A flat, keyable union of individual bookings and group occurrences so both kinds
// can share one day/week-grouped schedule (see BookingScheduleGroups.vue, generic
// over any item with an id/start_at) - the "kind" tag picks which card to render.
type ScheduleItem = ({ kind: "booking" } & Booking) | ({ kind: "occurrence" } & StudentGroupOccurrence);

const upcoming = computed<ScheduleItem[]>(() => {
  const bookingItems: ScheduleItem[] = bookings.value
    .filter((b) => b.status === "scheduled" && !isBeforeToday(b.start_at, scheduleTimeZone))
    .map((b) => ({ kind: "booking", ...b }));
  const occurrenceItems: ScheduleItem[] = occurrences.value
    .filter((o) => o.status !== "cancelled" && !isBeforeToday(o.start_at, scheduleTimeZone))
    .map((o) => ({ kind: "occurrence", ...o }));
  return [...bookingItems, ...occurrenceItems].sort((a, b) => a.start_at.localeCompare(b.start_at));
});
const past = computed(() =>
  bookings.value
    .filter((b) => b.status !== "scheduled" || isBeforeToday(b.start_at, scheduleTimeZone))
    .sort((a, b) => b.start_at.localeCompare(a.start_at))
    .slice(0, 20),
);

const weeks = computed(() => groupByWeekAndDay(upcoming.value, (item) => item.start_at, scheduleTimeZone));

// --- Список карточек или недельная сетка -------------------------------------------

const LAYOUT_STORAGE_KEY = "student-bookings-layout";
// Выбор запоминается, как и у репетитора.
const scheduleLayout = ref<"list" | "week">(
  localStorage.getItem(LAYOUT_STORAGE_KEY) === "week" ? "week" : "list",
);
watch(scheduleLayout, (layout) => localStorage.setItem(LAYOUT_STORAGE_KEY, layout));

// В сетке - вся текущая неделя, включая прошедшие дни: это календарь.
const calendarWeeks = computed(() =>
  groupIntoCalendarWeeks<ScheduleItem>(
    [
      ...bookings.value.filter((b) => b.status === "scheduled").map((b) => ({ kind: "booking" as const, ...b })),
      ...occurrences.value.filter((o) => o.status !== "cancelled").map((o) => ({ kind: "occurrence" as const, ...o })),
    ],
    (item) => item.start_at,
    scheduleTimeZone,
  ),
);

// Храним id, а не объект: после действия список перезагружается, и окно показывает
// свежие данные, а пропавшее (отменённое) занятие закрывает окно само.
const openedId = ref<string | null>(null);
const openedItem = computed<ScheduleItem | null>(() => {
  const booking = bookings.value.find((b) => b.id === openedId.value && b.status === "scheduled");
  if (booking) return { kind: "booking", ...booking };
  const occurrence = occurrences.value.find((o) => o.id === openedId.value && o.status !== "cancelled");
  return occurrence ? { kind: "occurrence", ...occurrence } : null;
});

function requestRescheduleFromModal(booking: Booking): void {
  openedId.value = null;
  openReschedule(booking);
}

async function load(): Promise<void> {
  [bookings.value, occurrences.value, whiteboards.value] = await Promise.all([
    listMyBookings(),
    myOccurrences(),
    listMyWhiteboards(),
  ]);
}

// У ученика карточка индивидуального занятия отбирает доски по репетитору: доска
// общая для всей их пары, а не для конкретной записи.
function boardsForTutor(tutorId: string): Whiteboard[] {
  return whiteboards.value.filter((board) => board.tutor_id === tutorId && board.student_id);
}

function boardsForGroup(groupId: string): Whiteboard[] {
  return whiteboards.value.filter((board) => board.group_id === groupId);
}

function openReschedule(booking: Booking): void {
  reschedulingBooking.value = booking;
}

async function onRescheduled(): Promise<void> {
  reschedulingBooking.value = null;
  await load();
  toast.show("Занятие перенесено");
}

onMounted(load);
</script>

<template>
  <div class="flex flex-col gap-6" :class="scheduleLayout === 'list' ? 'max-w-2xl' : ''">
    <div
      class="inline-flex self-end rounded-md border border-slate-300 p-0.5 text-sm dark:border-slate-700"
      role="group"
      aria-label="Вид расписания"
    >
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded px-2.5 py-1"
        :class="scheduleLayout === 'list' ? 'bg-brand-500 text-white' : 'text-slate-500'"
        :aria-pressed="scheduleLayout === 'list'"
        @click="scheduleLayout = 'list'"
      >
        <List class="h-4 w-4" />Список
      </button>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded px-2.5 py-1"
        :class="scheduleLayout === 'week' ? 'bg-brand-500 text-white' : 'text-slate-500'"
        :aria-pressed="scheduleLayout === 'week'"
        @click="scheduleLayout = 'week'"
      >
        <CalendarDays class="h-4 w-4" />Неделя
      </button>
    </div>

    <section v-if="scheduleLayout === 'week'">
      <ScheduleWeekGrid :weeks="calendarWeeks">
        <template #item="{ item }">
          <button
            type="button"
            class="flex flex-col rounded-md px-1.5 py-1 text-left text-xs shadow-sm ring-1 transition-colors hover:ring-brand-400 dark:hover:ring-brand-600"
            :class="
              item.kind === 'occurrence'
                ? 'bg-sky-50 ring-sky-200 dark:bg-sky-950/40 dark:ring-sky-800'
                : 'bg-white ring-slate-200 dark:bg-slate-900 dark:ring-slate-700'
            "
            :data-group-occurrence="item.kind === 'occurrence' ? '' : undefined"
            @click="openedId = item.id"
          >
            <span class="font-semibold tabular-nums">{{ formatTime(item.start_at) }}</span>
            <template v-if="item.kind === 'occurrence'">
              <span class="leading-tight">Группа «{{ item.group_name }}»</span>
              <span class="text-slate-400">{{ item.tutor_display_name }}</span>
            </template>
            <template v-else>
              <span class="leading-tight">{{ item.tutor_display_name ?? "Занятие" }}</span>
              <span v-if="item.lesson_type_name" class="text-slate-400">{{ item.lesson_type_name }}</span>
            </template>
          </button>
        </template>
      </ScheduleWeekGrid>
    </section>

    <section v-else>
      <BookingScheduleGroups :weeks="weeks">
        <template #default="{ item }">
          <BookingCard
            v-if="item.kind === 'booking'"
            :booking="item"
            role="student"
            :whiteboards="boardsForTutor(item.tutor_id)"
            @changed="load"
            @reschedule-requested="openReschedule"
          />
          <GroupOccurrenceCard
            v-else
            :occurrence="item"
            :whiteboards="boardsForGroup(item.group_id)"
            @changed="load"
          />
        </template>
      </BookingScheduleGroups>
    </section>

    <section>
      <h2 class="text-lg font-medium">История</h2>
      <div v-for="booking in past" :key="booking.id" class="mt-2 flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-500 dark:border-slate-800">
        <div>{{ formatDateTimeWithMsk(booking.start_at) }}</div>
        <div>{{ booking.status }}</div>
      </div>
    </section>

    <ScheduleItemModal
      v-if="openedItem"
      :start-at="openedItem.start_at"
      :end-at="openedItem.end_at"
      :is-group="openedItem.kind === 'occurrence'"
      @close="openedId = null"
    >
      <BookingCard
        v-if="openedItem.kind === 'booking'"
        :booking="openedItem"
        role="student"
        :whiteboards="boardsForTutor(openedItem.tutor_id)"
        @changed="load"
        @reschedule-requested="requestRescheduleFromModal"
      />
      <GroupOccurrenceCard
        v-else
        :occurrence="openedItem"
        :whiteboards="boardsForGroup(openedItem.group_id)"
        @changed="load"
      />
    </ScheduleItemModal>

    <RescheduleModal
      v-if="reschedulingBooking"
      :booking="reschedulingBooking"
      @close="reschedulingBooking = null"
      @rescheduled="onRescheduled"
    />
  </div>
</template>
