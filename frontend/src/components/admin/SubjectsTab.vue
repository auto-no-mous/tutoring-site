<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  createDirection,
  createSubject,
  deleteDirection,
  deleteSubject,
  listSubjectsAdmin,
  updateDirection,
  updateSubject,
} from "@/api/admin";
import type { Subject } from "@/types/subject";

const subjects = ref<Subject[]>([]);
const newSubjectName = ref("");
const newDirectionName = ref<Record<string, string>>({});
const editingSubjectId = ref<string | null>(null);
const editingSubjectName = ref("");
const editingDirectionId = ref<string | null>(null);
const editingDirectionName = ref("");
const error = ref("");

async function load(): Promise<void> {
  subjects.value = await listSubjectsAdmin();
}

async function addSubject(): Promise<void> {
  error.value = "";
  if (!newSubjectName.value.trim()) return;
  try {
    await createSubject(newSubjectName.value.trim());
    newSubjectName.value = "";
    await load();
  } catch {
    error.value = "Такой предмет уже существует.";
  }
}

function startEditSubject(subject: Subject): void {
  editingSubjectId.value = subject.id;
  editingSubjectName.value = subject.name;
}

async function saveSubject(subject: Subject): Promise<void> {
  await updateSubject(subject.id, editingSubjectName.value);
  editingSubjectId.value = null;
  await load();
}

async function removeSubject(subject: Subject): Promise<void> {
  if (!window.confirm(`Удалить предмет «${subject.name}» вместе со всеми направлениями?`)) return;
  await deleteSubject(subject.id);
  await load();
}

async function addDirection(subject: Subject): Promise<void> {
  error.value = "";
  const name = (newDirectionName.value[subject.id] ?? "").trim();
  if (!name) return;
  try {
    await createDirection(subject.id, name);
    newDirectionName.value[subject.id] = "";
    await load();
  } catch {
    error.value = "Такое направление уже есть у этого предмета.";
  }
}

function startEditDirection(directionId: string, currentName: string): void {
  editingDirectionId.value = directionId;
  editingDirectionName.value = currentName;
}

async function saveDirection(directionId: string): Promise<void> {
  await updateDirection(directionId, editingDirectionName.value);
  editingDirectionId.value = null;
  await load();
}

async function removeDirection(directionId: string): Promise<void> {
  if (!window.confirm("Удалить направление?")) return;
  await deleteDirection(directionId);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex max-w-2xl flex-col gap-6">
    <form class="flex items-end gap-2 rounded-lg border border-slate-200 p-4 dark:border-slate-800" @submit.prevent="addSubject">
      <label class="flex flex-1 flex-col gap-1 text-sm">
        Новый предмет
        <input v-model="newSubjectName" placeholder="например, Математика" class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
      </label>
      <button type="submit" class="rounded-md bg-brand-500 px-3 py-1.5 text-sm text-white">Добавить</button>
    </form>
    <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>

    <div class="flex flex-col gap-4">
      <div v-for="subject in subjects" :key="subject.id" class="rounded-md border border-slate-200 p-3 dark:border-slate-800">
        <div class="flex items-center justify-between">
          <template v-if="editingSubjectId === subject.id">
            <div class="flex flex-1 items-center gap-2">
              <input v-model="editingSubjectName" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700" />
              <button type="button" class="rounded-md bg-brand-500 px-2 py-1 text-xs text-white" @click="saveSubject(subject)">
                Сохранить
              </button>
              <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="editingSubjectId = null">
                Отмена
              </button>
            </div>
          </template>
          <template v-else>
            <div class="font-medium">{{ subject.name }}</div>
            <div class="flex gap-2">
              <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="startEditSubject(subject)">
                Изменить
              </button>
              <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="removeSubject(subject)">
                Удалить
              </button>
            </div>
          </template>
        </div>

        <div class="mt-3 flex flex-col gap-1.5 pl-3">
          <div v-for="direction in subject.directions" :key="direction.id" class="flex items-center justify-between text-sm">
            <template v-if="editingDirectionId === direction.id">
              <div class="flex flex-1 items-center gap-2">
                <input v-model="editingDirectionName" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-xs dark:border-slate-700" />
                <button type="button" class="rounded-md bg-brand-500 px-2 py-0.5 text-xs text-white" @click="saveDirection(direction.id)">
                  Сохранить
                </button>
                <button type="button" class="rounded-md border border-slate-300 px-2 py-0.5 text-xs dark:border-slate-700" @click="editingDirectionId = null">
                  Отмена
                </button>
              </div>
            </template>
            <template v-else>
              <span class="text-slate-600 dark:text-slate-300">{{ direction.name }}</span>
              <div class="flex gap-2">
                <button type="button" class="text-xs text-slate-500 underline" @click="startEditDirection(direction.id, direction.name)">
                  Изменить
                </button>
                <button type="button" class="text-xs text-red-600 underline dark:text-red-400" @click="removeDirection(direction.id)">
                  Удалить
                </button>
              </div>
            </template>
          </div>
          <p v-if="subject.directions.length === 0" class="text-xs text-slate-400">Направлений пока нет.</p>

          <form class="mt-1 flex items-end gap-2" @submit.prevent="addDirection(subject)">
            <input
              v-model="newDirectionName[subject.id]"
              placeholder="Новое направление"
              class="flex-1 rounded-md border border-slate-300 bg-transparent px-2 py-1 text-xs dark:border-slate-700"
            />
            <button type="submit" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700">+ направление</button>
          </form>
        </div>
      </div>
      <p v-if="subjects.length === 0" class="text-sm text-slate-400">Предметов пока нет.</p>
    </div>
  </div>
</template>
