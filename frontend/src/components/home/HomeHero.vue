<script setup lang="ts">
import { CalendarCheck, GraduationCap, Search } from "lucide-vue-next";
import { onBeforeUnmount, ref } from "vue";

import { useAuthStore } from "@/stores/auth";

defineEmits<{ (e: "find-tutor"): void }>();

const auth = useAuthStore();

// Подзаголовок чередует две реплики - для ученика и для репетитора: платформа
// нужна обеим сторонам, а место под хиро одно.
const SLIDES = [
  "Выберите преподавателя, запишитесь на удобное время и занимайтесь онлайн. " +
    "Расписание, домашние задания, материалы и чат — в одном личном кабинете.",
  "Репетитор может настроить своё расписание, дни и время занятий, удобно вести " +
    "расписание с множеством учеников. Уведомления, индивидуальные и групповые занятия, и многое другое.",
];
const SLIDE_INTERVAL_MS = 7000;

const activeSlide = ref(0);
let timer: number | undefined;

function startRotation(): void {
  stopRotation();
  timer = window.setInterval(() => {
    activeSlide.value = (activeSlide.value + 1) % SLIDES.length;
  }, SLIDE_INTERVAL_MS);
}

function stopRotation(): void {
  if (timer !== undefined) window.clearInterval(timer);
  timer = undefined;
}

// Ручной выбор перезапускает таймер, иначе реплика может смениться сразу после
// клика по точке.
function selectSlide(index: number): void {
  activeSlide.value = index;
  startRotation();
}

startRotation();
onBeforeUnmount(stopRotation);
</script>

<template>
  <section class="mx-auto w-full max-w-5xl px-4 pt-12 pb-2 sm:pt-16">
    <div class="flex flex-col items-center gap-8 sm:flex-row sm:items-center sm:gap-10">
      <div class="animate-fade-in-up flex-1 text-center sm:text-left">
        <h1 class="text-3xl font-bold tracking-tight sm:text-5xl">
          Удобная платформа для <br class="hidden sm:block" />
          <span class="text-brand-600 dark:text-brand-300">репетиторов и учеников</span>
        </h1>
        <!-- Реплики лежат стопкой в одной ячейке грида, а не подменяются через
             <Transition>: так высота блока равна самой длинной из них и текст ниже
             не прыгает при смене. Наведение и фокус останавливают ротацию, чтобы
             реплику можно было дочитать. -->
        <div class="mt-4 grid" @mouseenter="stopRotation" @mouseleave="startRotation" @focusin="stopRotation" @focusout="startRotation">
          <p
            v-for="(slide, index) in SLIDES"
            :key="index"
            class="col-start-1 row-start-1 text-lg leading-relaxed text-slate-600 transition-opacity duration-500 dark:text-slate-300"
            :class="index === activeSlide ? 'opacity-100' : 'pointer-events-none opacity-0'"
            :aria-hidden="index !== activeSlide"
          >
            {{ slide }}
          </p>
        </div>
        <div class="mt-4 flex justify-center gap-2 sm:justify-start">
          <button
            v-for="(_, index) in SLIDES"
            :key="index"
            type="button"
            :aria-label="`Показать описание ${index + 1} из ${SLIDES.length}`"
            :aria-current="index === activeSlide"
            class="h-2 rounded-full transition-all duration-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500"
            :class="
              index === activeSlide
                ? 'w-6 bg-brand-500'
                : 'w-2 bg-slate-300 hover:bg-brand-300 dark:bg-slate-700 dark:hover:bg-brand-700'
            "
            @click="selectSlide(index)"
          ></button>
        </div>
        <div class="mt-7 flex flex-wrap justify-center gap-3 sm:justify-start">
          <button type="button" class="btn-primary text-base" @click="$emit('find-tutor')">
            <Search class="h-4 w-4" />
            Найти репетитора
          </button>
          <RouterLink v-if="!auth.isAuthenticated" to="/register?role=tutor" class="btn-outline text-base">
            <GraduationCap class="h-4 w-4" />
            Я репетитор
          </RouterLink>
          <RouterLink v-else to="/cabinet" class="btn-outline text-base">
            <CalendarCheck class="h-4 w-4" />
            Мои занятия
          </RouterLink>
        </div>
      </div>
      <!-- Логотип как декоративная иллюстрация: у сайта нет собственной графики,
           а фирменный знак уже отрисован под обе темы. -->
      <div class="relative shrink-0" aria-hidden="true">
        <div class="absolute inset-0 -z-10 rounded-full bg-brand-200/40 blur-3xl dark:bg-brand-800/30"></div>
        <img src="/logo-mark.svg" alt="" class="animate-float h-40 w-auto sm:h-56 dark:hidden" />
        <img src="/logo-mark-dark.svg" alt="" class="animate-float hidden h-40 w-auto sm:h-56 dark:block" />
      </div>
    </div>
  </section>
</template>
