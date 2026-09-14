<script setup lang="ts">
import { computed } from "vue";

// Фото есть далеко не у всех: оно появляется при входе через VK или Яндекс либо
// когда человек загрузил его сам. Без запасного варианта список учеников выглядел
// рваным - у половины карточек картинка, у половины пустое место. Кружок с первой
// буквой имени закрывает дыру и заодно помогает различать строки взглядом.
const props = defineProps<{
  photoUrl?: string | null;
  name?: string | null;
  size?: "sm" | "md" | "lg";
}>();

const SIZES = {
  sm: "h-8 w-8 text-xs",
  md: "h-10 w-10 text-sm",
  lg: "h-14 w-14 text-lg",
} as const;

const sizeClass = computed(() => SIZES[props.size ?? "md"]);

const initial = computed(() => {
  const trimmed = (props.name ?? "").trim();
  return trimmed ? trimmed[0].toUpperCase() : "?";
});
</script>

<template>
  <img
    v-if="photoUrl"
    :src="photoUrl"
    alt=""
    class="shrink-0 rounded-full object-cover"
    :class="sizeClass"
  />
  <div
    v-else
    class="flex shrink-0 items-center justify-center rounded-full bg-brand-100 font-semibold text-brand-800 dark:bg-brand-900/60 dark:text-brand-200"
    :class="sizeClass"
    :title="name ?? undefined"
    aria-hidden="true"
  >
    {{ initial }}
  </div>
</template>
