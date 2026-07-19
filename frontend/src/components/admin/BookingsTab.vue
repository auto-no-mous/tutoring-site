<script setup lang="ts">
import { onMounted, ref } from "vue";

import { deleteBooking, listBookings } from "@/api/admin";
import type { Booking } from "@/types/booking";
import { formatDateTimeWithMsk } from "@/utils/time";

const bookings = ref<Booking[]>([]);
const isLoading = ref(true);

const statusLabels: Record<string, string> = {
  scheduled: "запланировано",
  cancelled_by_student: "отменено учеником",
  cancelled_by_tutor: "отменено репетитором",
  rescheduled: "перенесено",
  completed: "проведено",
};

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    bookings.value = await listBookings();
  } finally {
    isLoading.value = false;
  }
}

async function remove(booking: Booking): Promise<void> {
  if (!window.confirm("Удалить запись безвозвратно?")) return;
  await deleteBooking(booking.id);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex flex-col gap-2">
    <p v-if="isLoading" class="text-sm text-slate-400">Загрузка…</p>
    <div v-for="booking in bookings" :key="booking.id" class="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
      <div>
        <div class="font-medium">{{ formatDateTimeWithMsk(booking.start_at) }}</div>
        <div class="text-slate-500">
          {{ booking.student_display_name ?? (booking.is_manual_block ? "Личная блокировка" : "—") }}
          · {{ statusLabels[booking.status] ?? booking.status }}
        </div>
      </div>
      <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="remove(booking)">
        Удалить
      </button>
    </div>
    <p v-if="!isLoading && bookings.length === 0" class="text-sm text-slate-400">Занятий пока нет.</p>
  </div>
</template>
