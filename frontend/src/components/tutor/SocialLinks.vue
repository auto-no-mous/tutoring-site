<script setup lang="ts">
import type { TutorExtraLink } from "@/types/tutor";

defineProps<{
  telegramUrl?: string | null;
  vkUrl?: string | null;
  youtubeUrl?: string | null;
  extraLinks?: TutorExtraLink[];
}>();

const iconButtonClass =
  "flex h-9 w-9 items-center justify-center rounded-lg border border-slate-300 text-slate-600 transition-colors hover:border-slate-400 hover:text-slate-900 dark:border-slate-700 dark:text-slate-300 dark:hover:border-slate-500 dark:hover:text-white";
</script>

<template>
  <div class="flex flex-wrap gap-2">
    <a
      v-if="telegramUrl"
      :href="telegramUrl"
      target="_blank"
      rel="noopener noreferrer"
      title="Telegram"
      :class="iconButtonClass"
    >
      <svg viewBox="0 0 24 24" class="h-4.5 w-4.5" fill="currentColor">
        <path
          d="M21.5 3.5 2.7 10.9c-.9.4-.9 1.6.1 1.9l4.6 1.5 1.8 5.7c.3.9 1.4 1.1 2 .4l2.6-2.9 4.9 3.6c.8.6 1.9.1 2.1-.8l3.1-15.4c.2-1-.8-1.8-1.7-1.4Zm-3 3.8-8.4 7.6-.3 3.3-1.6-5 9.9-6.7c.3-.2.6.2.4.4Z"
        />
      </svg>
    </a>
    <a v-if="vkUrl" :href="vkUrl" target="_blank" rel="noopener noreferrer" title="ВКонтакте" :class="iconButtonClass">
      <span class="text-[13px] font-bold leading-none">VK</span>
    </a>
    <a
      v-if="youtubeUrl"
      :href="youtubeUrl"
      target="_blank"
      rel="noopener noreferrer"
      title="YouTube"
      :class="iconButtonClass"
    >
      <svg viewBox="0 0 24 24" class="h-4.5 w-4.5" fill="currentColor">
        <rect x="2" y="5" width="20" height="14" rx="4" />
        <path d="M10 9.3v5.4l4.8-2.7Z" class="fill-white dark:fill-slate-900" />
      </svg>
    </a>
    <a
      v-for="link in extraLinks ?? []"
      :key="link.url"
      :href="link.url"
      target="_blank"
      rel="noopener noreferrer"
      :title="link.label"
      :class="iconButtonClass"
    >
      <svg viewBox="0 0 24 24" class="h-4.5 w-4.5" fill="none" stroke="currentColor" stroke-width="2">
        <path
          d="M13.828 10.172a4 4 0 010 5.656l-3 3a4 4 0 01-5.656-5.656l1.5-1.5M10.172 13.828a4 4 0 010-5.656l3-3a4 4 0 015.656 5.656l-1.5 1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </a>
  </div>
</template>
