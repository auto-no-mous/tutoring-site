<script setup lang="ts">
import { ref } from "vue";

import BookingsTab from "@/components/admin/BookingsTab.vue";
import GroupsTab from "@/components/admin/GroupsTab.vue";
import StudentsTab from "@/components/admin/StudentsTab.vue";
import SubjectsTab from "@/components/admin/SubjectsTab.vue";
import TutorsTab from "@/components/admin/TutorsTab.vue";

const tabs = [
  { key: "tutors", label: "Репетиторы" },
  { key: "students", label: "Ученики" },
  { key: "bookings", label: "Занятия" },
  { key: "groups", label: "Группы" },
  { key: "subjects", label: "Предметы" },
];

const activeTab = ref(tabs[0].key);
</script>

<template>
  <div class="mx-auto max-w-5xl px-4 py-10">
    <h1 class="text-2xl font-semibold">Админка</h1>
    <p class="mt-1 text-sm text-slate-500">Полный доступ ко всей системе.</p>

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
      <TutorsTab v-if="activeTab === 'tutors'" />
      <StudentsTab v-else-if="activeTab === 'students'" />
      <BookingsTab v-else-if="activeTab === 'bookings'" />
      <GroupsTab v-else-if="activeTab === 'groups'" />
      <SubjectsTab v-else-if="activeTab === 'subjects'" />
    </div>
  </div>
</template>
