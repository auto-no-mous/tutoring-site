<script setup lang="ts">
import { ChevronDown, SlidersHorizontal, Star } from "lucide-vue-next";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { listSubjects } from "@/api/subjects";
import { getCatalog } from "@/api/tutors";
import ForTutorsNote from "@/components/home/ForTutorsNote.vue";
import HomeBlog from "@/components/home/HomeBlog.vue";
import HomeFaq from "@/components/home/HomeFaq.vue";
import HomeHero from "@/components/home/HomeHero.vue";
import HowItWorks from "@/components/home/HowItWorks.vue";
import PlatformFeatures from "@/components/home/PlatformFeatures.vue";
import SubjectTiles from "@/components/home/SubjectTiles.vue";
import type { CatalogSubject } from "@/types/subject";
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
const subjects = ref<CatalogSubject[]>([]);
const subjectId = ref("");
const priceMin = ref("");
const priceMax = ref("");
const isLoading = ref(false);
const isLoadingMore = ref(false);
const sentinel = ref<HTMLElement | null>(null);
const catalogSection = ref<HTMLElement | null>(null);
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

function scrollToCatalog(): void {
  const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  catalogSection.value?.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
}

// Плитка предмета - это тот же фильтр, что и в панели фильтров. Раскрываем панель,
// иначе выбранный предмет нигде не виден и снять фильтр неоткуда.
function onSubjectTileSelect(id: string): void {
  subjectId.value = id;
  showFilters.value = true;
  scrollToCatalog();
}

