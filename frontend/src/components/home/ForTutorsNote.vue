<script setup lang="ts">
import { Link2, Megaphone, Settings2 } from "lucide-vue-next";

import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();

// Честная секция для репетиторов: сайт пока не продвигается среди учеников, и
// обещать поток заявок из каталога было бы враньём. Та же мысль приходит репетитору
// в приветственном системном уведомлении при регистрации - см. DEFAULT_TEMPLATES
// (WELCOME, TUTOR) в backend/app/services/system_notification_service.py.
const points = [
  {
    icon: Megaphone,
    title: "Каталог — не источник учеников",
    text: "Сайт пока не продвигается среди учеников, и поток заявок из каталога ждать не стоит. Мы предпочитаем сказать это прямо, а не обещать очередь.",
  },
  {
    icon: Link2,
    title: "Что работает — ваша ссылка",
    text: "Разместите ссылку на свою страницу там, где вас уже находят: в соцсетях, мессенджерах, объявлениях. Ученик откроет её, увидит расписание и цены и запишется сам — без переписки «а когда вы свободны?».",
  },
  {
    icon: Settings2,
    title: "Главное — управление занятиями",
    text: "my-tutor.ru — прежде всего инструмент для ведения индивидуальных и групповых занятий: расписание, записи, группы, домашние задания, напоминания и чат в одном кабинете.",
  },
];
</script>

<template>
  <section class="mx-auto w-full max-w-5xl px-4 pt-16">
    <div class="surface-card p-6 sm:p-8">
      <h2 class="text-2xl font-semibold tracking-tight">Репетитору: чего ждать от сайта</h2>
      <p class="mt-1.5 text-base text-slate-500 dark:text-slate-400">
        Коротко и без обещаний: зачем регистрироваться, если учеников сайт пока не приводит.
      </p>
      <div class="mt-6 grid gap-5 sm:grid-cols-3">
        <div v-for="point in points" :key="point.title" class="flex flex-col">
          <span class="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
            <component :is="point.icon" class="h-5 w-5" />
          </span>
          <h3 class="mt-4 text-lg font-semibold">{{ point.title }}</h3>
          <p class="mt-1.5 text-base leading-relaxed text-slate-600 dark:text-slate-300">{{ point.text }}</p>
        </div>
      </div>
      <RouterLink
        v-if="!auth.isAuthenticated"
        to="/register?role=tutor"
        class="btn-primary mt-6 text-base"
      >
        Создать страницу репетитора
      </RouterLink>
      <RouterLink v-else-if="auth.user?.role === 'tutor'" to="/cabinet?tab=profile" class="btn-outline mt-6 text-base">
        Открыть свой профиль
      </RouterLink>
    </div>
  </section>
</template>
