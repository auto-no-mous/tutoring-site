<script setup lang="ts">
import { computed } from "vue";

import { linkifySegments } from "@/utils/linkify";

// Текст с кликабельными адресами - без v-html: текст выводится как текст, ссылки -
// отдельными <a>. Сюда попадают и чужие письма (журнал почты в админке), и разметка
// из них не должна оказаться на странице. nofollow и noreferrer - потому что адрес
// пришёл от постороннего отправителя.
const props = defineProps<{ text: string }>();

const segments = computed(() => linkifySegments(props.text));
</script>

<template>
  <template v-for="(segment, i) in segments" :key="i">
    <a
      v-if="segment.type === 'link'"
      :href="segment.value"
      target="_blank"
      rel="noopener noreferrer nofollow"
      class="break-all text-brand-700 underline underline-offset-2 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
      >{{ segment.value }}</a
    ><template v-else>{{ segment.value }}</template>
  </template>
</template>
