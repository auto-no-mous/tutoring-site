<script setup lang="ts">
import { computed, ref } from "vue";

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
const activeTab = ref(tabs.value[0]?.key ?? "bookings");
</script>

<template>
  <div class="mx-auto max-w-5xl px-4 py-10">
    <h1 class="text-2xl font-semibold">Личный кабинет</h1>
    <p class="mt-1 text-sm text-slate-500">
      {{ auth.user?.display_name }} · {{ auth.user?.role === "tutor" ? "Репетитор" : "Ученик" }}
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
