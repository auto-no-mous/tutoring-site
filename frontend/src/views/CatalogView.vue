<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { listSubjects } from "@/api/subjects";
import { getCatalog } from "@/api/tutors";
import type { Subject } from "@/types/subject";
import type { TutorCatalogItem } from "@/types/tutor";

const router = useRouter();

const PAGE_SIZE = 20;
const PRICE_STEPS = [500, 750, 1000, 1500, 2000, 2500, 3000];
// "Цена от": каждый пункт, плюс верхний открытый порог.
const MIN_OPTIONS = [...PRICE_STEPS.map((v) => ({ label: `${v} ₽`, value: v })), { label: "более 3000 ₽", value: 3000.01 }];
// "Цена до": нижний открытый порог, плюс каждый пункт.
const MAX_OPTIONS = [{ label: "менее 500 ₽", value: 499.99 }, ...PRICE_STEPS.map((v) => ({ label: `${v} ₽`, value: v }))];

const tutors = ref<TutorCatalogItem[]>([]);
const total = ref(0);
const page = ref(0);
const subjects = ref<Subject[]>([]);
const subjectId = ref("");
const priceMin = ref("");
const priceMax = ref("");
const isLoading = ref(false);
const isLoadingMore = ref(false);
const sentinel = ref<HTMLElement | null>(null);
const showFilters = ref(false);

let observer: IntersectionObserver | null = null;

function hasMore(): boolean {
  // page 0 means we haven't fetched anything yet - always allow that first fetch,
  // since tutors.length < total (0 < 0) would otherwise be false and loadMore()
  // would exit before ever making a request.
  return page.value === 0 || tutors.value.length < total.value;
}

async function loadMore(): Promise<void> {
  if (isLoading.value || isLoadingMore.value || !hasMore()) return;
  isLoadingMore.value = true;
  try {
    const result = await getCatalog({
      subject_id: subjectId.value || undefined,
      price_min: priceMin.value ? Number(priceMin.value) : undefined,
      price_max: priceMax.value ? Number(priceMax.value) : undefined,
      page: page.value + 1,
      page_size: PAGE_SIZE,
    });
    tutors.value.push(...result.items);
    total.value = result.total;
    page.value = result.page;
  } finally {
    isLoadingMore.value = false;
  }
}

async function search(): Promise<void> {
  isLoading.value = true;
  tutors.value = [];
  total.value = 0;
  page.value = 0;
  try {
    await loadMore();
  } finally {
    isLoading.value = false;
  }
}

// Results update the moment a filter changes - no separate "Найти" button. Not
// `immediate`, so this doesn't double up with the explicit search() in onMounted.
watch([subjectId, priceMin, priceMax], search);

// The card itself is a RouterLink to the tutor's profile; this button sits inside it
// for a direct shortcut to booking, so its click must not also trigger the card's
// own navigation.
function goToBooking(tutorId: string, event: MouseEvent): void {
  event.preventDefault();
  event.stopPropagation();
  router.push(`/tutors/${tutorId}/book`);
}

onMounted(async () => {
  subjects.value = await listSubjects();
  await search();

  observer = new IntersectionObserver((entries) => {
    if (entries[0]?.isIntersecting) loadMore();
  });
  if (sentinel.value) observer.observe(sentinel.value);
});

onBeforeUnmount(() => {
  observer?.disconnect();
});
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
    <h1 class="text-2xl font-semibold">Каталог репетиторов</h1>

    <div class="mt-6">
      <button
        type="button"
        class="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
        @click="showFilters = !showFilters"
      >
        {{ showFilters ? "Скрыть фильтры" : "Фильтры" }}
      </button>
      <div v-if="showFilters" class="mt-3 flex flex-wrap gap-3">
        <select
          v-model="subjectId"
          class="min-w-48 flex-1 rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-700"
        >
          <option value="">Все предметы</option>
          <option v-for="subject in subjects" :key="subject.id" :value="subject.id">{{ subject.name }}</option>
        </select>
        <select v-model="priceMin" class="w-40 rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-700">
          <option value="">Цена от</option>
          <option v-for="opt in MIN_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <select v-model="priceMax" class="w-40 rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-700">
          <option value="">Цена до</option>
          <option v-for="opt in MAX_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
    </div>

    <p v-if="isLoading" class="mt-8 text-slate-400">Загрузка…</p>
    <p v-else-if="tutors.length === 0" class="mt-8 text-slate-400">Репетиторы не найдены.</p>

    <div v-else class="mt-8 flex flex-col gap-4">
      <RouterLink
        v-for="tutor in tutors"
        :key="tutor.id"
        :to="`/tutors/${tutor.slug ?? tutor.id}`"
        class="flex gap-5 rounded-lg border border-slate-200 p-5 transition-transform duration-150 ease-out hover:z-10 hover:scale-[1.02] hover:border-slate-400 hover:shadow-lg dark:border-slate-800 dark:hover:border-slate-600"
      >
        <img v-if="tutor.photo_url" :src="tutor.photo_url" alt="" class="h-28 w-28 shrink-0 rounded-md object-cover" />
        <div v-else class="h-28 w-28 shrink-0 rounded-md bg-slate-200 dark:bg-slate-800"></div>
        <div class="flex-1">
          <div class="text-lg font-medium">{{ tutor.name_patronymic }}</div>
          <div v-if="tutor.hourly_price != null" class="mt-1 text-sm text-slate-500">
            от {{ tutor.hourly_price }} ₽/час
          </div>
          <div v-if="tutor.avg_rating != null" class="mt-1 text-sm text-slate-500">
            ★ {{ tutor.avg_rating.toFixed(1) }} ({{ tutor.reviews_count }} отзывов)
          </div>
          <div v-if="tutor.subjects.length > 0" class="mt-2 flex flex-wrap gap-1.5">
            <span
              v-for="subjectName in tutor.subjects"
              :key="subjectName"
              class="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300"
            >
              {{ subjectName }}
            </span>
          </div>
          <p v-if="tutor.about_snippet" class="mt-2 text-sm text-slate-600 dark:text-slate-300">{{ tutor.about_snippet }}</p>
          <button
            v-if="tutor.show_individual_booking"
            type="button"
            class="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-xs text-white dark:bg-white dark:text-slate-900"
            @click="goToBooking(tutor.id, $event)"
          >
            Запись на индивидуальное занятие
          </button>
        </div>
      </RouterLink>
    </div>

    <!-- Sentinel: as soon as this scrolls into view, the IntersectionObserver loads
    the next page. Kept mounted (not v-if) even after everything's loaded so the
    observer stays attached to a stable element - hasMore() inside loadMore() is what
    actually stops further requests once total is reached. -->
    <div ref="sentinel" class="mt-4 h-px"></div>
    <p v-if="isLoadingMore" class="text-center text-sm text-slate-400">Загружаем ещё…</p>
  </div>
</template>
