<script setup lang="ts">
import type { BlogPostListItem } from "@/types/blog";
import { formatArticleDate } from "@/utils/time";

defineProps<{ post: BlogPostListItem }>();
</script>

<template>
  <RouterLink
    :to="`/blog/${post.slug}`"
    class="surface-card group flex flex-col overflow-hidden transition-all duration-200 ease-out hover:-translate-y-1 hover:border-brand-300 hover:shadow-lg dark:hover:border-brand-700"
  >
    <img
      v-if="post.cover_image_url"
      :src="post.cover_image_url"
      alt=""
      class="h-40 w-full object-cover transition-transform duration-300 group-hover:scale-105"
    />
    <!-- Без обложки карточка не должна быть заметно ниже соседних, поэтому вместо
         картинки остаётся фирменная полоска. -->
    <div v-else class="h-2 w-full bg-gradient-to-r from-brand-400 to-aqua-400"></div>
    <div class="flex flex-1 flex-col p-5">
      <time v-if="post.published_at" :datetime="post.published_at" class="text-sm text-slate-500 dark:text-slate-400">
        {{ formatArticleDate(post.published_at) }}
      </time>
      <h3 class="mt-1 text-lg font-semibold group-hover:text-brand-700 dark:group-hover:text-brand-300">
        {{ post.title }}
      </h3>
      <p v-if="post.summary" class="mt-2 line-clamp-3 text-base leading-relaxed text-slate-600 dark:text-slate-300">
        {{ post.summary }}
      </p>
      <span class="mt-auto pt-4 text-base font-medium text-brand-700 dark:text-brand-300">Читать →</span>
    </div>
  </RouterLink>
</template>
