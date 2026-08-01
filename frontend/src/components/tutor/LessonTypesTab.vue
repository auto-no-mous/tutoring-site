<script setup lang="ts">
import { onMounted, ref } from "vue";

import { createLessonType, deleteLessonType, getMyLessonTypes, updateLessonType } from "@/api/tutors";
import type { LessonType } from "@/types/tutor";

const types = ref<LessonType[]>([]);
const name = ref("");
const format = ref<"individual" | "group">("individual");
const duration = ref(60);
const price = ref(1000);
const error = ref("");

const editingId = ref<string | null>(null);
const editName = ref("");
const editDuration = ref(60);
const editPrice = ref(0);
const editError = ref("");

const isAdding = ref(false);

async function load(): Promise<void> {
  types.value = await getMyLessonTypes();
}

function openAdd(): void {
  name.value = "";
  format.value = "individual";
  duration.value = 60;
  price.value = 1000;
  error.value = "";
  isAdding.value = true;
}

function cancelAdd(): void {
  isAdding.value = false;
  error.value = "";
}

async function create(): Promise<void> {
  error.value = "";
  try {
    await createLessonType({ name: name.value, format: format.value, duration_minutes: duration.value, price: price.value });
    isAdding.value = false;
    await load();
  } catch {
    error.value = "Не удалось создать тип занятия (длительность должна быть кратна шагу сетки расписания).";
  }
}

function startEdit(type: LessonType): void {
  editingId.value = type.id;
  editName.value = type.name;
  editDuration.value = type.duration_minutes;
  editPrice.value = type.price;
  editError.value = "";
}

function cancelEdit(): void {
  editingId.value = null;
  editError.value = "";
}

async function saveEdit(type: LessonType): Promise<void> {
  editError.value = "";
  try {
    await updateLessonType(type.id, {
      name: editName.value,
      duration_minutes: editDuration.value,
      price: editPrice.value,
    });
    editingId.value = null;
    await load();
  } catch {
    editError.value = "Не удалось сохранить (длительность должна быть кратна шагу сетки расписания).";
  }
}

async function toggleActive(type: LessonType): Promise<void> {
  await updateLessonType(type.id, { is_active: !type.is_active });
  await load();
}

async function remove(type: LessonType): Promise<void> {
  await deleteLessonType(type.id);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex max-w-xl flex-col gap-6">
    <div class="flex flex-col gap-2">
      <div v-for="type in types" :key="type.id" class="rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
        <template v-if="editingId === type.id">
          <div class="flex flex-wrap items-end gap-2">
            <label class="flex flex-col gap-1 text-xs">
              Название
              <input v-model="editName" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Длительность, мин
              <input v-model.number="editDuration" type="number" min="1" class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Цена, ₽
              <input v-model.number="editPrice" type="number" min="0" class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <button type="button" class="rounded-md bg-slate-900 px-2 py-1 text-xs text-white dark:bg-white dark:text-slate-900" @click="saveEdit(type)">
              Сохранить
            </button>
            <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="cancelEdit">
              Отмена
            </button>
          </div>
          <p v-if="editError" class="mt-1 text-xs text-red-600 dark:text-red-400">{{ editError }}</p>
        </template>
        <div v-else class="flex items-center justify-between">
          <div>
            <div class="font-medium">{{ type.name }} <span class="text-slate-400">({{ type.format === "individual" ? "инд." : "групп." }})</span></div>
            <div class="text-slate-500">{{ type.duration_minutes }} мин · {{ type.price }} ₽ · {{ type.is_active ? "активен" : "выключен" }}</div>
          </div>
          <div class="flex gap-2">
            <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="startEdit(type)">
              Изменить
            </button>
            <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="toggleActive(type)">
              {{ type.is_active ? "Выключить" : "Включить" }}
            </button>
            <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="remove(type)">
              Удалить
            </button>
          </div>
        </div>
      </div>
    </div>

    <button
      v-if="!isAdding"
      type="button"
      class="w-fit rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
      @click="openAdd"
    >
      Добавить +
    </button>

    <form v-else class="flex flex-wrap items-end gap-2 rounded-lg border border-slate-200 p-4 dark:border-slate-800" @submit.prevent="create">
      <label class="flex flex-col gap-1 text-sm">
        Название
        <input v-model="name" required class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        Формат
        <select v-model="format" class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700">
          <option value="individual">Индивидуальное</option>
          <option value="group">Групповое</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        Длительность, мин
        <input v-model.number="duration" type="number" min="1" class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        Цена, ₽
        <input v-model.number="price" type="number" min="0" class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
      </label>
      <button type="submit" class="rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white dark:bg-white dark:text-slate-900">Сохранить</button>
      <button type="button" class="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700" @click="cancelAdd">Отмена</button>
      <p v-if="error" class="w-full text-sm text-red-600 dark:text-red-400">{{ error }}</p>
    </form>
  </div>
</template>
