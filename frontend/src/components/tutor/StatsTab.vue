<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getTutorStats } from "@/api/stats";
import ActivityLog from "@/components/ActivityLog.vue";
import StudentsBlock from "@/components/tutor/StudentsBlock.vue";
import type { TutorStats } from "@/types/stats";

const stats = ref<TutorStats | null>(null);

onMounted(async () => {
  stats.value = await getTutorStats();
});
</script>

<template>
  <div class="flex max-w-4xl flex-col gap-8">
    <div v-if="stats" class="grid max-w-xl grid-cols-3 gap-4">
      <div class="rounded-lg border border-slate-200 p-4 text-center dark:border-slate-800">
        <div class="text-2xl font-semibold">{{ stats.total_lessons_held }}</div>
        <div class="text-xs text-slate-500">занятий проведено</div>
      </div>
      <div class="rounded-lg border border-slate-200 p-4 text-center dark:border-slate-800">
        <div class="text-2xl font-semibold">{{ stats.homeworks_done }}</div>
        <div class="text-xs text-slate-500">домашних заданий выполнено</div>
      </div>
      <div class="rounded-lg border border-slate-200 p-4 text-center dark:border-slate-800">
        <div class="text-2xl font-semibold">{{ stats.unique_students_this_month }}</div>
        <div class="text-xs text-slate-500">учеников в этом месяце</div>
      </div>
    </div>

    <StudentsBlock />

    <section>
      <h2 class="text-lg font-medium">Журнал событий</h2>
      <div class="mt-3">
        <ActivityLog role="tutor" />
      </div>
    </section>
  </div>
</template>
