<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { listMyBookings } from "@/api/bookings";
import BookingCard from "@/components/BookingCard.vue";
import BookingScheduleGroups from "@/components/BookingScheduleGroups.vue";
import RescheduleModal from "@/components/RescheduleModal.vue";
import { useToastStore } from "@/stores/toast";
import type { Booking } from "@/types/booking";
import { formatDateTimeWithMsk } from "@/utils/time";
import { groupByWeekAndDay } from "@/utils/scheduleGrouping";

const toast = useToastStore();

const bookings = ref<Booking[]>([]);
const reschedulingBooking = ref<Booking | null>(null);

const localTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

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

const weeks = computed(() => groupByWeekAndDay(upcoming.value, (b) => b.start_at, localTimeZone));

async function load(): Promise<void> {
  bookings.value = await listMyBookings();
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
        <template #default="{ item: booking }">
          <BookingCard :booking="booking" role="student" @changed="load" @reschedule-requested="openReschedule" />
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
