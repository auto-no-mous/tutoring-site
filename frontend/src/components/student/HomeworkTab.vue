<script setup lang="ts">
import { onMounted, ref } from "vue";

import { deleteSubmissionFile, markDone, myHomework, uploadSubmission } from "@/api/homework";
import FileDropZone from "@/components/FileDropZone.vue";
import HomeworkFiles from "@/components/homework/HomeworkFiles.vue";
import { useNotificationsStore } from "@/stores/notifications";
import type { StudentHomework } from "@/types/homework";
import { apiErrorMessage } from "@/utils/apiError";
import { homeworkCardClass, homeworkStatusLabel, homeworkStatusTextClass } from "@/utils/homework";
import { formatDateTimeWithMsk } from "@/utils/time";

const notifications = useNotificationsStore();

const items = ref<StudentHomework[]>([]);
const files = ref<Record<string, File | null>>({});
const errors = ref<Record<string, string>>({});
const busyId = ref<string | null>(null);

async function load(): Promise<void> {
  items.value = await myHomework();
  // Бейдж у вкладки «ДЗ» считает несданные задания - после сдачи он должен погаснуть
  // сразу, не дожидаясь следующего опроса.
  notifications.refresh();
}

function setFile(submissionId: string, file: File | null): void {
  files.value = { ...files.value, [submissionId]: file };
  errors.value = { ...errors.value, [submissionId]: "" };
}

function setError(submissionId: string, err: unknown, fallback: string): void {
  // Причину знает сервер: слишком большой файл или неподходящий тип. Раньше
  // ошибка молча терялась, и ученик не понимал, отправилось ли что-нибудь.
  errors.value = { ...errors.value, [submissionId]: apiErrorMessage(err, fallback) };
}

async function complete(item: StudentHomework): Promise<void> {
  await markDone(item.submission_id);
  await load();
}

async function upload(item: StudentHomework): Promise<void> {
  const file = files.value[item.submission_id];
  if (!file) return;
  busyId.value = item.submission_id;
  errors.value = { ...errors.value, [item.submission_id]: "" };
  try {
    await uploadSubmission(item.submission_id, file);
    setFile(item.submission_id, null);
    await load();
  } catch (err) {
    setError(item.submission_id, err, "Не удалось отправить файл");
  } finally {
    busyId.value = null;
  }
}

async function removeFile(item: StudentHomework, fileId: string): Promise<void> {
  busyId.value = item.submission_id;
  errors.value = { ...errors.value, [item.submission_id]: "" };
  try {
    await deleteSubmissionFile(item.submission_id, fileId);
    await load();
  } catch (err) {
    // Чаще всего это 409: репетитор уже проверил работу, и менять её поздно.
    setError(item.submission_id, err, "Не удалось убрать файл");
  } finally {
    busyId.value = null;
  }
}

onMounted(load);
</script>

<template>
  <div class="flex max-w-2xl flex-col gap-3">
    <p v-if="items.length === 0" class="text-sm text-slate-400">Домашних заданий пока нет.</p>
    <div
      v-for="item in items"
      :key="item.submission_id"
      :data-status="item.status"
      class="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800"
      :class="homeworkCardClass(item.status)"
    >
      <div class="flex items-center justify-between gap-2">
        <div class="font-medium">{{ item.title || "Без названия" }}</div>
        <span class="text-xs font-medium" :class="homeworkStatusTextClass(item.status)">
          {{ homeworkStatusLabel(item.status) }}
        </span>
      </div>
      <div class="mt-1 flex gap-3 text-xs text-slate-500">
        <a v-if="item.content_url" :href="item.content_url" target="_blank" class="underline">Материал (ссылка)</a>
        <a v-if="item.content_file_path" :href="item.content_file_path" target="_blank" class="underline">Материал (файл)</a>
        <span v-if="item.due_at">Срок: {{ formatDateTimeWithMsk(item.due_at) }}</span>
      </div>

      <div v-if="item.submission_mode === 'file_upload'" class="mt-2 flex flex-col gap-2">
        <div v-if="item.files.length > 0" class="flex flex-col gap-1">
          <div class="text-xs text-slate-500">Ваши файлы</div>
          <!-- Проверенную работу менять уже нельзя - сервер на это отвечает 409. -->
          <HomeworkFiles
            :files="item.files"
            :removable="item.status !== 'done'"
            :disabled="busyId === item.submission_id"
            @remove="removeFile(item, $event)"
          />
        </div>
        <template v-if="item.status !== 'done'">
          <FileDropZone
            :model-value="files[item.submission_id] ?? null"
            :disabled="busyId === item.submission_id"
            @update:model-value="setFile(item.submission_id, $event)"
          />
          <div class="flex items-center gap-2">
            <button
              type="button"
              :disabled="!files[item.submission_id] || busyId === item.submission_id"
              class="rounded-md bg-brand-500 px-3 py-1.5 text-xs text-white disabled:opacity-50"
              @click="upload(item)"
            >
              {{ busyId === item.submission_id ? "Отправляем…" : item.files.length > 0 ? "Добавить файл" : "Отправить" }}
            </button>
          </div>
        </template>
      </div>
      <div v-else-if="item.status === 'pending'" class="mt-2">
        <button type="button" class="rounded-md bg-brand-500 px-3 py-1.5 text-xs text-white" @click="complete(item)">
          Отметить выполненным
        </button>
      </div>

      <p v-if="errors[item.submission_id]" class="mt-2 text-xs text-red-600 dark:text-red-400">
        {{ errors[item.submission_id] }}
      </p>
    </div>
  </div>
</template>
