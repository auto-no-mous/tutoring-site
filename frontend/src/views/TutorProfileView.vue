<script setup lang="ts">
import { CalendarPlus, MessageCircle, Star, Users } from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { openThreadWithTutor } from "@/api/chat";
import { getPublicProfile, getReviews } from "@/api/tutors";
import SocialLinks from "@/components/tutor/SocialLinks.vue";
import { useAuthStore } from "@/stores/auth";
import { sanitizeRichText } from "@/utils/richText";
import type { TutorPublicProfile } from "@/types/tutor";
import type { Review } from "@/types/stats";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const tutorId = route.params.id as string;

const profile = ref<TutorPublicProfile | null>(null);
const reviews = ref<Review[]>([]);
const isLoading = ref(true);

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    // route param may be a UUID or a slug (see backend's get_profile_by_id_or_slug) -
    // resolve the profile first, then use its real id for the sub-resource call
    // below, which only accepts a UUID.
    const profileData = await getPublicProfile(tutorId);
    profile.value = profileData;
    reviews.value = await getReviews(profileData.id);
  } finally {
    isLoading.value = false;
  }
}

const aboutHtml = computed(() => (profile.value?.about ? sanitizeRichText(profile.value.about) : ""));

const hasSocialLinks = computed(
  () =>
    !!profile.value &&
    (!!profile.value.telegram_url ||
      !!profile.value.vk_url ||
      !!profile.value.youtube_url ||
      profile.value.extra_links.length > 0),
);

async function openChat(): Promise<void> {
  if (!profile.value) return;
  const thread = await openThreadWithTutor(profile.value.id);
  await router.push({ path: "/cabinet", query: { tab: "chat", thread: thread.id } });
}

onMounted(load);
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
    <p v-if="isLoading" class="text-base text-slate-400">Загрузка…</p>
    <template v-else-if="profile">
      <div class="surface-card animate-fade-in-up p-5 sm:p-6">
        <div class="flex flex-col gap-5 sm:flex-row sm:items-start">
          <img
            v-if="profile.photo_url"
            :src="profile.photo_url"
            alt=""
            class="h-32 w-32 shrink-0 self-center rounded-2xl object-cover ring-4 ring-brand-100 dark:ring-brand-900/50 sm:h-36 sm:w-36 sm:self-start"
          />
          <div
            v-else
            class="h-32 w-32 shrink-0 self-center rounded-2xl bg-brand-50 ring-4 ring-brand-100 dark:bg-slate-800 dark:ring-brand-900/50 sm:h-36 sm:w-36 sm:self-start"
          ></div>
          <div class="flex flex-1 flex-col items-center text-center sm:items-start sm:text-left">
            <h1 class="text-3xl font-bold tracking-tight">{{ profile.display_name }}</h1>
            <p
              v-if="profile.avg_rating != null"
              class="mt-2 inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1 text-base font-medium text-brand-800 dark:bg-brand-900/40 dark:text-brand-200"
            >
              <Star class="h-4 w-4 fill-aqua-400 text-aqua-400" /> {{ profile.avg_rating.toFixed(1) }}
              <span class="font-normal text-slate-500 dark:text-slate-400">({{ profile.reviews_count }} отзывов)</span>
            </p>
            <SocialLinks
              v-if="hasSocialLinks"
              class="mt-3 justify-center sm:justify-start"
              :telegram-url="profile.telegram_url"
              :vk-url="profile.vk_url"
              :youtube-url="profile.youtube_url"
              :extra-links="profile.extra_links"
            />
            <div
              v-if="profile.show_individual_booking || profile.show_group_booking || auth.user?.role === 'student'"
              class="mt-5 flex flex-wrap justify-center gap-3 sm:justify-start"
            >
              <RouterLink v-if="profile.show_individual_booking" :to="`/tutors/${profile.id}/book`" class="btn-primary text-base">
                <CalendarPlus class="h-4 w-4" />
                Запись на индивидуальное занятие
              </RouterLink>
              <RouterLink v-if="profile.show_group_booking" :to="`/tutors/${profile.id}/groups`" class="btn-outline text-base">
                <Users class="h-4 w-4" />
                Запись на групповое занятие
              </RouterLink>
              <button v-if="auth.user?.role === 'student'" type="button" class="btn-outline text-base" @click="openChat">
                <MessageCircle class="h-4 w-4" />
                Написать сообщение
              </button>
            </div>
          </div>
        </div>
      </div>

      <section v-if="profile.subjects.length > 0" class="surface-card animate-fade-in-up mt-5 p-5 [animation-delay:60ms]">
        <h2 class="text-xl font-semibold">Предметы и направления</h2>
        <div class="mt-3 flex flex-col gap-2">
          <div v-for="subject in profile.subjects" :key="subject.subject_id" class="text-base">
            <span class="font-semibold">{{ subject.subject_name }}</span>
            <span v-if="subject.directions.length > 0" class="text-slate-500 dark:text-slate-400">
              — {{ subject.directions.map((d) => d.name).join(", ") }}
            </span>
          </div>
        </div>
      </section>

      <section class="surface-card animate-fade-in-up mt-5 p-5 [animation-delay:120ms]">
        <h2 class="text-xl font-semibold">О себе</h2>
        <div
          v-if="aboutHtml"
          class="mt-2 flow-root text-base leading-relaxed text-slate-600 dark:text-slate-300"
          v-html="aboutHtml"
        ></div>
        <p v-else class="mt-2 text-base text-slate-600 dark:text-slate-300">—</p>
      </section>

      <!-- Ссылку разбирает бэкенд (app/utils/video.py) и отдаёт готовый адрес
           плеера, так что сюда попадает только YouTube/RuTube/VK Видео. Обёртка
           с aspect-video держит пропорции 16:9 на любой ширине. -->
      <section v-if="profile.video_embed_url" class="surface-card animate-fade-in-up mt-5 p-5 [animation-delay:150ms]">
        <h2 class="text-xl font-semibold">Видео</h2>
        <div class="mt-2 aspect-video w-full overflow-hidden rounded-lg bg-slate-100 dark:bg-slate-800">
          <iframe
            :src="profile.video_embed_url"
            :title="`Видео репетитора ${profile.display_name}`"
            class="h-full w-full"
            frameborder="0"
            loading="lazy"
            referrerpolicy="strict-origin-when-cross-origin"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen"
            allowfullscreen
          ></iframe>
        </div>
      </section>

      <section v-if="reviews.length > 0" class="mt-8">
        <h2 class="text-xl font-semibold">Отзывы</h2>
        <div class="mt-3 flex flex-col gap-3">
          <div
            v-for="review in reviews"
            :key="review.id"
            class="surface-card animate-fade-in-up p-4 text-base transition-shadow hover:shadow-md"
          >
            <div class="flex items-center gap-1.5 font-semibold">
              {{ review.student_display_name }} ·
              <Star class="h-4 w-4 fill-aqua-400 text-aqua-400" />
              {{ review.rating }}
            </div>
            <p v-if="review.text" class="mt-1 leading-relaxed text-slate-600 dark:text-slate-300">{{ review.text }}</p>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
