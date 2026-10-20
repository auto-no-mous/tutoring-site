<script setup lang="ts">
import { computed } from "vue";

import { HOMEWORK_PAGE_SIZE } from "@/utils/homework";

const props = defineProps<{ remaining: number }>();
defineEmits<{ more: [] }>();

const next = computed(() => Math.min(HOMEWORK_PAGE_SIZE, props.remaining));
</script>

<template>
  <button
    v-if="remaining > 0"
    type="button"
    class="w-fit text-sm text-brand-600 underline hover:text-brand-700 dark:text-brand-300 dark:hover:text-brand-200"
    @click="$emit('more')"
  >
    Показать ещё {{ next }} (осталось {{ remaining }})
  </button>
</template>
