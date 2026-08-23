<script setup lang="ts">
import { onMounted, ref } from "vue";

import { listBlogPosts } from "@/api/blog";
import BlogPostCard from "@/components/blog/BlogPostCard.vue";
import type { BlogPostListItem } from "@/types/blog";

const PAGE_SIZE = 12;

const posts = ref<BlogPostListItem[]>([]);
const total = ref(0);
const page = ref(0);
const isLoading = ref(true);
const isLoadingMore = ref(false);

async function loadMore(): Promise<void> {
  if (isLoadingMore.value) return;
  isLoadingMore.value = true;
  try {
    const result = await listBlogPosts({ page: page.value + 1, page_size: PAGE_SIZE });
    posts.value.push(...result.items);
    total.value = result.total;
    page.value = result.page;
  } finally {
    isLoadingMore.value = false;
  }
}

onMounted(async () => {
  try {
    await loadMore();
  } finally {
    isLoading.value = false;
  }
});
</script>

<template>
  <div class="mx-auto w-full max-w-5xl px-4 py-10">
    <h1 class="text-3xl font-bold tracking-tight sm:text-4xl">Блог</h1>
    <p class="mt-2 text-base text-slate-500 dark:text-slate-400">
      Статьи о подготовке к экзаменам, учёбе и занятиях с репетитором.
    </p>

    <p v-if="isLoading" class="mt-8 text-base text-slate-400">Загрузка…</p>
    <p v-else-if="posts.length === 0" class="mt-8 text-base text-slate-400">Пока нет ни одной статьи.</p>

    <div v-else class="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <BlogPostCard v-for="post in posts" :key="post.id" :post="post" />
    </div>

    <div v-if="posts.length < total" class="mt-8 flex justify-center">
      <button type="button" class="btn-outline text-base" :disabled="isLoadingMore" @click="loadMore">
        {{ isLoadingMore ? "Загружаем…" : "Показать ещё" }}
      </button>
    </div>
  </div>
</template>
