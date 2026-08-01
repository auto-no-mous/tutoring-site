<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import { getStudentLog, getTutorLog } from "@/api/stats";
import { ACTIVITY_EVENT_GROUPS, ACTIVITY_EVENT_LABELS, type ActivityLogEntry } from "@/types/stats";
import { formatDateTimeWithMsk } from "@/utils/time";

const props = defineProps<{ role: "tutor" | "student" }>();

const PAGE_SIZE = 20;

const entries = ref<ActivityLogEntry[]>([]);
const total = ref(0);
const page = ref(1);
const isLoading = ref(false);

const showFilters = ref(false);
const checkedTypes = reactive(new Set<string>());
const dateFrom = ref("");
const dateTo = ref("");

const activeFilterCount = computed(() => checkedTypes.size + (dateFrom.value ? 1 : 0) + (dateTo.value ? 1 : 0));

// Green = a good outcome, red = a negative one (no-show/cancelled/rejected/removed),
// amber = neutral-but-worth-noticing (rescheduled), slate = plain informational.
const STATUS_STYLES: Record<string, string> = {
  lesson_conducted: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400",
  group_lesson_conducted: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400",
  group_application_accepted: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400",
  lesson_student_no_show: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
  lesson_tutor_no_show: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
  group_lesson_student_no_show: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
  lesson_cancelled_by_student: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
  lesson_cancelled_by_tutor: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
  group_lesson_cancelled: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
  group_application_rejected: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
  group_membership_removed: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
  lesson_rescheduled: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
  group_lesson_rescheduled: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
  group_membership_left: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
};

function statusStyle(entry: ActivityLogEntry): string {
  return STATUS_STYLES[entry.event_type] ?? "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300";
}

async function load(reset: boolean): Promise<void> {
  isLoading.value = true;
  try {
    const params = {
      event_types: checkedTypes.size > 0 ? [...checkedTypes] : undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      page: reset ? 1 : page.value,
      page_size: PAGE_SIZE,
    };
    const data = props.role === "tutor" ? await getTutorLog(params) : await getStudentLog(params);
    entries.value = reset ? data.entries : [...entries.value, ...data.entries];
    total.value = data.total;
    page.value = data.page;
  } finally {
    isLoading.value = false;
  }
}

function toggleType(type: string): void {
  if (checkedTypes.has(type)) {
    checkedTypes.delete(type);
  } else {
    checkedTypes.add(type);
  }
  load(true);
}

function clearFilters(): void {
  checkedTypes.clear();
  dateFrom.value = "";
  dateTo.value = "";
  load(true);
}

function loadMore(): void {
  page.value += 1;
  load(false);
}

watch([dateFrom, dateTo], () => load(true));

load(true);
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="rounded-lg border border-slate-200 dark:border-slate-800">
      <button
        type="button"
        class="flex w-full items-center justify-between px-4 py-2.5 text-sm"
        @click="showFilters = !showFilters"
      >
        <span class="font-medium">
          Фильтры
          <span v-if="activeFilterCount > 0" class="ml-1 text-xs text-slate-500">({{ activeFilterCount }})</span>
        </span>
        <span class="text-slate-400">{{ showFilters ? "▲" : "▼" }}</span>
      </button>

      <div v-if="showFilters" class="flex flex-wrap items-start gap-6 border-t border-slate-200 p-4 text-sm dark:border-slate-800">
        <div v-for="group in ACTIVITY_EVENT_GROUPS" :key="group.label" class="flex flex-col gap-1.5">
          <span class="font-medium text-slate-600 dark:text-slate-300">{{ group.label }}</span>
          <label v-for="type in group.types" :key="type" class="flex items-center gap-2 text-xs">
            <input type="checkbox" :checked="checkedTypes.has(type)" @change="toggleType(type)" />
            {{ ACTIVITY_EVENT_LABELS[type] }}
          </label>
        </div>
        <div class="flex flex-col gap-1.5">
          <span class="font-medium text-slate-600 dark:text-slate-300">Период</span>
          <label class="flex items-center gap-2 text-xs">
            с
            <input v-model="dateFrom" type="date" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
          </label>
          <label class="flex items-center gap-2 text-xs">
            по
            <input v-model="dateTo" type="date" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
          </label>
        </div>
        <button
          v-if="activeFilterCount > 0"
          type="button"
          class="self-end text-xs text-slate-500 underline"
          @click="clearFilters"
        >
          Сбросить фильтры
        </button>
      </div>
    </div>

    <p v-if="!isLoading && entries.length === 0" class="text-sm text-slate-400">Событий не найдено.</p>

    <div v-else class="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
      <table class="w-full text-left text-sm">
        <thead>
          <tr class="border-b border-slate-200 text-xs text-slate-500 dark:border-slate-800">
            <th class="px-3 py-2 font-medium">Тип</th>
            <th class="px-3 py-2 font-medium">{{ role === "tutor" ? "Ученик" : "Репетитор" }}</th>
            <th class="px-3 py-2 font-medium">Длительность</th>
            <th class="px-3 py-2 font-medium">Дата/время</th>
            <th class="px-3 py-2 font-medium">Статус</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
          <tr v-for="entry in entries" :key="entry.id">
            <td class="px-3 py-2">{{ entry.format_label }}</td>
            <td class="px-3 py-2">{{ entry.counterpart_name }}</td>
            <td class="px-3 py-2 text-slate-500">{{ entry.duration_minutes != null ? `${entry.duration_minutes} мин` : "—" }}</td>
            <td class="px-3 py-2 text-slate-500">{{ formatDateTimeWithMsk(entry.lesson_at ?? entry.occurred_at) }}</td>
            <td class="px-3 py-2">
              <span class="rounded-full px-2 py-0.5 text-xs font-medium" :class="statusStyle(entry)">{{ entry.status_label }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="entries.length < total" class="flex justify-center">
      <button
        type="button"
        :disabled="isLoading"
        class="rounded-md border border-slate-300 px-4 py-1.5 text-sm disabled:opacity-50 dark:border-slate-700"
        @click="loadMore"
      >
        {{ isLoading ? "Загрузка…" : "Показать ещё" }}
      </button>
    </div>
  </div>
</template>
