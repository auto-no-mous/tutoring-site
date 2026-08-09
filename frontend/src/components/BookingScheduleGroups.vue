<script setup lang="ts" generic="T extends { id: string; start_at: string; end_at: string }">
import { onBeforeUnmount, onMounted, ref } from "vue";

import type { WeekGroup } from "@/utils/scheduleGrouping";

defineProps<{ weeks: WeekGroup<T>[] }>();

// Refreshed periodically so the "idёт сейчас" highlight appears/disappears without
// requiring a reload while the tab is open.
const now = ref(new Date());
let timer: number | undefined;
onMounted(() => {
  timer = window.setInterval(() => {
    now.value = new Date();
  }, 30000);
});
onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
});

const IMMINENT_WINDOW_MS = 15 * 60 * 1000;

function isHappeningNow(item: T): boolean {
  const t = now.value.getTime();
  return t >= new Date(item.start_at).getTime() && t < new Date(item.end_at).getTime();
}

// Starts within the next 15 minutes (but hasn't started yet - once it has, it's
// "happening now" instead).
function isStartingSoon(item: T): boolean {
  const t = now.value.getTime();
  const start = new Date(item.start_at).getTime();
  return t < start && start - t <= IMMINENT_WINDOW_MS;
}

function isImminent(item: T): boolean {
  return isHappeningNow(item) || isStartingSoon(item);
}

function minutesUntilStart(item: T): number {
  return Math.max(0, Math.round((new Date(item.start_at).getTime() - now.value.getTime()) / 60000));
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <div v-for="week in weeks" :key="week.label">
      <h2 class="text-lg font-medium">{{ week.label }}</h2>
      <div class="mt-2 flex flex-col gap-4">
        <div v-for="day in week.days" :key="day.dateIso">
          <div
            class="flex items-baseline gap-2 text-sm font-medium"
            :class="day.isToday ? 'text-slate-900 dark:text-white' : 'text-slate-600 dark:text-slate-300'"
          >
            <span>{{ day.label }}</span>
            <span class="text-xs font-normal text-slate-400">{{ day.dateLabel }}</span>
          </div>
          <p v-if="day.items.length === 0" class="mt-1 text-sm text-slate-400">
            {{ day.isToday ? "Сегодня занятий нет" : "Занятий нет" }}
          </p>
          <div v-else class="mt-1 flex flex-col gap-2">
            <div
              v-for="item in day.items"
              :key="item.id"
              class="rounded-md border px-3 py-2 transition-colors"
              :class="
                isImminent(item)
                  ? 'border-blue-500 bg-blue-100 ring-1 ring-blue-400 dark:border-blue-500 dark:bg-blue-950 dark:ring-blue-600'
                  : day.isToday
                    ? 'border-blue-200 bg-blue-50/70 dark:border-blue-900 dark:bg-blue-950/30'
                    : week.isCurrentWeek
                      ? 'border-blue-100 bg-blue-50/30 dark:border-blue-950/60 dark:bg-blue-950/10'
                      : 'border-slate-200 dark:border-slate-800'
              "
            >
              <div v-if="isImminent(item)" class="mb-1 flex items-center gap-1 text-xs font-semibold text-blue-700 dark:text-blue-300">
                <span class="inline-block h-1.5 w-1.5 rounded-full bg-blue-600 dark:bg-blue-400"></span>
                {{ isHappeningNow(item) ? "Идёт сейчас" : `Начинается через ${minutesUntilStart(item)} мин` }}
              </div>
              <slot :item="item" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
