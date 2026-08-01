<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { getPublicLessonTypes, getPublicProfile } from "@/api/tutors";
import BookingWizard from "@/components/BookingWizard.vue";
import type { LessonType, TutorPublicProfile } from "@/types/tutor";

const route = useRoute();
// May be a UUID or a slug (see backend's get_profile_by_id_or_slug) - resolved to the
// real UUID below once the profile loads, since everything downstream (lesson types,
// the booking wizard's availability/booking calls) only accepts a UUID.
const routeTutorId = route.params.id as string;

const profile = ref<TutorPublicProfile | null>(null);
const lessonTypes = ref<LessonType[]>([]);
const isLoading = ref(true);

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    const profileData = await getPublicProfile(routeTutorId);
    profile.value = profileData;
    lessonTypes.value = await getPublicLessonTypes(profileData.id);
  } finally {
    isLoading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="mx-auto max-w-2xl px-4 py-10">
    <RouterLink :to="`/tutors/${routeTutorId}`" class="text-sm text-slate-500 hover:underline">← Анкета репетитора</RouterLink>
    <p v-if="isLoading" class="mt-4 text-slate-400">Загрузка…</p>
    <template v-else-if="profile">
      <h1 class="mt-2 text-2xl font-semibold">Запись к репетитору {{ profile.display_name }}</h1>
      <div class="mt-6">
        <BookingWizard :tutor-id="profile.id" :tutor-name="profile.display_name" :lesson-types="lessonTypes" />
      </div>
    </template>
  </div>
</template>
