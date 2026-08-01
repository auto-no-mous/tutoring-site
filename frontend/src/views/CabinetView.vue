<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import ChatPanel from "@/components/ChatPanel.vue";
import SettingsTab from "@/components/SettingsTab.vue";
import BookingsTabStudent from "@/components/student/BookingsTab.vue";
import GroupsTabStudent from "@/components/student/GroupsTab.vue";
import HomeworkTabStudent from "@/components/student/HomeworkTab.vue";
import StatsTabStudent from "@/components/student/StatsTab.vue";
import BookingsTabTutor from "@/components/tutor/BookingsTab.vue";
import GroupsTabTutor from "@/components/tutor/GroupsTab.vue";
import HomeworkTabTutor from "@/components/tutor/HomeworkTab.vue";
import LessonTypesTab from "@/components/tutor/LessonTypesTab.vue";
import ProfileTab from "@/components/tutor/ProfileTab.vue";
import ScheduleTab from "@/components/tutor/ScheduleTab.vue";
import StatsTabTutor from "@/components/tutor/StatsTab.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const route = useRoute();

const tutorTabs = [
  { key: "bookings", label: "Занятия" },
  { key: "profile", label: "Профиль" },
  { key: "lesson-types", label: "Типы занятий" },
  { key: "schedule", label: "Расписание" },
  { key: "groups", label: "Группы" },
  { key: "homework", label: "Домашние задания" },
  { key: "chat", label: "Чат" },
  { key: "stats", label: "Статистика" },
  { key: "settings", label: "Настройки" },
];

const studentTabs = [
  { key: "bookings", label: "Занятия" },
  { key: "groups", label: "Группы" },
  { key: "homework", label: "Домашние задания" },
  { key: "chat", label: "Чат" },
  { key: "stats", label: "Статистика" },
  { key: "settings", label: "Настройки" },
];

const tabs = computed(() => (auth.user?.role === "tutor" ? tutorTabs : studentTabs));

function initialTab(): string {
  const queryTab = route.query.tab;
  if (typeof queryTab === "string" && tabs.value.some((t) => t.key === queryTab)) return queryTab;
  return tabs.value[0]?.key ?? "bookings";
}

const activeTab = ref(initialTab());

// Lets header links (components/UserMenu.vue) navigate straight to a tab via
// /cabinet?tab=... even when already on this page (e.g. switching from "Занятия" to
// "Настройки" through the menu, not just on first load).
watch(
  () => route.query.tab,
  (queryTab) => {
    if (typeof queryTab === "string" && tabs.value.some((t) => t.key === queryTab)) {
      activeTab.value = queryTab;
    }
  },
);

// Section-specific short name format: students show Фамилия + Имя (no patronymic),
// tutors show Имя + Отчество (no surname, matches the catalog card format).
const shortName = computed(() => {
  const user = auth.user;
  if (!user) return "";
  if (user.role === "tutor") {
    return user.patronymic ? `${user.first_name} ${user.patronymic}` : user.first_name;
  }
  return `${user.last_name} ${user.first_name}`.trim();
});
</script>

<template>
  <div class="mx-auto max-w-5xl px-4 py-10">
    <h1 class="text-2xl font-semibold">Личный кабинет</h1>
    <p class="mt-1 text-sm text-slate-500">
      {{ shortName }} · {{ auth.user?.role === "tutor" ? "Репетитор" : "Ученик" }}
    </p>

    <nav class="mt-6 flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="rounded-t-md px-3 py-2 text-sm"
        :class="activeTab === tab.key ? 'border-b-2 border-slate-900 font-medium dark:border-white' : 'text-slate-500'"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <div class="mt-6">
      <template v-if="auth.user?.role === 'tutor'">
        <ProfileTab v-if="activeTab === 'profile'" />
        <LessonTypesTab v-else-if="activeTab === 'lesson-types'" />
        <ScheduleTab v-else-if="activeTab === 'schedule'" />
        <BookingsTabTutor v-else-if="activeTab === 'bookings'" />
        <GroupsTabTutor v-else-if="activeTab === 'groups'" />
        <HomeworkTabTutor v-else-if="activeTab === 'homework'" />
        <ChatPanel v-else-if="activeTab === 'chat'" />
        <StatsTabTutor v-else-if="activeTab === 'stats'" />
        <SettingsTab v-else-if="activeTab === 'settings'" />
      </template>
      <template v-else>
        <BookingsTabStudent v-if="activeTab === 'bookings'" />
        <GroupsTabStudent v-else-if="activeTab === 'groups'" />
        <HomeworkTabStudent v-else-if="activeTab === 'homework'" />
        <ChatPanel v-else-if="activeTab === 'chat'" />
        <StatsTabStudent v-else-if="activeTab === 'stats'" />
        <SettingsTab v-else-if="activeTab === 'settings'" />
      </template>
    </div>
  </div>
</template>
