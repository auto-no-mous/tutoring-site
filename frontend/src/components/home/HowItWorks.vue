<script setup lang="ts">
import { BellRing, CalendarPlus, UserSearch, Video } from "lucide-vue-next";

const steps = [
  {
    icon: UserSearch,
    title: "Выберите репетитора",
    text: "Фильтруйте каталог по предмету и цене, смотрите анкеты, рейтинг и отзывы учеников.",
  },
  {
    icon: CalendarPlus,
    title: "Запишитесь на занятие",
    text: "В календаре видно только реально свободное время. Индивидуально или в группу — на ваш выбор.",
  },
  {
    icon: Video,
    title: "Занимайтесь онлайн",
    text: "Репетитор присылает ссылку на встречу, а домашние задания и материалы остаются в кабинете.",
  },
  {
    icon: BellRing,
    title: "Ничего не забывайте",
    text: "Напоминания о занятиях и об изменениях в расписании приходят на почту и в Telegram.",
  },
];
</script>

<template>
  <section class="mx-auto w-full max-w-5xl px-4 pt-16">
    <h2 class="text-2xl font-semibold tracking-tight">Как это работает</h2>
    <ol class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <li
        v-for="(step, index) in steps"
        :key="step.title"
        class="surface-card relative flex flex-col p-5 transition-all duration-200 ease-out hover:-translate-y-1 hover:shadow-lg"
      >
        <span
          class="absolute top-4 right-4 text-3xl font-bold text-brand-100 select-none dark:text-slate-800"
          aria-hidden="true"
        >
          {{ index + 1 }}
        </span>
        <span class="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
          <component :is="step.icon" class="h-5 w-5" />
        </span>
        <h3 class="mt-4 text-lg font-semibold">{{ step.title }}</h3>
        <p class="mt-1.5 text-base leading-relaxed text-slate-600 dark:text-slate-300">{{ step.text }}</p>
      </li>
    </ol>
  </section>
</template>
