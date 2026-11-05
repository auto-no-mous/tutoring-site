<script setup lang="ts" generic="T extends { id: string }">
import type { CalendarWeek } from "@/utils/scheduleGrouping";

// Каркас недельного вида: блок на неделю, в нём семь столбцов по дням. Что рисовать
// в строке дня, решает родитель (слот item) - у репетитора это ученик и класс, у
// ученика - репетитор или группа.
defineProps<{ weeks: CalendarWeek<T>[] }>();
</script>

<template>
  <div class="flex flex-col gap-6">
    <section v-for="week in weeks" :key="week.label" :data-week="week.label">
      <h2 class="text-lg font-medium">{{ week.label }}</h2>
      <!-- Неделя переносится по строкам, когда семь дней в ряд не помещаются: 7 в ряд,
           иначе 4 + 3, на телефоне - по 2. Раньше сетка прокручивалась вбок, и на
           телефоне неделю приходилось листать пальцем поперёк страницы. Решает ширина
           самого блока (container query), пороги - чтобы день не был уже ~8rem:
           столько нужно на время и «Фамилию Имя». По два дня в ряд пустые дни ниже, иначе
           почти пустая неделя растягивалась на телефоне на два экрана. -->
      <div class="@container mt-2">
        <div class="grid grid-cols-2 gap-1.5 @min-[34rem]:grid-cols-4 @min-[56rem]:grid-cols-7">
          <div
            v-for="day in week.days"
            :key="day.dateIso"
            :data-day="day.dateIso"
            class="flex min-h-16 flex-col rounded-lg border @min-[34rem]:min-h-28"
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
              <template v-for="item in day.items" :key="item.id">
                <slot name="item" :item="item" />
              </template>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
