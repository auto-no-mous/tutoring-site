<script setup lang="ts">
import { ArrowLeft } from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { getBlogPost } from "@/api/blog";
import type { BlogPost } from "@/types/blog";
import { usePageMeta } from "@/utils/pageMeta";
import { sanitizeRichText } from "@/utils/richText";
import { formatArticleDate } from "@/utils/time";

const route = useRoute();
const slug = route.params.slug as string;

const post = ref<BlogPost | null>(null);
const isLoading = ref(true);
const notFound = ref(false);

// Санитайзер прогоняется ещё раз на рендере, хотя бэкенд уже почистил тело при
// сохранении - та же защита в глубину, что и на анкете репетитора.
const bodyHtml = computed(() => (post.value?.body ? sanitizeRichText(post.value.body) : ""));

usePageMeta(() => ({
  title: post.value?.title,
  description: post.value?.summary,
  jsonLd: post.value
    ? {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: post.value.title,
        description: post.value.summary,
        datePublished: post.value.published_at,
        image: post.value.cover_image_url ? [new URL(post.value.cover_image_url, window.location.origin).href] : undefined,
        author: post.value.author_name ? { "@type": "Person", name: post.value.author_name } : undefined,
      }
    : undefined,
}));

onMounted(async () => {
  try {
    post.value = await getBlogPost(slug);
  } catch {
    notFound.value = true;
  } finally {
    isLoading.value = false;
  }
});
</script>

<template>
  <div class="mx-auto w-full max-w-3xl px-4 py-10">
    <RouterLink to="/blog" class="back-link">
      <ArrowLeft class="h-4 w-4" />
      Все статьи
    </RouterLink>

    <p v-if="isLoading" class="mt-8 text-base text-slate-400">Загрузка…</p>

    <template v-else-if="notFound">
      <h1 class="mt-6 text-3xl font-bold tracking-tight">Статья не найдена</h1>
      <p class="mt-2 text-base text-slate-500 dark:text-slate-400">
        Возможно, её удалили или сняли с публикации.
      </p>
    </template>

    <article v-else-if="post" class="animate-fade-in-up mt-6">
      <img
        v-if="post.cover_image_url"
        :src="post.cover_image_url"
        alt=""
        class="mb-6 max-h-96 w-full rounded-2xl object-cover"
      />
      <h1 class="text-3xl font-bold tracking-tight sm:text-4xl">{{ post.title }}</h1>
      <div class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500 dark:text-slate-400">
        <time v-if="post.published_at" :datetime="post.published_at">{{ formatArticleDate(post.published_at) }}</time>
        <span v-if="post.published_at && post.author_name" aria-hidden="true">·</span>
        <span v-if="post.author_name">{{ post.author_name }}</span>
      </div>
      <!-- flow-root, чтобы обтекаемые картинки (rt-img-left/right) не вылезали за
           пределы статьи - так же, как в блоке «О себе» на анкете репетитора. -->
      <div
        v-if="bodyHtml"
        class="prose-article mt-6 flow-root text-base leading-relaxed text-slate-700 dark:text-slate-300"
        v-html="bodyHtml"
      ></div>
    </article>
  </div>
</template>
