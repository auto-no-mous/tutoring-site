<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { listMyBookings } from "@/api/bookings";
import { myOccurrences } from "@/api/groups";
import BookingCard from "@/components/BookingCard.vue";
import BookingScheduleGroups from "@/components/BookingScheduleGroups.vue";
import GroupOccurrenceCard from "@/components/GroupOccurrenceCard.vue";
import RescheduleModal from "@/components/RescheduleModal.vue";
import { useToastStore } from "@/stores/toast";
import type { Booking } from "@/types/booking";
import type { StudentGroupOccurrence } from "@/types/group";
import { formatDateTimeWithMsk } from "@/utils/time";
import { groupByWeekAndDay, isBeforeToday } from "@/utils/scheduleGrouping";

const toast = useToastStore();

const bookings = ref<Booking[]>([]);
const occurrences = ref<StudentGroupOccurrence[]>([]);
const reschedulingBooking = ref<Booking | null>(null);

const localTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

// A flat, keyable union of individual bookings and group occurrences so both kinds
// can share one day/week-grouped schedule (see BookingScheduleGroups.vue, generic
// over any item with an id/start_at) - the "kind" tag picks which card to render.
type ScheduleItem = ({ kind: "booking" } & Booking) | ({ kind: "occurrence" } & StudentGroupOccurrence);

const upcoming = computed<ScheduleItem[]>(() => {
  const bookingItems: ScheduleItem[] = bookings.value
    .filter((b) => b.status === "scheduled" && !isBeforeToday(b.start_at, localTimeZone))
    .map((b) => ({ kind: "booking", ...b }));
  const occurrenceItems: ScheduleItem[] = occurrences.value
    .filter((o) => o.status !== "cancelled" && !isBeforeToday(o.start_at, localTimeZone))
    .map((o) => ({ kind: "occurrence", ...o }));
  return [...bookingItems, ...occurrenceItems].sort((a, b) => a.start_at.localeCompare(b.start_at));
});
const past = computed(() =>
  bookings.value
    .filter((b) => b.status !== "scheduled" || isBeforeToday(b.start_at, localTimeZone))
    .sort((a, b) => b.start_at.localeCompare(a.start_at))
    .slice(0, 20),
);

const weeks = computed(() => groupByWeekAndDay(upcoming.value, (item) => item.start_at, localTimeZone));

async function load(): Promise<void> {
  [bookings.value, occurrences.value] = await Promise.all([listMyBookings(), myOccurrences()]);
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
  <div class="flex max-w-2xl flex-col gap-6">
    <section>
      <BookingScheduleGroups :weeks="weeks">
        <template #default="{ item }">
          <BookingCard
            v-if="item.kind === 'booking'"
            :booking="item"
            role="student"
            @changed="load"
            @reschedule-requested="openReschedule"
          />
          <GroupOccurrenceCard v-else :occurrence="item" @changed="load" />
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

    <RescheduleModal
      v-if="reschedulingBooking"
      :booking="reschedulingBooking"
      @close="reschedulingBooking = null"
      @rescheduled="onRescheduled"
    />
  </div>
</template>
