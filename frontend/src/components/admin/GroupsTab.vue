<script setup lang="ts">
import { onMounted, ref } from "vue";

import { deleteGroup, listGroups, updateGroup } from "@/api/admin";
import type { Group } from "@/types/group";

const groups = ref<Group[]>([]);
const isLoading = ref(true);

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    groups.value = await listGroups();
  } finally {
    isLoading.value = false;
  }
}

async function toggleActive(group: Group): Promise<void> {
  await updateGroup(group.id, { is_active: !group.is_active });
  await load();
}

async function remove(group: Group): Promise<void> {
  if (!window.confirm(`Удалить группу «${group.name}» безвозвратно?`)) return;
  await deleteGroup(group.id);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex flex-col gap-2">
    <p v-if="isLoading" class="text-sm text-slate-400">Загрузка…</p>
    <div v-for="group in groups" :key="group.id" class="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
      <div>
        <div class="font-medium">
          {{ group.name }}
          <span v-if="!group.is_active" class="ml-1 text-xs text-slate-400">(неактивна)</span>
        </div>
        <div class="text-slate-500">Мест: {{ group.member_count }}/{{ group.capacity }}</div>
      </div>
      <div class="flex gap-2">
        <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="toggleActive(group)">
          {{ group.is_active ? "Деактивировать" : "Активировать" }}
        </button>
        <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="remove(group)">
          Удалить
        </button>
      </div>
    </div>
    <p v-if="!isLoading && groups.length === 0" class="text-sm text-slate-400">Групп пока нет.</p>
  </div>
</template>
