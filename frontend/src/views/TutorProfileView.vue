<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { applyToGroup } from "@/api/groups";
import { getPublicGroups, getPublicProfile, getReviews } from "@/api/tutors";
import { useAuthStore } from "@/stores/auth";
import { sanitizeRichText } from "@/utils/richText";
import type { GroupPublic } from "@/types/group";
import type { TutorPublicProfile } from "@/types/tutor";
import type { Review } from "@/types/stats";

const route = useRoute();
const auth = useAuthStore();
const tutorId = route.params.id as string;

const profile = ref<TutorPublicProfile | null>(null);
const groups = ref<GroupPublic[]>([]);
const reviews = ref<Review[]>([]);
const applyStatus = ref<Record<string, string>>({});
const isLoading = ref(true);

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    // route param may be a UUID or a slug (see backend's get_profile_by_id_or_slug) -
    // resolve the profile first, then use its real id for the sub-resource calls
    // below, which only accept a UUID.
    const profileData = await getPublicProfile(tutorId);
    profile.value = profileData;
    const [groupsData, reviewsData] = await Promise.all([getPublicGroups(profileData.id), getReviews(profileData.id)]);
    groups.value = groupsData;
    reviews.value = reviewsData;
  } finally {
    isLoading.value = false;
  }
}

async function apply(groupId: string): Promise<void> {
  await applyToGroup(groupId);
  applyStatus.value[groupId] = "Заявка отправлена";
}

const weekdayNames = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

const aboutHtml = computed(() => (profile.value?.about ? sanitizeRichText(profile.value.about) : ""));

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
        <RouterLink
          :to="`/tutors/${profile.id}/book`"
          class="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm text-white dark:bg-white dark:text-slate-900"
        >
          Записаться на занятие
        </RouterLink>
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

      <section v-if="groups.length > 0" class="mt-8">
        <h2 class="text-lg font-medium">Группы подготовки</h2>
        <div class="mt-2 flex flex-col gap-2">
          <div v-for="group in groups" :key="group.id" class="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
            <div class="font-medium">{{ group.name }}</div>
            <div class="text-slate-500">
              {{ group.price }} ₽/место · {{ group.duration_minutes }} мин · мест: {{ group.member_count }}/{{ group.capacity }}
            </div>
            <div class="text-slate-500">
              {{ group.schedule_slots.map((s) => `${weekdayNames[s.weekday]} ${s.start_time.slice(0, 5)}`).join(", ") }}
            </div>
            <button
              v-if="auth.isAuthenticated && auth.user?.role === 'student'"
              type="button"
              class="mt-2 rounded-md border border-slate-300 px-3 py-1 text-xs dark:border-slate-700"
              :disabled="!!applyStatus[group.id]"
              @click="apply(group.id)"
            >
              {{ applyStatus[group.id] ?? "Подать заявку" }}
            </button>
          </div>
        </div>
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
