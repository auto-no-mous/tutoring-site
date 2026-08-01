<script setup lang="ts">
import { onMounted, ref } from "vue";

import { createHomework, getStudentHomeworkForTutor, setSubmissionStatus } from "@/api/homework";
import type { StudentHomework } from "@/types/homework";
import { formatDateTimeWithMsk } from "@/utils/time";

const props = defineProps<{ studentId: string; studentName: string }>();
const emit = defineEmits<{ close: []; changed: [] }>();

const items = ref<StudentHomework[]>([]);
const isLoading = ref(true);
const showForm = ref(false);

const title = ref("");
const submissionMode = ref<"mark_done" | "file_upload">("mark_done");
const contentUrl = ref("");
const file = ref<File | null>(null);
const error = ref("");

const STATUS_OPTIONS = [
  { value: "pending", label: "Не выполнено" },
  { value: "submitted", label: "Отправлено" },
  { value: "done", label: "Выполнено" },
];

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    items.value = await getStudentHomeworkForTutor(props.studentId);
    showForm.value = items.value.length === 0;
  } finally {
    isLoading.value = false;
  }
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
      student_id: props.studentId,
      content_url: contentUrl.value || undefined,
      file: file.value ?? undefined,
    });
    title.value = "";
    contentUrl.value = "";
    file.value = null;
    showForm.value = false;
    await load();
    emit("changed");
  } catch {
    error.value = "Не удалось создать задание — укажите ссылку или файл (и только один вариант).";
  }
}

async function onStatusChange(item: StudentHomework, event: Event): Promise<void> {
  const status = (event.target as HTMLSelectElement).value;
  await setSubmissionStatus(item.submission_id, status);
  await load();
  emit("changed");
}

onMounted(load);
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="emit('close')">
    <div class="flex max-h-[85vh] w-full max-w-lg flex-col rounded-lg bg-white p-4 shadow-xl dark:bg-slate-900">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-medium">ДЗ · {{ studentName }}</h2>
        <button type="button" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200" @click="emit('close')">✕</button>
      </div>

      <p v-if="isLoading" class="mt-4 text-sm text-slate-400">Загрузка…</p>
      <div v-else class="mt-3 flex flex-1 flex-col gap-3 overflow-y-auto">
        <p v-if="items.length === 0" class="text-sm text-slate-400">Заданий пока нет.</p>
        <div v-for="item in items" :key="item.submission_id" class="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
          <div class="flex items-center justify-between">
            <div class="font-medium">{{ item.title }}</div>
            <select
              :value="item.status"
              class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-xs dark:border-slate-700"
              @change="onStatusChange(item, $event)"
            >
              <option v-for="opt in STATUS_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <div class="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
            <a v-if="item.content_url" :href="item.content_url" target="_blank" class="underline">Материал (ссылка)</a>
            <a v-if="item.content_file_path" :href="item.content_file_path" target="_blank" class="underline">Материал (файл)</a>
            <span v-if="item.due_at">Срок: {{ formatDateTimeWithMsk(item.due_at) }}</span>
          </div>
          <a v-if="item.file_path" :href="item.file_path" target="_blank" class="mt-1 block text-xs underline">
            Файл ученика {{ item.submitted_at ? `(${formatDateTimeWithMsk(item.submitted_at)})` : "" }}
          </a>
          <div v-else-if="item.status !== 'pending'" class="mt-1 text-xs text-slate-400">
            Статус изменён вручную{{ item.submitted_at ? ` · ${formatDateTimeWithMsk(item.submitted_at)}` : "" }}
          </div>
        </div>
      </div>

      <div class="mt-3 border-t border-slate-200 pt-3 dark:border-slate-800">
        <button
          v-if="!showForm"
          type="button"
          class="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
          @click="showForm = true"
        >
          + Новое задание
        </button>
        <form v-else class="flex flex-col gap-2" @submit.prevent="create">
          <label class="flex flex-col gap-1 text-sm">
            Название задания
            <input v-model="title" required class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700" />
          </label>
          <label class="flex flex-col gap-1 text-sm">
            Что должен сделать ученик
            <select v-model="submissionMode" class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700">
              <option value="mark_done">Отметить «выполнено»</option>
              <option value="file_upload">Загрузить файл</option>
            </select>
          </label>
          <label class="flex flex-col gap-1 text-sm">
            Ссылка на материал (или прикрепите файл ниже)
            <input v-model="contentUrl" class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700" />
          </label>
          <input
            type="file"
            class="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700 dark:file:bg-white dark:file:text-slate-900 dark:hover:file:bg-slate-200"
            @change="onFileChange"
          />
          <p v-if="error" class="text-xs text-red-600 dark:text-red-400">{{ error }}</p>
          <div class="flex items-center gap-2">
            <button type="submit" class="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm text-white dark:bg-white dark:text-slate-900">
              Отправить
            </button>
            <button v-if="items.length > 0" type="button" class="text-xs text-slate-500 underline" @click="showForm = false">
              Отмена
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
