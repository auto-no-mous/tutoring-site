<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import {
  acceptGroupApplication,
  addGroupMember,
  deleteGroup,
  listGroupApplications,
  listGroupMembers,
  listGroups,
  listStudents,
  listTutors,
  reassignGroupTutor,
  rejectGroupApplication,
  removeGroupMember,
  updateGroup,
} from "@/api/admin";
import { getPublicLessonTypes } from "@/api/tutors";
import type { Group, GroupApplication, GroupMembership } from "@/types/group";
import type { LessonType, TutorProfile } from "@/types/tutor";
import type { User } from "@/types/user";

const groups = ref<Group[]>([]);
const students = ref<User[]>([]);
const tutors = ref<TutorProfile[]>([]);
const isLoading = ref(true);

const selectedGroupId = ref<string | null>(null);
const applications = ref<GroupApplication[]>([]);
const members = ref<GroupMembership[]>([]);
const addStudentId = ref("");
const error = ref("");

const editName = ref("");
const renameError = ref("");

const reassignTutorId = ref("");
const reassignLessonTypeId = ref("");
const reassignLessonTypes = ref<LessonType[]>([]);
const reassignError = ref("");

const studentNameById = computed(() => {
  const map: Record<string, string> = {};
  for (const s of students.value) map[s.id] = s.display_name;
  return map;
});

const tutorNameById = computed(() => {
  const map: Record<string, string> = {};
  for (const t of tutors.value) map[t.id] = t.display_name ?? "—";
  return map;
});

const availableStudentsToAdd = computed(() => {
  const memberIds = new Set(members.value.filter((m) => m.status === "active").map((m) => m.student_id));
  return students.value.filter((s) => !memberIds.has(s.id));
});

const selectedGroup = computed(() => groups.value.find((g) => g.id === selectedGroupId.value) ?? null);
const reassignableTutors = computed(() => tutors.value.filter((t) => t.id !== selectedGroup.value?.tutor_id));
const pendingApplications = computed(() => applications.value.filter((a) => a.status === "pending"));
const activeMembers = computed(() => members.value.filter((m) => m.status === "active"));

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    [groups.value, students.value, tutors.value] = await Promise.all([listGroups(), listStudents(), listTutors()]);
  } finally {
    isLoading.value = false;
  }
}

async function selectGroup(group: Group): Promise<void> {
  selectedGroupId.value = group.id;
  addStudentId.value = "";
  error.value = "";
  editName.value = group.name;
  renameError.value = "";
  reassignTutorId.value = "";
  reassignLessonTypeId.value = "";
  reassignLessonTypes.value = [];
  reassignError.value = "";
  [applications.value, members.value] = await Promise.all([listGroupApplications(group.id), listGroupMembers(group.id)]);
}

async function refreshSelected(): Promise<void> {
  if (!selectedGroup.value) return;
  const id = selectedGroup.value.id;
  [applications.value, members.value] = await Promise.all([listGroupApplications(id), listGroupMembers(id)]);
}

async function toggleActive(group: Group): Promise<void> {
  await updateGroup(group.id, { is_active: !group.is_active });
  await load();
}

async function remove(group: Group): Promise<void> {
  if (!window.confirm(`Удалить группу «${group.name}» безвозвратно?`)) return;
  if (selectedGroupId.value === group.id) selectedGroupId.value = null;
  await deleteGroup(group.id);
  await load();
}

async function saveName(group: Group): Promise<void> {
  renameError.value = "";
  if (!editName.value.trim()) {
    renameError.value = "Название не может быть пустым";
    return;
  }
  try {
    await updateGroup(group.id, { name: editName.value.trim() });
    await load();
  } catch {
    renameError.value = "Не удалось переименовать группу";
  }
}

watch(reassignTutorId, async (tutorId) => {
  reassignLessonTypeId.value = "";
  reassignLessonTypes.value = [];
  if (!tutorId) return;
  const lessonTypes = await getPublicLessonTypes(tutorId);
  reassignLessonTypes.value = lessonTypes.filter((lt) => lt.format === "group");
});

async function reassignTutor(group: Group): Promise<void> {
  reassignError.value = "";
  if (!reassignTutorId.value || !reassignLessonTypeId.value) return;
  try {
    await reassignGroupTutor(group.id, reassignTutorId.value, reassignLessonTypeId.value);
    reassignTutorId.value = "";
    reassignLessonTypeId.value = "";
    await load();
  } catch {
    reassignError.value = "Не удалось передать группу другому репетитору";
  }
}

async function accept(app: GroupApplication): Promise<void> {
  error.value = "";
  try {
    await acceptGroupApplication(app.group_id, app.id);
    await refreshSelected();
    await load();
  } catch {
    error.value = "Не удалось принять заявку — возможно, в группе нет свободных мест.";
  }
}

async function reject(app: GroupApplication): Promise<void> {
  error.value = "";
  try {
    await rejectGroupApplication(app.group_id, app.id);
    await refreshSelected();
  } catch {
    error.value = "Не удалось отклонить заявку";
  }
}

async function removeMember(member: GroupMembership): Promise<void> {
  error.value = "";
  try {
    await removeGroupMember(member.group_id, member.student_id);
    await refreshSelected();
    await load();
  } catch {
    error.value = "Не удалось исключить ученика";
  }
}

