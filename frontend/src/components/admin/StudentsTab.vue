<script setup lang="ts">
import axios from "axios";
import { onMounted, ref } from "vue";

import { deleteStudent, listStudents, updateStudent } from "@/api/admin";
import ResetPasswordButton from "@/components/admin/ResetPasswordButton.vue";
import type { User } from "@/types/user";

const students = ref<User[]>([]);
const editingId = ref<string | null>(null);

const editLastName = ref("");
const editFirstName = ref("");
const editPatronymic = ref("");
const editEmail = ref("");
const editGrade = ref<number | null>(null);
const editTimezone = ref("");
const error = ref("");

async function load(): Promise<void> {
  students.value = await listStudents();
}

function startEdit(student: User): void {
  editingId.value = student.id;
  editLastName.value = student.last_name;
  editFirstName.value = student.first_name;
  editPatronymic.value = student.patronymic ?? "";
  editEmail.value = student.email ?? "";
  editGrade.value = student.grade;
  editTimezone.value = student.timezone;
  error.value = "";
}

function cancelEdit(): void {
  editingId.value = null;
}

async function saveEdit(student: User): Promise<void> {
  error.value = "";
  try {
    await updateStudent(student.id, {
      last_name: editLastName.value,
      first_name: editFirstName.value,
      patronymic: editPatronymic.value || null,
      email: editEmail.value || undefined,
      grade: editGrade.value,
      timezone: editTimezone.value,
    });
    editingId.value = null;
    await load();
  } catch (err) {
    error.value =
      axios.isAxiosError(err) && err.response?.status === 409 ? "Эта почта уже используется другим аккаунтом" : "Не удалось сохранить";
  }
}

async function toggleActive(student: User): Promise<void> {
  await updateStudent(student.id, { is_active: !student.is_active });
  await load();
}

async function remove(student: User): Promise<void> {
  if (!window.confirm(`Удалить ученика «${student.display_name}» безвозвратно?`)) return;
  await deleteStudent(student.id);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex flex-col gap-2">
    <div v-for="student in students" :key="student.id" class="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
      <template v-if="editingId === student.id">
        <div class="flex flex-col gap-3">
          <div class="flex flex-wrap gap-2">
            <label class="flex flex-col gap-1 text-xs">
              Фамилия
              <input v-model="editLastName" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Имя
              <input v-model="editFirstName" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Отчество
              <input v-model="editPatronymic" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Почта
              <input v-model="editEmail" type="email" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Класс
              <select v-model.number="editGrade" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700">
                <option :value="null">—</option>
                <option v-for="n in 11" :key="n" :value="n">{{ n }}-й класс</option>
              </select>
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Часовой пояс
              <input v-model="editTimezone" placeholder="Europe/Moscow" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
          </div>

          <p v-if="error" class="text-xs text-red-600 dark:text-red-400">{{ error }}</p>
          <div class="flex gap-2">
            <button type="button" class="rounded-md bg-brand-500 px-3 py-1.5 text-xs text-white" @click="saveEdit(student)">
              Сохранить
            </button>
            <button type="button" class="rounded-md border border-slate-300 px-3 py-1.5 text-xs dark:border-slate-700" @click="cancelEdit">
              Отмена
            </button>
          </div>
        </div>
      </template>
      <div v-else class="flex items-center justify-between">
        <div>
          <div class="font-medium">
            {{ student.display_name }}
            <span v-if="!student.is_active" class="ml-1 text-xs text-red-600 dark:text-red-400">(заблокирован)</span>
            <span v-if="student.grade" class="ml-1 text-xs text-slate-400">({{ student.grade }}-й класс)</span>
          </div>
          <div class="text-slate-500">
            {{ student.email }}
            <span
              v-if="!student.email_verified"
              class="ml-1 text-xs text-amber-600 dark:text-amber-400"
              title="Пользователь не переходил по ссылке из письма подтверждения"
              >почта не подтверждена</span
            >
          </div>
        </div>
        <div class="flex gap-2">
          <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="startEdit(student)">
            Изменить
          </button>
          <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="toggleActive(student)">
            {{ student.is_active ? "Заблокировать" : "Разблокировать" }}
          </button>
          <ResetPasswordButton :user-id="student.id" :display-name="student.display_name" />
          <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="remove(student)">
            Удалить
          </button>
        </div>
      </div>
    </div>
    <p v-if="students.length === 0" class="text-sm text-slate-400">Учеников пока нет.</p>
  </div>
</template>
