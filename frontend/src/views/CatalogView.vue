<script setup lang="ts">
import { onMounted, ref } from "vue";

import { listSubjects } from "@/api/subjects";
import { getCatalog } from "@/api/tutors";
import type { Subject } from "@/types/subject";
import type { TutorCatalogItem } from "@/types/tutor";

const PRICE_STEPS = [500, 750, 1000, 1500, 2000, 2500, 3000];
// "Цена от": каждый пункт, плюс верхний открытый порог.
const MIN_OPTIONS = [...PRICE_STEPS.map((v) => ({ label: `${v} ₽`, value: v })), { label: "более 3000 ₽", value: 3000.01 }];
// "Цена до": нижний открытый порог, плюс каждый пункт.
const MAX_OPTIONS = [{ label: "менее 500 ₽", value: 499.99 }, ...PRICE_STEPS.map((v) => ({ label: `${v} ₽`, value: v }))];

const tutors = ref<TutorCatalogItem[]>([]);
const subjects = ref<Subject[]>([]);
const subjectId = ref("");
const priceMin = ref("");
const priceMax = ref("");
const isLoading = ref(false);

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    tutors.value = await getCatalog({
      subject_id: subjectId.value || undefined,
      price_min: priceMin.value ? Number(priceMin.value) : undefined,
      price_max: priceMax.value ? Number(priceMax.value) : undefined,
    });
  } finally {
    isLoading.value = false;
  }
}

onMounted(async () => {
  subjects.value = await listSubjects();
  await load();
});
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
    <h1 class="text-2xl font-semibold">Каталог репетиторов</h1>

    <form class="mt-6 flex flex-wrap gap-3" @submit.prevent="load">
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
      <button type="submit" class="rounded-md bg-slate-900 px-4 py-2 text-sm text-white dark:bg-white dark:text-slate-900">
        Найти
      </button>
    </form>

    <p v-if="isLoading" class="mt-8 text-slate-400">Загрузка…</p>
    <p v-else-if="tutors.length === 0" class="mt-8 text-slate-400">Репетиторы не найдены.</p>

    <div v-else class="mt-8 flex flex-col gap-4">
      <RouterLink
        v-for="tutor in tutors"
        :key="tutor.id"
        :to="`/tutors/${tutor.id}`"
        class="flex gap-5 rounded-lg border border-slate-200 p-5 hover:border-slate-400 dark:border-slate-800 dark:hover:border-slate-600"
      >
        <img v-if="tutor.photo_url" :src="tutor.photo_url" alt="" class="h-28 w-28 shrink-0 rounded-full object-cover" />
        <div v-else class="h-28 w-28 shrink-0 rounded-full bg-slate-200 dark:bg-slate-800"></div>
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
        </div>
      </RouterLink>
    </div>
  </div>
</template>