// The card itself is a RouterLink to the tutor's profile; these buttons sit inside it
// as direct shortcuts to booking, so their clicks must not also trigger the card's
// own navigation.
function goToBooking(tutorId: string, event: MouseEvent, format: "individual" | "group" = "individual"): void {
  event.preventDefault();
  event.stopPropagation();
  router.push(format === "group" ? `/tutors/${tutorId}/groups` : `/tutors/${tutorId}/book`);
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
  <div class="pb-16">
    <HomeHero @find-tutor="scrollToCatalog" />

    <SubjectTiles :subjects="subjects" :selected-id="subjectId" @select="onSubjectTileSelect" />

    <!-- scroll-mt компенсирует липкую шапку, когда сюда скроллят из хиро или с плиток. -->
    <!-- max-w-5xl - как у остальных секций главной (хиро, плитки предметов, «Как это
         работает», «Что внутри платформы»): каталог стоит с ними в одной колонке, и
         более узкая рамка бросалась в глаза как ошибка вёрстки. -->
    <section ref="catalogSection" class="mx-auto w-full max-w-5xl scroll-mt-20 px-4 pt-16">
      <h2 class="text-2xl font-semibold tracking-tight">Каталог репетиторов</h2>
      <p class="mt-1.5 text-base text-slate-500 dark:text-slate-400">
        Выберите преподавателя и запишитесь на занятие в пару кликов.
      </p>

      <div class="mt-6">
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white/70 px-3.5 py-2 text-base font-medium transition-colors hover:border-brand-400 hover:text-brand-700 dark:border-slate-700 dark:bg-transparent dark:hover:border-brand-500 dark:hover:text-brand-300"
          @click="showFilters = !showFilters"
        >
          <SlidersHorizontal class="h-4 w-4" />
          Фильтры
          <ChevronDown class="h-4 w-4 transition-transform duration-300" :class="{ 'rotate-180': showFilters }" />
        </button>
        <Transition name="collapse">
          <div v-if="showFilters">
            <div class="collapse-inner">
              <div class="mt-3 flex flex-wrap gap-3">
                <select v-model="subjectId" class="filter-select min-w-48 flex-1">
                  <option value="">Все предметы</option>
                  <option v-for="subject in subjects" :key="subject.id" :value="subject.id">{{ subject.name }}</option>
                </select>
                <select v-model="priceMin" class="filter-select w-40">
                  <option value="">Цена от</option>
                  <option v-for="opt in MIN_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
                <select v-model="priceMax" class="filter-select w-40">
                  <option value="">Цена до</option>
                  <option v-for="opt in MAX_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <p v-if="isLoading" class="mt-8 text-base text-slate-400">Загрузка…</p>
      <p v-else-if="tutors.length === 0" class="mt-8 text-base text-slate-400">Репетиторы не найдены.</p>

      <!-- Сетка в одну колонку, а не flex-колонка: auto-rows-fr выравнивает все
           карточки по высоте самой содержательной, так что список выглядит ровным
           независимо от длины описания и наличия кнопок записи. -->
      <TransitionGroup v-else name="list" tag="div" class="relative mt-8 grid auto-rows-fr grid-cols-1 gap-4">
        <RouterLink
          v-for="(tutor, index) in tutors"
          :key="tutor.id"
          :to="`/tutors/${tutor.slug ?? tutor.id}`"
          :style="{ '--stagger': `${(index % PAGE_SIZE) * 35}ms` }"
          class="surface-card flex h-full min-h-36 gap-5 p-5 transition-all duration-200 ease-out hover:z-10 hover:-translate-y-1 hover:border-brand-300 hover:shadow-lg dark:hover:border-brand-700"
        >
          <!-- Фото занимает всю высоту карточки, но не участвует в её вычислении:
               растягивается обёртка (self-stretch), а сама картинка позиционирована
               абсолютно, поэтому её собственные пропорции больше не могут раздуть
               карточку по вертикали - как это было, когда img стоял здесь напрямую.
               Высоту задаёт текстовая колонка, object-cover обрезает, а не растягивает.
               max-h-44 только до sm: на узком экране текст переносится, карточка
               становится высокой, и фото при своей ширине выродилось бы в полосу. -->
          <div
            class="relative max-h-44 w-28 shrink-0 self-stretch overflow-hidden rounded-xl bg-brand-50 ring-2 ring-brand-100 sm:max-h-none sm:w-36 dark:bg-slate-800 dark:ring-brand-900/50"
          >
            <img
              v-if="tutor.photo_url"
              :src="tutor.photo_url"
              alt=""
              class="absolute inset-0 h-full w-full object-cover"
            />
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-xl font-semibold">{{ tutor.name_patronymic }}</div>
            <div v-if="tutor.hourly_price != null" class="mt-1 text-base font-medium text-brand-700 dark:text-brand-300">
              от {{ tutor.hourly_price }} ₽/час
            </div>
            <div v-if="tutor.avg_rating != null" class="mt-1 flex items-center gap-1 text-base text-slate-500 dark:text-slate-400">
              <Star class="h-4 w-4 fill-aqua-400 text-aqua-400" />
              {{ tutor.avg_rating.toFixed(1) }} ({{ tutor.reviews_count }} отзывов)
            </div>
            <div v-if="tutor.subjects.length > 0" class="mt-2 flex flex-wrap gap-1.5">
              <span
                v-for="subjectName in tutor.subjects"
                :key="subjectName"
                class="rounded-full bg-brand-50 px-3 py-1 text-sm font-medium text-brand-800 dark:bg-brand-900/40 dark:text-brand-200"
              >
                {{ subjectName }}
              </span>
            </div>
            <!-- Бэкенд обрезает описание до 140 символов, но в узкой колонке они
                 занимают разное число строк; line-clamp держит карточки одинаковыми. -->
            <p
              v-if="tutor.about_snippet"
              class="mt-2 line-clamp-2 text-base leading-relaxed text-slate-600 dark:text-slate-300"
            >
              {{ tutor.about_snippet }}
            </p>
            <!-- Обе кнопки-ярлыка ведут туда же, куда кнопки на самом профиле
                 (TutorProfileView), и подчиняются тем же флагам с бэкенда. -->
            <div
              v-if="tutor.show_individual_booking || tutor.show_group_booking"
              class="mt-3 flex flex-wrap gap-2"
            >
              <button
                v-if="tutor.show_individual_booking"
                type="button"
                class="btn-primary px-3.5 py-1.5 text-sm"
                @click="goToBooking(tutor.id, $event)"
              >
                Запись на индивидуальное занятие
              </button>
              <button
                v-if="tutor.show_group_booking"
                type="button"
                class="btn-outline px-3.5 py-1.5 text-sm"
                @click="goToBooking(tutor.id, $event, 'group')"
              >
                Запись на групповое занятие
              </button>
            </div>
          </div>
        </RouterLink>
      </TransitionGroup>

      <!-- Sentinel: as soon as this scrolls into view, the IntersectionObserver loads
      the next page. Kept mounted (not v-if) even after everything's loaded so the
      observer stays attached to a stable element - hasMore() inside loadMore() is what
      actually stops further requests once total is reached. -->
      <div ref="sentinel" class="mt-4 h-px"></div>
      <p v-if="isLoadingMore" class="text-center text-base text-slate-400">Загружаем ещё…</p>
    </section>

    <HowItWorks />
    <PlatformFeatures />
    <ForTutorsNote />
    <HomeBlog />
    <HomeFaq />
  </div>
</template>
