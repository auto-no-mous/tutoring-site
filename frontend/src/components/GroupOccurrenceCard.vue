<script setup lang="ts">
import { computed, ref } from "vue";

import { markOwnNoShow } from "@/api/groups";
import type { Whiteboard } from "@/api/whiteboards";
import WhiteboardLinks from "@/components/WhiteboardLinks.vue";
import { useToastStore } from "@/stores/toast";
import type { StudentGroupOccurrence } from "@/types/group";
import { formatDateTimeWithMsk } from "@/utils/time";

const props = defineProps<{ occurrence: StudentGroupOccurrence; whiteboards?: Whiteboard[] }>();
const emit = defineEmits<{ changed: [] }>();

const toast = useToastStore();
const showActions = ref(false);
const isBusy = ref(false);

const durationMinutes = computed(() =>
  Math.round((new Date(props.occurrence.end_at).getTime() - new Date(props.occurrence.start_at).getTime()) / 60000),
);

const hasDeclaredNoShow = computed(() => props.occurrence.my_attendance_outcome === "student_no_show");

async function markNoShow(): Promise<void> {
  if (
    !window.confirm(
      "Репетитор будет уведомлён, что вы не сможете присутствовать на этом занятии. Продолжить?",
    )
  ) {
    return;
  }
  isBusy.value = true;
  try {
    await markOwnNoShow(props.occurrence.id);
    toast.show("Репетитор уведомлён");
    emit("changed");
  } catch {
    toast.show("Не удалось отменить участие в занятии");
  } finally {
    isBusy.value = false;
  }
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between">
      <div>
        <div class="font-medium">{{ formatDateTimeWithMsk(occurrence.start_at) }}</div>
        <div class="text-sm text-slate-500">
          Группа «{{ occurrence.group_name }}» · Репетитор {{ occurrence.tutor_display_name }}
        </div>
        <div class="text-xs text-slate-400">Групповое · {{ durationMinutes }} мин</div>
      </div>
      <div class="flex items-center gap-2">
        <a
          v-if="occurrence.meeting_link"
          :href="occurrence.meeting_link"
          target="_blank"
          class="rounded-md bg-brand-500 px-2 py-1 text-xs text-white"
        >
          Перейти на занятие
        </a>
        <!-- Доска у группы общая: её ведёт репетитор в карточке группы. -->
        <WhiteboardLinks v-if="(whiteboards ?? []).length > 0" :boards="whiteboards ?? []" />
      </div>
    </div>

    <p v-if="hasDeclaredNoShow" class="mt-2 text-xs text-amber-600 dark:text-amber-400">
      Вы отметили, что не сможете присутствовать. Репетитор уведомлён.
    </p>
    <template v-else>
      <button type="button" class="mt-2 text-xs text-slate-500 underline" @click="showActions = !showActions">
        {{ showActions ? "Скрыть управление" : "Управление занятием" }}
      </button>
      <div v-if="showActions" class="mt-2 flex flex-wrap items-center gap-2 border-t border-slate-200 pt-2 dark:border-slate-800">
        <button
          type="button"
          class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 disabled:opacity-50 dark:border-red-800"
          :disabled="isBusy"
          @click="markNoShow"
        >
          Отменить
        </button>
      </div>
    </template>
  </div>
</template>
