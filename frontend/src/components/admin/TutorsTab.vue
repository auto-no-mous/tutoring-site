<script setup lang="ts">
import { onMounted, ref } from "vue";

import { deleteTutor, listTutors, updateTutor } from "@/api/admin";
import type { TutorProfile } from "@/types/tutor";

const tutors = ref<TutorProfile[]>([]);
const editingId = ref<string | null>(null);
const editFirstName = ref("");
const editLastName = ref("");
const editAbout = ref("");

async function load(): Promise<void> {
  tutors.value = await listTutors();
}

function startEdit(tutor: TutorProfile): void {
  editingId.value = tutor.id;
  editFirstName.value = "";
  editLastName.value = "";
  editAbout.value = tutor.about;
}

function cancelEdit(): void {
  editingId.value = null;
}

async function saveEdit(tutor: TutorProfile): Promise<void> {
  await updateTutor(tutor.id, {
    first_name: editFirstName.value || undefined,
    last_name: editLastName.value || undefined,
    about: editAbout.value,
  });
  editingId.value = null;
  await load();
}

async function toggleActive(tutor: TutorProfile): Promise<void> {
  await updateTutor(tutor.id, { is_active: !tutor.is_active });
  await load();
}

async function remove(tutor: TutorProfile): Promise<void> {
  if (!window.confirm(`Удалить репетитора «${tutor.display_name}» безвозвратно?`)) return;
  await deleteTutor(tutor.id);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex flex-col gap-2">
    <div v-for="tutor in tutors" :key="tutor.id" class="rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
      <template v-if="editingId === tutor.id">
        <div class="flex flex-wrap items-end gap-2">
          <label class="flex flex-col gap-1 text-xs">
            Фамилия
            <input v-model="editLastName" :placeholder="tutor.display_name ?? ''" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
          </label>
          <label class="flex flex-col gap-1 text-xs">
            Имя
            <input v-model="editFirstName" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
          </label>
          <label class="flex flex-col gap-1 text-xs">
            О себе
            <input v-model="editAbout" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
          </label>
          <button type="button" class="rounded-md bg-slate-900 px-2 py-1 text-xs text-white dark:bg-white dark:text-slate-900" @click="saveEdit(tutor)">
            Сохранить
          </button>
          <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="cancelEdit">
            Отмена
          </button>
        </div>
      </template>
      <div v-else class="flex items-center justify-between">
        <div>
          <div class="font-medium">
            {{ tutor.display_name }}
            <span v-if="tutor.is_active === false" class="ml-1 text-xs text-red-600 dark:text-red-400">(заблокирован)</span>
            <span v-if="tutor.is_hidden" class="ml-1 text-xs text-slate-400">(скрыт из каталога)</span>
          </div>
          <div class="text-slate-500">{{ tutor.about || "—" }}</div>
        </div>
        <div class="flex gap-2">
          <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="startEdit(tutor)">
            Изменить
          </button>
          <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="toggleActive(tutor)">
            {{ tutor.is_active === false ? "Разблокировать" : "Заблокировать" }}
          </button>
          <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="remove(tutor)">
            Удалить
          </button>
        </div>
      </div>
    </div>
    <p v-if="tutors.length === 0" class="text-sm text-slate-400">Репетиторов пока нет.</p>
  </div>
</template>
