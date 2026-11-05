<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { updateOccurrence } from "@/api/groups";
import { useToastStore } from "@/stores/toast";
import type { TutorGroupOccurrence } from "@/types/group";
import { apiErrorMessage } from "@/utils/apiError";
import { formatDateTimeWithMsk } from "@/utils/time";

// Занятие группы в расписании репетитора - и в списке, и в окне из недельной сетки.
// Посещаемость, перенос и состав группы остаются во вкладке «Группы»: здесь только
// то, что нужно перед самим занятием.
const props = defineProps<{ occurrence: TutorGroupOccurrence }>();
const emit = defineEmits<{ changed: [] }>();

const router = useRouter();
const toast = useToastStore();
const isBusy = ref(false);

const durationMinutes = computed(() =>
  Math.round((new Date(props.occurrence.end_at).getTime() - new Date(props.occurrence.start_at).getTime()) / 60000),
);

async function cancel(): Promise<void> {
  if (!window.confirm(`Отменить занятие группы «${props.occurrence.group_name}»?`)) return;
  isBusy.value = true;
  try {
    await updateOccurrence(props.occurrence.group_id, props.occurrence.id, { status: "cancelled" });
    toast.show("Занятие группы отменено");
    emit("changed");
  } catch (err) {
    toast.show(apiErrorMessage(err, "Не удалось отменить занятие"));
  } finally {
    isBusy.value = false;
  }
}

function openGroups(): void {
  router.push({ path: "/cabinet", query: { tab: "groups" } });
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between gap-2">
      <div>
        <div class="font-medium">{{ formatDateTimeWithMsk(occurrence.start_at) }}</div>
        <div class="text-sm text-slate-500">Группа «{{ occurrence.group_name }}»</div>
        <div class="text-xs text-slate-400">
          Групповое · {{ durationMinutes }} мин · участников: {{ occurrence.member_count }}
        </div>
      </div>
      <a
        v-if="occurrence.meeting_link"
        :href="occurrence.meeting_link"
        target="_blank"
        class="shrink-0 rounded-md bg-brand-500 px-2 py-1 text-xs text-white"
      >
        Перейти на занятие
      </a>
    </div>
    <div class="mt-2 flex flex-wrap items-center gap-2">
      <button type="button" class="text-xs text-slate-500 underline" @click="openGroups">Открыть группы</button>
      <button
        type="button"
        class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 disabled:opacity-50 dark:border-red-800"
        :disabled="isBusy"
        @click="cancel"
      >
        Отменить занятие
      </button>
    </div>
  </div>
</template>
