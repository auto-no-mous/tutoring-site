<script setup lang="ts">
import type { Booking } from "@/types/booking";
import type { TutorStudent } from "@/types/tutor";
import type { CalendarWeek } from "@/utils/scheduleGrouping";
import { formatTime } from "@/utils/time";

// Недельный вид занятий репетитора: блок на неделю, в нём семь столбцов по дням. В
// строке только время, ученик и класс - остальное в окне занятия по клику.
const props = defineProps<{ weeks: CalendarWeek<Booking>[]; students: Record<string, TutorStudent> }>();
const emit = defineEmits<{ open: [Booking] }>();

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
  <div class="flex flex-col gap-6">
    <section v-for="week in weeks" :key="week.label" :data-week="week.label">
      <h2 class="text-lg font-medium">{{ week.label }}</h2>
      <!-- На узком экране семь столбцов не помещаются - сетка прокручивается вбок,
           а не сжимается до нечитаемого. -->
      <div class="mt-2 overflow-x-auto">
        <div class="grid min-w-[56rem] grid-cols-7 gap-1.5">
          <div
            v-for="day in week.days"
            :key="day.dateIso"
            :data-day="day.dateIso"
            class="flex min-h-28 flex-col rounded-lg border"
            :class="[
              day.isToday
                ? 'border-brand-300 bg-brand-50/70 dark:border-brand-800 dark:bg-brand-900/30'
                : 'border-slate-200 dark:border-slate-800',
              day.isPast ? 'opacity-60' : '',
            ]"
          >
            <div
              class="flex items-baseline justify-between border-b px-2 py-1.5 text-xs"
              :class="day.isToday ? 'border-brand-200 dark:border-brand-800' : 'border-slate-200 dark:border-slate-800'"
            >
              <span class="font-semibold" :class="day.isToday ? 'text-brand-700 dark:text-brand-300' : ''">
                {{ day.isToday ? "Сегодня" : day.weekday }}
              </span>
              <span class="text-slate-400">{{ day.dateLabel }}</span>
            </div>
            <div class="flex flex-1 flex-col gap-1 p-1">
              <button
                v-for="booking in day.items"
                :key="booking.id"
                type="button"
                class="flex flex-col rounded-md px-1.5 py-1 text-left text-xs transition-colors"
                :class="
                  booking.is_manual_block
                    ? 'bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700'
                    : 'bg-white shadow-sm ring-1 ring-slate-200 hover:ring-brand-400 dark:bg-slate-900 dark:ring-slate-700 dark:hover:ring-brand-600'
                "
                @click="emit('open', booking)"
              >
                <span class="font-semibold tabular-nums">{{ formatTime(booking.start_at) }}</span>
                <span class="leading-tight">{{ studentName(booking) }}</span>
                <span v-if="studentGrade(booking)" class="text-slate-400">{{ studentGrade(booking) }} кл.</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
