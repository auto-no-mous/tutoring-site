<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter, type LocationQuery } from "vue-router";

import { myMemberships } from "@/api/groups";
import ChatPanel from "@/components/ChatPanel.vue";
import SettingsTab from "@/components/SettingsTab.vue";
import BookingsTabStudent from "@/components/student/BookingsTab.vue";
import GroupsTabStudent from "@/components/student/GroupsTab.vue";
import HomeworkTabStudent from "@/components/student/HomeworkTab.vue";
import StatsTabStudent from "@/components/student/StatsTab.vue";
import BookingsTabTutor from "@/components/tutor/BookingsTab.vue";
import GroupsTabTutor from "@/components/tutor/GroupsTab.vue";
import HomeworkTabTutor from "@/components/tutor/HomeworkTab.vue";
import ProfileTab from "@/components/tutor/ProfileTab.vue";
import ScheduleTab from "@/components/tutor/ScheduleTab.vue";
import StatsTabTutor from "@/components/tutor/StatsTab.vue";
import { useAuthStore } from "@/stores/auth";
import { useNotificationsStore } from "@/stores/notifications";

const auth = useAuthStore();
const notifications = useNotificationsStore();
const route = useRoute();
const router = useRouter();

const tutorTabs = [
  { key: "bookings", label: "Занятия" },
  { key: "schedule", label: "Расписание" },
  { key: "groups", label: "Группы" },
  { key: "homework", label: "Домашние задания" },
  { key: "chat", label: "Чат" },
  { key: "profile", label: "Профиль" },
  { key: "stats", label: "Статистика" },
  { key: "settings", label: "Настройки" },
];

// A student's "Группы" tab only makes sense once they're (or were) actually in a
// group - see loadGroupHistory below. Hidden by default until that check resolves.
const hasGroupHistory = ref(false);

const studentTabs = computed(() => [
  { key: "bookings", label: "Занятия" },
  ...(hasGroupHistory.value ? [{ key: "groups", label: "Группы" }] : []),
  { key: "homework", label: "Домашние задания" },
  { key: "chat", label: "Чат" },
  { key: "stats", label: "Статистика" },
  { key: "settings", label: "Настройки" },
]);

const tabs = computed(() => (auth.user?.role === "tutor" ? tutorTabs : studentTabs.value));

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

// Обратная сторона: выбранная вкладка должна попадать в адрес. Пока её держало
// только состояние компонента, обновление страницы возвращало на ту вкладку, с
// которой в кабинет вошли по ссылке из меню (?tab=chat), а не на текущую.
// replace, а не push: переключение вкладок - это не переход по страницам, и кнопка
// "назад" должна возвращать туда, откуда пришли в кабинет, а не перебирать вкладки.
watch(activeTab, (tab) => {
  if (route.query.tab === tab) return;
  const query: LocationQuery = { ...route.query, tab };
  // Ссылка на конкретный диалог имеет смысл только вместе с чатом: на другой
  // вкладке она ни на что не влияет, а при возврате в чат открыла бы старый тред.
  if (tab !== "chat") delete query.thread;
  router.replace({ query });
});

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

async function loadGroupHistory(): Promise<void> {
  if (auth.user?.role !== "student") return;
  const memberships = await myMemberships();
  hasGroupHistory.value = memberships.length > 0;
  // A ?tab=groups deep link may only become valid once history is known - re-resolve
  // it now that the tab list can include "groups".
  if (route.query.tab === "groups" && hasGroupHistory.value) {
    activeTab.value = "groups";
  }
}

// Lets other tabs (tutor/GroupsTab.vue's "написать" / "чат группы" buttons) deep-link
// straight into a specific chat thread - see ChatPanel.vue's initialThreadId prop.
const chatThreadId = computed(() => (typeof route.query.thread === "string" ? route.query.thread : null));

onMounted(loadGroupHistory);
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
        class="rounded-t-lg px-3 py-2 text-sm transition-colors hover:text-brand-700 dark:hover:text-brand-300"
        :class="
          activeTab === tab.key
            ? 'border-b-2 border-brand-500 font-semibold text-brand-700 dark:border-brand-400 dark:text-brand-300'
            : 'text-slate-500'
        "
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span
          v-if="tab.key === 'chat' && notifications.total > 0"
          class="ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-medium text-white"
        >
          {{ notifications.total > 9 ? "9+" : notifications.total }}
        </span>
      </button>
    </nav>

    <Transition name="fade" mode="out-in">
      <div :key="activeTab" class="mt-6">
        <template v-if="auth.user?.role === 'tutor'">
          <ProfileTab v-if="activeTab === 'profile'" />
          <ScheduleTab v-else-if="activeTab === 'schedule'" />
          <BookingsTabTutor v-else-if="activeTab === 'bookings'" />
          <GroupsTabTutor v-else-if="activeTab === 'groups'" />
          <HomeworkTabTutor v-else-if="activeTab === 'homework'" />
          <ChatPanel v-else-if="activeTab === 'chat'" :initial-thread-id="chatThreadId" />
          <StatsTabTutor v-else-if="activeTab === 'stats'" />
          <SettingsTab v-else-if="activeTab === 'settings'" />
        </template>
        <template v-else>
          <BookingsTabStudent v-if="activeTab === 'bookings'" />
          <GroupsTabStudent v-else-if="activeTab === 'groups'" />
          <HomeworkTabStudent v-else-if="activeTab === 'homework'" />
          <ChatPanel v-else-if="activeTab === 'chat'" :initial-thread-id="chatThreadId" />
          <StatsTabStudent v-else-if="activeTab === 'stats'" />
          <SettingsTab v-else-if="activeTab === 'settings'" />
        </template>
      </div>
    </Transition>
  </div>
</template>