async function addMember(): Promise<void> {
  if (!selectedGroupId.value || !addStudentId.value) return;
  error.value = "";
  try {
    await addGroupMember(selectedGroupId.value, addStudentId.value);
    addStudentId.value = "";
    await refreshSelected();
    await load();
  } catch {
    error.value = "Не удалось добавить — возможно, в группе нет свободных мест.";
  }
}

onMounted(load);
</script>

<template>
  <div class="flex flex-col gap-4">
    <p v-if="isLoading" class="text-sm text-slate-400">Загрузка…</p>
    <div class="flex flex-col gap-2">
      <div
        v-for="group in groups"
        :key="group.id"
        class="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
        :class="selectedGroupId === group.id ? 'border-brand-500 dark:border-brand-400' : 'border-slate-200 dark:border-slate-800'"
      >
        <button type="button" class="text-left" @click="selectGroup(group)">
          <div class="font-medium">
            {{ group.name }}
            <span v-if="!group.is_active" class="ml-1 text-xs text-slate-400">(неактивна)</span>
          </div>
          <div class="text-slate-500">
            Репетитор: {{ tutorNameById[group.tutor_id] ?? "—" }} · Мест занято: {{ group.member_count }}/{{ group.capacity }}
          </div>
        </button>
        <div class="flex shrink-0 gap-2">
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

    <template v-if="selectedGroup">
      <section class="rounded-md border border-slate-200 p-3 dark:border-slate-800">
        <h2 class="text-sm font-medium">Настройки группы</h2>
        <div class="mt-2 flex flex-wrap items-end gap-2">
          <label class="flex flex-col gap-1 text-xs">
            Название
            <input v-model="editName" class="w-64 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700" />
          </label>
          <button
            type="button"
            class="rounded-md bg-brand-500 px-3 py-1.5 text-sm text-white"
            @click="saveName(selectedGroup)"
          >
            Сохранить название
          </button>
        </div>
        <p v-if="renameError" class="mt-1 text-xs text-red-600 dark:text-red-400">{{ renameError }}</p>

        <div class="mt-3 flex flex-wrap items-end gap-2 border-t border-slate-200 pt-3 dark:border-slate-800">
          <label class="flex flex-col gap-1 text-xs">
            Передать группу репетитору
            <select v-model="reassignTutorId" class="w-56 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700">
              <option value="" disabled>Выберите репетитора</option>
              <option v-for="t in reassignableTutors" :key="t.id" :value="t.id">{{ t.display_name }}</option>
            </select>
          </label>
          <label class="flex flex-col gap-1 text-xs">
            Тип занятия у нового репетитора
            <select
              v-model="reassignLessonTypeId"
              :disabled="!reassignTutorId"
              class="w-56 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm disabled:opacity-50 dark:border-slate-700"
            >
              <option value="" disabled>Выберите тип занятия</option>
              <option v-for="lt in reassignLessonTypes" :key="lt.id" :value="lt.id">{{ lt.name }}</option>
            </select>
          </label>
          <button
            type="button"
            :disabled="!reassignTutorId || !reassignLessonTypeId"
            class="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-slate-700"
            @click="reassignTutor(selectedGroup)"
          >
            Передать
          </button>
          <p v-if="reassignTutorId && reassignLessonTypes.length === 0" class="w-full text-xs text-slate-400">
            У этого репетитора нет групповых типов занятий.
          </p>
          <p v-if="reassignError" class="w-full text-xs text-red-600 dark:text-red-400">{{ reassignError }}</p>
        </div>
      </section>

      <section v-if="pendingApplications.length > 0" class="rounded-md border border-slate-200 p-3 dark:border-slate-800">
        <h2 class="text-sm font-medium">Заявки в «{{ selectedGroup.name }}»</h2>
        <div v-for="app in pendingApplications" :key="app.id" class="mt-2 flex items-center justify-between text-sm">
          <span>{{ studentNameById[app.student_id] ?? app.student_id }}</span>
          <div class="flex gap-2">
            <button type="button" class="rounded-md border border-green-300 px-2 py-1 text-xs text-green-700 dark:border-green-800" @click="accept(app)">
              Принять
            </button>
            <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="reject(app)">
              Отклонить
            </button>
          </div>
        </div>
      </section>

      <section class="rounded-md border border-slate-200 p-3 dark:border-slate-800">
        <h2 class="text-sm font-medium">Участники «{{ selectedGroup.name }}»</h2>
        <p v-if="activeMembers.length === 0" class="mt-2 text-sm text-slate-400">Пока никого нет.</p>
        <div v-for="member in activeMembers" :key="member.id" class="mt-2 flex items-center justify-between text-sm">
          <span>{{ studentNameById[member.student_id] ?? member.student_id }}</span>
          <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="removeMember(member)">
            Исключить
          </button>
        </div>

        <div class="mt-3 flex flex-wrap items-end gap-2 border-t border-slate-200 pt-3 dark:border-slate-800">
          <label class="flex flex-col gap-1 text-xs">
            Добавить ученика
            <select v-model="addStudentId" class="w-56 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700">
              <option value="" disabled>Выберите ученика</option>
              <option v-for="s in availableStudentsToAdd" :key="s.id" :value="s.id">{{ s.display_name }}</option>
            </select>
          </label>
          <button
            type="button"
            :disabled="!addStudentId"
            class="rounded-md bg-brand-500 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            @click="addMember"
          >
            Добавить
          </button>
          <p v-if="error" class="w-full text-xs text-red-600 dark:text-red-400">{{ error }}</p>
        </div>
      </section>
    </template>
  </div>
</template>
