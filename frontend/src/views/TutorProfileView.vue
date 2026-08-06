<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { openThreadWithTutor } from "@/api/chat";
import { getPublicProfile, getReviews } from "@/api/tutors";
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

async function openChat(): Promise<void> {
  if (!profile.value) return;
  const thread = await openThreadWithTutor(profile.value.id);
  await router.push({ path: "/cabinet", query: { tab: "chat", thread: thread.id } });
}

onMounted(load);
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
    <p v-if="isLoading" class="text-slate-400">Загрузка…</p>
    <template v-else-if="profile">
      <div class="flex flex-col items-center text-center">
        <img
          v-if="profile.photo_url"
          :src="profile.photo_url"
          alt=""
          class="aspect-[3/4] w-[30vw] min-w-40 max-w-sm rounded-lg object-cover"
        />
        <div v-else class="aspect-[3/4] w-[30vw] min-w-40 max-w-sm rounded-lg bg-slate-200 dark:bg-slate-800"></div>
        <h1 class="mt-4 text-2xl font-semibold">{{ profile.display_name }}</h1>
        <p v-if="profile.avg_rating != null" class="mt-1 text-sm text-slate-500">
          ★ {{ profile.avg_rating.toFixed(1) }} ({{ profile.reviews_count }} отзывов)
        </p>
        <div
          v-if="profile.show_individual_booking || profile.show_group_booking || auth.user?.role === 'student'"
          class="mt-4 flex flex-wrap justify-center gap-3"
        >
          <RouterLink
            v-if="profile.show_individual_booking"
            :to="`/tutors/${profile.id}/book`"
            class="rounded-md bg-slate-900 px-4 py-2 text-sm text-white dark:bg-white dark:text-slate-900"
          >
            Запись на индивидуальное занятие
          </RouterLink>
          <RouterLink
            v-if="profile.show_group_booking"
            :to="`/tutors/${profile.id}/groups`"
            class="rounded-md border border-slate-300 px-4 py-2 text-sm dark:border-slate-700"
          >
            Запись на групповое занятие
          </RouterLink>
          <button
            v-if="auth.user?.role === 'student'"
            type="button"
            class="rounded-md border border-slate-300 px-4 py-2 text-sm dark:border-slate-700"
            @click="openChat"
          >
            Написать сообщение
          </button>
        </div>
      </div>

      <section v-if="profile.subjects.length > 0" class="mt-6">
        <h2 class="text-lg font-medium">Предметы и направления</h2>
        <div class="mt-2 flex flex-col gap-1.5">
          <div v-for="subject in profile.subjects" :key="subject.subject_id" class="text-sm">
            <span class="font-medium">{{ subject.subject_name }}</span>
            <span v-if="subject.directions.length > 0" class="text-slate-500">
              — {{ subject.directions.map((d) => d.name).join(", ") }}
            </span>
          </div>
        </div>
      </section>

      <section class="mt-6">
        <h2 class="text-lg font-medium">О себе</h2>
        <div v-if="aboutHtml" class="mt-1 flow-root text-sm text-slate-600 dark:text-slate-300" v-html="aboutHtml"></div>
        <p v-else class="mt-1 text-sm text-slate-600 dark:text-slate-300">—</p>
      </section>

      <section v-if="reviews.length > 0" class="mt-8">
        <h2 class="text-lg font-medium">Отзывы</h2>
        <div class="mt-2 flex flex-col gap-3">
          <div v-for="review in reviews" :key="review.id" class="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
            <div class="font-medium">{{ review.student_display_name }} · ★ {{ review.rating }}</div>
            <p v-if="review.text" class="mt-1 text-slate-600 dark:text-slate-300">{{ review.text }}</p>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
