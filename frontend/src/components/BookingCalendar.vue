<script setup lang="ts">
import { getLocalTimeZone, parseDate, today, type DateValue } from "@internationalized/date";
import { ChevronLeft, ChevronRight } from "lucide-vue-next";
import {
  CalendarCell,
  CalendarCellTrigger,
  CalendarGrid,
  CalendarGridBody,
  CalendarGridHead,
  CalendarGridRow,
  CalendarHeadCell,
  CalendarHeader,
  CalendarHeading,
  CalendarNext,
  CalendarPrev,
  CalendarRoot,
} from "reka-ui";
import { computed } from "vue";

// Сетка месяца для выбора даты занятия: свободные дни кликабельны, занятые —
// приглушены и недоступны. Список свободных дат приходит с бэкенда
// (getAvailableDates), здесь он только раскладывается по календарю.
// allowPast - режим переноса для репетитора: ему доступны и прошедшие даты (можно
// записать уже проведённое занятие задним числом), поэтому календарь не упирается
// в сегодняшний день, а прошедшие дни просто показываются бледнее.
const props = withDefaults(defineProps<{ availableDates: string[]; allowPast?: boolean }>(), {
  allowPast: false,
});
const emit = defineEmits<{ select: [date: string] }>();

const availableSet = computed(() => new Set(props.availableDates));

// Календарь листается только по диапазону, который вернул бэкенд: от первой
// свободной даты (но не раньше сегодняшнего дня) до последней.
const minValue = computed<DateValue>(() => {
  const now = today(getLocalTimeZone());
  const first = props.availableDates[0];
  if (!first) return now;
  const firstDate = parseDate(first);
  if (props.allowPast) return firstDate;
  return firstDate.compare(now) < 0 ? firstDate : now;
});

// Открываем календарь на текущем месяце, когда прошлое доступно: иначе репетитор
// попадал бы сразу на начало диапазона, то есть на месяц назад.
const todayValue = computed<DateValue>(() => today(getLocalTimeZone()));

function isPast(date: DateValue): boolean {
  return date.compare(todayValue.value) < 0;
}

const maxValue = computed<DateValue | undefined>(() => {
  const last = props.availableDates[props.availableDates.length - 1];
  return last ? parseDate(last) : undefined;
});

// Открываем на месяце с первой свободной датой - иначе при записи в конце месяца
// ученик увидит пустую сетку и решит, что мест нет.
const placeholder = computed<DateValue>(() => (props.allowPast ? todayValue.value : minValue.value));

function isDateUnavailable(date: DateValue): boolean {
  return !availableSet.value.has(date.toString());
}

function onSelect(date: DateValue | undefined): void {
  if (date) emit("select", date.toString());
}
</script>

<template>
  <CalendarRoot
    v-slot="{ grid, weekDays }"
    :default-placeholder="placeholder"
    :min-value="minValue"
    :max-value="maxValue"
    :is-date-unavailable="isDateUnavailable"
    :week-starts-on="1"
    weekday-format="short"
    locale="ru-RU"
    fixed-weeks
    initial-focus
    calendar-label="Выбор даты занятия"
    class="rounded-xl border border-slate-200 p-3 dark:border-slate-700"
    @update:model-value="onSelect"
  >
    <CalendarHeader class="flex items-center justify-between gap-2">
      <CalendarPrev
        class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-30 disabled:hover:bg-transparent dark:hover:bg-brand-900/30 dark:hover:text-brand-200"
        aria-label="Предыдущий месяц"
      >
        <ChevronLeft class="h-4 w-4" />
      </CalendarPrev>
      <CalendarHeading v-slot="{ headingValue }" class="text-base font-semibold first-letter:uppercase">
        {{ headingValue }}
      </CalendarHeading>
      <CalendarNext
        class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-30 disabled:hover:bg-transparent dark:hover:bg-brand-900/30 dark:hover:text-brand-200"
        aria-label="Следующий месяц"
      >
        <ChevronRight class="h-4 w-4" />
      </CalendarNext>
    </CalendarHeader>

    <CalendarGrid v-for="month in grid" :key="month.value.toString()" class="mt-3 w-full border-collapse">
      <CalendarGridHead>
        <CalendarGridRow class="grid grid-cols-7">
          <CalendarHeadCell
            v-for="day in weekDays"
            :key="day"
            class="pb-1 text-center text-xs font-medium capitalize text-slate-400"
          >
            {{ day }}
          </CalendarHeadCell>
        </CalendarGridRow>
      </CalendarGridHead>
      <CalendarGridBody class="grid gap-1">
        <CalendarGridRow v-for="(week, index) in month.rows" :key="`week-${index}`" class="grid grid-cols-7 gap-1">
          <CalendarCell v-for="weekDate in week" :key="weekDate.toString()" :date="weekDate" class="text-center">
            <CalendarCellTrigger
              :day="weekDate"
              :month="month.value"
              :class="allowPast && isPast(weekDate) ? 'text-slate-400 dark:text-slate-500' : ''"
              class="flex h-10 w-full cursor-pointer items-center justify-center rounded-lg text-base font-medium transition-all duration-150
                hover:-translate-y-0.5 hover:bg-brand-50 hover:text-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500
                data-[disabled]:cursor-not-allowed data-[disabled]:text-slate-300 data-[disabled]:hover:translate-y-0 data-[disabled]:hover:bg-transparent
                data-[outside-view]:invisible
                data-[selected]:bg-brand-500 data-[selected]:text-white data-[selected]:shadow-sm
                data-[today]:ring-1 data-[today]:ring-brand-300
                data-[unavailable]:cursor-not-allowed data-[unavailable]:text-slate-300 data-[unavailable]:hover:translate-y-0 data-[unavailable]:hover:bg-transparent data-[unavailable]:hover:text-slate-300
                dark:hover:bg-brand-900/30 dark:hover:text-brand-100 dark:data-[disabled]:text-slate-700 dark:data-[unavailable]:text-slate-700"
            />
          </CalendarCell>
        </CalendarGridRow>
      </CalendarGridBody>
    </CalendarGrid>
  </CalendarRoot>
</template>
