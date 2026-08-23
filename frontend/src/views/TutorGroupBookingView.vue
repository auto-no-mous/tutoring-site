<script setup lang="ts">
import { ArrowLeft } from "lucide-vue-next";
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { applyToGroup } from "@/api/groups";
import { getPublicGroups, getPublicProfile } from "@/api/tutors";
import { useAuthStore } from "@/stores/auth";
import type { GroupPublic } from "@/types/group";
import type { TutorPublicProfile } from "@/types/tutor";

const route = useRoute();
const auth = useAuthStore();
// May be a UUID or a slug (see backend's get_profile_by_id_or_slug) - resolved to the
// real UUID below once the profile loads, since getPublicGroups only accepts a UUID.
const routeTutorId = route.params.id as string;

const profile = ref<TutorPublicProfile | null>(null);
const groups = ref<GroupPublic[]>([]);
const applyStatus = ref<Record<string, string>>({});
const isLoading = ref(true);

const weekdayNames = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    const profileData = await getPublicProfile(routeTutorId);
    profile.value = profileData;
    groups.value = await getPublicGroups(profileData.id);
  } finally {
    isLoading.value = false;
  }
}

async function apply(groupId: string): Promise<void> {
  await applyToGroup(groupId);
  applyStatus.value[groupId] = "Заявка отправлена";
}

onMounted(load);
</script>

<template>
  <div class="mx-auto max-w-2xl px-4 py-10">
    <RouterLink :to="`/tutors/${routeTutorId}`" class="back-link"><ArrowLeft class="h-4 w-4" />Анкета репетитора</RouterLink>
    <p v-if="isLoading" class="mt-4 text-base text-slate-400">Загрузка…</p>
    <template v-else-if="profile">
      <h1 class="mt-3 text-3xl font-bold tracking-tight">
        Группы подготовки — <span class="text-brand-600 dark:text-brand-400">{{ profile.display_name }}</span>
      </h1>
      <p v-if="groups.length === 0" class="mt-6 text-base text-slate-400">У этого репетитора пока нет открытых групп.</p>
      <div v-else class="mt-6 flex flex-col gap-3">
        <div
          v-for="group in groups"
          :key="group.id"
          class="surface-card animate-fade-in-up p-4 text-base transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
        >
          <div class="text-lg font-semibold">{{ group.name }}</div>
          <div class="mt-1 text-slate-500 dark:text-slate-400">
            <span class="font-medium text-brand-700 dark:text-brand-300">{{ group.price }} ₽/место</span>
            · {{ group.duration_minutes }} мин · мест: {{ group.member_count }}/{{ group.capacity }}
          </div>
          <div class="text-slate-500 dark:text-slate-400">
            {{ group.schedule_slots.map((s) => `${weekdayNames[s.weekday]} ${s.start_time.slice(0, 5)}`).join(", ") }}
          </div>
          <button
            v-if="auth.isAuthenticated && auth.user?.role === 'student'"
            type="button"
            class="btn-outline mt-3 text-base"
            :disabled="!!applyStatus[group.id]"
            @click="apply(group.id)"
          >
            {{ applyStatus[group.id] ?? "Подать заявку" }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
