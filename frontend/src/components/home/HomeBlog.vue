<script setup lang="ts">
import { onMounted, ref } from "vue";

import { listBlogPosts } from "@/api/blog";
import BlogPostCard from "@/components/blog/BlogPostCard.vue";
import type { BlogPostListItem } from "@/types/blog";

const HOME_POSTS = 3;

const posts = ref<BlogPostListItem[]>([]);
const total = ref(0);

onMounted(async () => {
  // Пустой или упавший блог не должен ломать главную - секция просто не отрисуется.
  try {
    const page = await listBlogPosts({ page: 1, page_size: HOME_POSTS });
    posts.value = page.items;
    total.value = page.total;
  } catch {
    posts.value = [];
  }
});
</script>

<template>
  <section v-if="posts.length > 0" class="mx-auto w-full max-w-5xl px-4 pt-16">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Полезные статьи</h2>
        <p class="mt-1.5 text-base text-slate-500 dark:text-slate-400">
          Разбираем подготовку к экзаменам, учёбу и то, как заниматься эффективнее.
        </p>
      </div>
      <RouterLink
        v-if="total > posts.length"
        to="/blog"
        class="text-base font-medium text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
      >
        Все статьи →
      </RouterLink>
    </div>
    <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <BlogPostCard v-for="post in posts" :key="post.id" :post="post" />
    </div>
  </section>
</template>
