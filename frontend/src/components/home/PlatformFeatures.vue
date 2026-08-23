<script setup lang="ts">
import { BookOpenCheck, CalendarClock, Globe2, MessageCircle, Star, Users } from "lucide-vue-next";

const features = [
  {
    icon: CalendarClock,
    title: "Живое расписание",
    text: "Занятие можно перенести или отменить в кабинете — репетитор сразу увидит изменение, а слот освободится для других.",
  },
  {
    icon: BookOpenCheck,
    title: "Домашние задания",
    text: "Задания с дедлайнами и файлами, работы учеников и проверка с комментарием репетитора — всё хранится в одном месте.",
  },
  {
    icon: MessageCircle,
    title: "Чат с репетитором",
    text: "Личная переписка с преподавателем и общий чат группы — не нужно смешивать учёбу с личными мессенджерами.",
  },
  {
    icon: Users,
    title: "Групповые занятия",
    text: "Регулярные группы с постоянным расписанием и общей ссылкой на встречу — дешевле индивидуальных занятий.",
  },
  {
    icon: Star,
    title: "Честные отзывы",
    text: "Оставить отзыв может только ученик, у которого с этим репетитором действительно было занятие.",
  },
  {
    icon: Globe2,
    title: "Ваш часовой пояс",
    text: "Время занятий показывается в вашем поясе, рядом — московское. Никакой арифметики в уме.",
  },
];
</script>

<template>
  <section class="mx-auto w-full max-w-5xl px-4 pt-16">
    <h2 class="text-2xl font-semibold tracking-tight">Что внутри платформы</h2>
    <p class="mt-1.5 text-base text-slate-500 dark:text-slate-400">
      Не доска объявлений: после записи вы с репетитором работаете в общем кабинете.
    </p>
    <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="feature in features"
        :key="feature.title"
        class="surface-card flex gap-4 p-5 transition-all duration-200 ease-out hover:-translate-y-1 hover:shadow-lg"
      >
        <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
          <component :is="feature.icon" class="h-5 w-5" />
        </span>
        <div>
          <h3 class="text-lg font-semibold">{{ feature.title }}</h3>
          <p class="mt-1.5 text-base leading-relaxed text-slate-600 dark:text-slate-300">{{ feature.text }}</p>
        </div>
      </div>
    </div>
  </section>
</template>
