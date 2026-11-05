<script setup lang="ts">
import { StickyNote } from "lucide-vue-next";

import ScheduleWeekGrid from "@/components/ScheduleWeekGrid.vue";
import type { Booking } from "@/types/booking";
import type { TutorScheduleItem } from "@/types/group";
import type { TutorStudent } from "@/types/tutor";
import type { CalendarWeek } from "@/utils/scheduleGrouping";
import { formatTime } from "@/utils/time";

// Недельный вид занятий репетитора (каркас - ScheduleWeekGrid). В строке только
// время, ученик и класс (или название группы) - остальное в окне занятия по клику.
const props = defineProps<{ weeks: CalendarWeek<TutorScheduleItem>[]; students: Record<string, TutorStudent> }>();
const emit = defineEmits<{ open: [TutorScheduleItem] }>();

// «Фамилия Имя» из списка учеников; если ученика там нет (например, он ещё не
// подтянулся), - как назвал его сервер.
function studentName(booking: Booking): string {
  if (booking.is_manual_block) return "Личная блокировка";
  const student = booking.student_id ? props.students[booking.student_id] : undefined;
  if (student) return `${student.last_name} ${student.first_name}`.trim();
  return booking.student_display_name ?? "—";
}

function studentGrade(booking: Booking): number | null {
  return booking.student_id ? (props.students[booking.student_id]?.grade ?? null) : null;
}
</script>

<template>
  <ScheduleWeekGrid :weeks="weeks">
    <template #item="{ item }">
      <button
        v-if="item.kind === 'occurrence'"
        type="button"
        data-group-occurrence
        class="flex flex-col rounded-md bg-sky-50 px-1.5 py-1 text-left text-xs shadow-sm ring-1 ring-sky-200 transition-colors hover:ring-brand-400 dark:bg-sky-950/40 dark:ring-sky-800 dark:hover:ring-brand-600"
        @click="emit('open', item)"
      >
        <span class="font-semibold tabular-nums">{{ formatTime(item.start_at) }}</span>
        <span class="leading-tight">Группа «{{ item.group_name }}»</span>
        <span class="text-slate-400">участников: {{ item.member_count }}</span>
      </button>
      <button
        v-else
        type="button"
        class="flex flex-col rounded-md px-1.5 py-1 text-left text-xs transition-colors"
        :class="
          item.is_manual_block
            ? 'bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700'
            : 'bg-white shadow-sm ring-1 ring-slate-200 hover:ring-brand-400 dark:bg-slate-900 dark:ring-slate-700 dark:hover:ring-brand-600'
        "
        @click="emit('open', item)"
      >
        <span class="flex items-center justify-between gap-1">
          <span class="font-semibold tabular-nums">{{ formatTime(item.start_at) }}</span>
          <!-- Само примечание - в окне занятия; здесь только знак, что оно есть. -->
          <span v-if="item.notes" :title="item.notes" aria-label="Есть примечание" data-note>
            <StickyNote class="h-3 w-3 shrink-0 text-amber-500" />
          </span>
        </span>
        <span class="leading-tight">{{ studentName(item) }}</span>
        <span v-if="studentGrade(item)" class="text-slate-400">{{ studentGrade(item) }} кл.</span>
      </button>
    </template>
  </ScheduleWeekGrid>
</template>
