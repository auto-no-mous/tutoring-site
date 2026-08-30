<script setup lang="ts">
import { ArrowLeft } from "lucide-vue-next";
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { applyToGroup } from "@/api/groups";
import { getPublicGroups, getPublicProfile } from "@/api/tutors";
import { useAuthStore } from "@/stores/auth";
import { apiErrorMessage } from "@/utils/apiError";
import type { GroupPublic } from "@/types/group";
import type { TutorPublicProfile } from "@/types/tutor";

const route = useRoute();
const auth = useAuthStore();
// May be a UUID or a slug (see backend's get_profile_by_id_or_slug) - resolved to the
// real UUID below once the profile loads, since getPublicGroups only accepts a UUID.
const routeTutorId = route.params.id as string;

const profile = ref<TutorPublicProfile | null>(null);
const groups = ref<GroupPublic[]>([]);
// Группы, в которые заявка ушла прямо сейчас: до перезагрузки страницы сервер о них
// ещё не знает, а кнопку надо погасить сразу.
const justApplied = ref<Record<string, boolean>>({});
const applyError = ref<Record<string, string>>({});
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

// Кнопка гасится заранее, а не после отказа сервера: раньше ученик, уже состоящий в
// группе, жал "Подать заявку", получал 409 - и не видел ничего, потому что ошибку
// никто не показывал. Выглядело как сломанная кнопка.
function applyLabel(group: GroupPublic): string {
  if (group.is_member) return "Вы уже состоите в этой группе";
  if (group.has_pending_application || justApplied.value[group.id]) return "Заявка отправлена";
  return "Подать заявку";
}

function canApply(group: GroupPublic): boolean {
  return !group.is_member && !group.has_pending_application && !justApplied.value[group.id];
}

async function apply(groupId: string): Promise<void> {
  applyError.value = { ...applyError.value, [groupId]: "" };
  try {
    await applyToGroup(groupId);
    justApplied.value = { ...justApplied.value, [groupId]: true };
  } catch (err) {
    // Причину знает сервер (группа неактивна, заявка уже есть) - показываем её,
    // а не оставляем нажатие без ответа.
    applyError.value = {
      ...applyError.value,
      [groupId]: apiErrorMessage(err, "Не удалось подать заявку"),
    };
  }
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
          <template v-if="auth.isAuthenticated && auth.user?.role === 'student'">
            <button
              type="button"
              class="btn-outline mt-3 text-base"
              :disabled="!canApply(group)"
              @click="apply(group.id)"
            >
              {{ applyLabel(group) }}
            </button>
            <p v-if="applyError[group.id]" class="mt-2 text-sm text-red-600 dark:text-red-400">
              {{ applyError[group.id] }}
            </p>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>
