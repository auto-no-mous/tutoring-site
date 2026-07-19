<script setup lang="ts">
import { onMounted, ref } from "vue";

import { listMyGroups } from "@/api/groups";
import { createHomework, deleteAssignment, listMyAssignments, listSubmissions } from "@/api/homework";
import type { Group } from "@/types/group";
import type { HomeworkAssignment, HomeworkSubmission } from "@/types/homework";
import { formatDateTimeWithMsk } from "@/utils/time";

const assignments = ref<HomeworkAssignment[]>([]);
const groups = ref<Group[]>([]);
const submissionsByAssignment = ref<Record<string, HomeworkSubmission[]>>({});

const title = ref("");
const targetType = ref<"student" | "group">("student");
const studentId = ref("");
const groupId = ref("");
const submissionMode = ref<"mark_done" | "file_upload">("mark_done");
const contentUrl = ref("");
const file = ref<File | null>(null);
const error = ref("");

async function load(): Promise<void> {
  const [assignmentsData, groupsData] = await Promise.all([listMyAssignments(), listMyGroups()]);
  assignments.value = assignmentsData;
  groups.value = groupsData;
}

function onFileChange(event: Event): void {
  file.value = (event.target as HTMLInputElement).files?.[0] ?? null;
}

async function create(): Promise<void> {
  error.value = "";
  try {
    await createHomework({
      title: title.value,
      submission_mode: submissionMode.value,
      student_id: targetType.value === "student" ? studentId.value : undefined,
      group_id: targetType.value === "group" ? groupId.value : undefined,
      content_url: contentUrl.value || undefined,
      file: file.value ?? undefined,
    });
    title.value = "";
    contentUrl.value = "";
    studentId.value = "";
    file.value = null;
    await load();
  } catch {
    error.value = "Не удалось создать задание — укажите ссылку или файл (и только один вариант).";
  }
}

async function toggleSubmissions(assignmentId: string): Promise<void> {
  if (submissionsByAssignment.value[assignmentId]) {
    delete submissionsByAssignment.value[assignmentId];
    return;
  }
  submissionsByAssignment.value[assignmentId] = await listSubmissions(assignmentId);
}

async function remove(assignmentId: string): Promise<void> {
  await deleteAssignment(assignmentId);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex max-w-2xl flex-col gap-6">
    <form class="flex flex-col gap-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800" @submit.prevent="create">
      <label class="flex flex-col gap-1 text-sm">
        Название задания
        <input v-model="title" required class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
      </label>
      <div class="flex gap-4 text-sm">
        <label class="flex items-center gap-2"><input v-model="targetType" type="radio" value="student" /> Ученику</label>
        <label class="flex items-center gap-2"><input v-model="targetType" type="radio" value="group" /> Группе</label>
      </div>
      <label v-if="targetType === 'student'" class="flex flex-col gap-1 text-sm">
        ID ученика
        <input v-model="studentId" required class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
      </label>
      <label v-else class="flex flex-col gap-1 text-sm">
        Группа
        <select v-model="groupId" required class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700">
          <option v-for="group in groups" :key="group.id" :value="group.id">{{ group.name }}</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        Что должен сделать ученик
        <select v-model="submissionMode" class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700">
          <option value="mark_done">Отметить «выполнено»</option>
          <option value="file_upload">Загрузить файл</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        Ссылка на материал (или прикрепите файл ниже)
        <input v-model="contentUrl" class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
      </label>
      <input type="file" @change="onFileChange" />
      <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
      <button type="submit" class="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm text-white dark:bg-white dark:text-slate-900">Отправить</button>
    </form>

    <div class="flex flex-col gap-2">
      <div v-for="assignment in assignments" :key="assignment.id" class="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
        <div class="flex items-center justify-between">
          <div>
            <div class="font-medium">{{ assignment.title }}</div>
            <div class="text-slate-500">
              {{ assignment.group_id ? "Группа" : "Ученик" }} ·
              {{ assignment.submission_mode === "mark_done" ? "отметка" : "файл" }}
            </div>
          </div>
          <div class="flex gap-2">
            <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="toggleSubmissions(assignment.id)">
              Сдачи
            </button>
            <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="remove(assignment.id)">
              Удалить
            </button>
          </div>
        </div>
        <div v-if="submissionsByAssignment[assignment.id]" class="mt-2 flex flex-col gap-1 border-t border-slate-200 pt-2 dark:border-slate-800">
          <div v-for="submission in submissionsByAssignment[assignment.id]" :key="submission.id" class="flex items-center justify-between text-xs">
            <span>{{ submission.student_id }}</span>
            <span>
              {{ submission.status }}
              <template v-if="submission.submitted_at"> · {{ formatDateTimeWithMsk(submission.submitted_at) }}</template>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
