<script setup lang="ts">
import { computed } from "vue";

import { useAuthStore } from "@/stores/auth";
import { MSK_TIMEZONE, mskOffsetHours } from "@/utils/time";

// Всё время на сайте московское - и в кабинете репетитора, и у ученика. Тому, кто
// живёт в другом поясе, об этом надо сказать прямо в момент выбора времени: пока
// сайт показывал местное время, а письма московское, один и тот же урок назывался
// двумя числами, и переносы попадали не туда.
const auth = useAuthStore();

// Пояс из настроек, а если там пусто - тот, что сообщает браузер.
const zone = computed(
  () => auth.user?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || MSK_TIMEZONE,
);

const offset = computed(() => mskOffsetHours(zone.value));

const localNow = computed(() =>
  new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", timeZone: zone.value }).format(new Date()),
);

const mskNow = computed(() =>
  new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", timeZone: MSK_TIMEZONE }).format(new Date()),
);

function hoursWord(n: number): string {
  const abs = Math.abs(n) % 20;
  if (abs === 1) return "час";
  if (abs >= 2 && abs <= 4) return "часа";
  return "часов";
}
</script>

<template>
  <p
    v-if="offset !== 0"
    class="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900
      dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
  >
    Все времена на сайте — московские. Сейчас в Москве {{ mskNow }}, у вас {{ localNow }}:
    разница {{ offset > 0 ? "+" : "−" }}{{ Math.abs(offset) }} {{ hoursWord(offset) }}.
  </p>
</template>
