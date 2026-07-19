<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { cancelBooking, listMyBookings } from "@/api/bookings";
import BookingScheduleGroups from "@/components/BookingScheduleGroups.vue";
import RescheduleModal from "@/components/student/RescheduleModal.vue";
import type { Booking } from "@/types/booking";
import { formatDateTimeWithMsk } from "@/utils/time";
import { groupByWeekAndDay } from "@/utils/scheduleGrouping";

const bookings = ref<Booking[]>([]);
const error = ref("");
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

async function cancel(booking: Booking): Promise<void> {
  error.value = "";
  if (!window.confirm("Отменить это занятие?")) return;
  try {
    await cancelBooking(booking.id);
    await load();
  } catch {
    error.value = "Отмена недоступна: нарушены сроки или лимит отмен репетитора.";
  }
}

function openReschedule(booking: Booking): void {
  error.value = "";
  reschedulingBooking.value = booking;
}

async function onRescheduled(): Promise<void> {
  reschedulingBooking.value = null;
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex max-w-2xl flex-col gap-6">
    <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>

    <section>
      <BookingScheduleGroups :weeks="weeks">
        <template #default="{ item: booking }">
          <div class="flex items-center justify-between">
            <div class="font-medium">{{ formatDateTimeWithMsk(booking.start_at) }}</div>
            <a v-if="booking.meeting_link" :href="booking.meeting_link" target="_blank" class="text-xs underline">Перейти на занятие</a>
          </div>
          <div class="text-sm text-slate-500">
            {{ booking.lesson_type_name }} · Репетитор {{ booking.tutor_display_name }}
          </div>
          <div v-if="booking.recurring_series_id" class="mt-1 text-xs text-slate-500">Еженедельная запись</div>
          <div class="mt-2 flex flex-wrap gap-2">
            <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="openReschedule(booking)">
              Перенести
            </button>
            <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="cancel(booking)">
              Отменить
            </button>
          </div>
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
