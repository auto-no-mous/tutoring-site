<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getStudentStats } from "@/api/stats";
import type { StudentStats } from "@/types/stats";

const stats = ref<StudentStats | null>(null);

onMounted(async () => {
  stats.value = await getStudentStats();
});
</script>

<template>
  <div v-if="stats" class="grid max-w-xl grid-cols-3 gap-4">
    <div class="rounded-lg border border-slate-200 p-4 text-center dark:border-slate-800">
      <div class="text-2xl font-semibold">{{ stats.lessons_completed }}</div>
      <div class="text-xs text-slate-500">занятий проведено</div>
    </div>
    <div class="rounded-lg border border-slate-200 p-4 text-center dark:border-slate-800">
      <div class="text-2xl font-semibold">{{ stats.homework_done }}/{{ stats.homework_total }}</div>
      <div class="text-xs text-slate-500">домашних заданий выполнено</div>
    </div>
    <div class="rounded-lg border border-slate-200 p-4 text-center dark:border-slate-800">
      <div class="text-2xl font-semibold">{{ Math.round(stats.homework_completion_rate * 100) }}%</div>
      <div class="text-xs text-slate-500">доля выполненных ДЗ</div>
    </div>
  </div>
</template>
