<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { leaveGroup, myApplications, myMemberships } from "@/api/groups";
import type { GroupApplication, GroupMembership } from "@/types/group";

// myMemberships() returns every status (see CabinetView.vue's tab-visibility check,
// which needs past memberships too) - this tab itself only ever displays active ones.
const memberships = ref<GroupMembership[]>([]);
const activeMemberships = computed(() => memberships.value.filter((m) => m.status === "active"));
const applications = ref<GroupApplication[]>([]);

async function load(): Promise<void> {
  [memberships.value, applications.value] = await Promise.all([myMemberships(), myApplications()]);
}

async function leave(membership: GroupMembership): Promise<void> {
  if (!window.confirm("Отказаться от участия в группе? Это освободит место.")) return;
  await leaveGroup(membership.group_id);
  await load();
}

const statusLabels: Record<string, string> = { pending: "на рассмотрении", accepted: "принята", rejected: "отклонена" };

onMounted(load);
</script>

<template>
  <div class="flex max-w-xl flex-col gap-6">
    <section>
      <h2 class="text-lg font-medium">Мои группы</h2>
      <p v-if="activeMemberships.length === 0" class="mt-2 text-sm text-slate-400">Вы пока не состоите в группах.</p>
      <div v-for="membership in activeMemberships" :key="membership.id" class="mt-2 flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
        <span>Группа «{{ membership.group_name }}» у преподавателя {{ membership.tutor_display_name }}</span>
        <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="leave(membership)">
          Покинуть
        </button>
      </div>
    </section>

    <section>
      <h2 class="text-lg font-medium">Мои заявки</h2>
      <p v-if="applications.length === 0" class="mt-2 text-sm text-slate-400">Заявок пока нет.</p>
      <div v-for="app in applications" :key="app.id" class="mt-2 flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
        <span>Группа «{{ app.group_name }}» у преподавателя {{ app.tutor_display_name }}</span>
        <span class="text-slate-500">{{ statusLabels[app.status] ?? app.status }}</span>
      </div>
    </section>
  </div>
</template>
