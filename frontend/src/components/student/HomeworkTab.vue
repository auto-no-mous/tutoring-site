<script setup lang="ts">
import { onMounted, ref } from "vue";

import { deleteSubmissionFile, markDone, myHomework, uploadSubmission } from "@/api/homework";
import FileDropZone from "@/components/FileDropZone.vue";
import HomeworkFiles from "@/components/homework/HomeworkFiles.vue";
import HomeworkMaterialLinks from "@/components/homework/HomeworkMaterialLinks.vue";
import ShowMoreHomework from "@/components/homework/ShowMoreHomework.vue";
import { useNotificationsStore } from "@/stores/notifications";
import type { StudentHomework } from "@/types/homework";
import { apiErrorMessage } from "@/utils/apiError";
import {
  attachmentsProblem,
  homeworkCardClass,
  homeworkStatusLabel,
  homeworkStatusTextClass,
  MAX_HOMEWORK_FILES,
  useHomeworkPage,
} from "@/utils/homework";
import { formatDateTimeWithMsk } from "@/utils/time";

const notifications = useNotificationsStore();

const items = ref<StudentHomework[]>([]);
// Выбранные, но ещё не отправленные файлы - по сдаче.
const files = ref<Record<string, File[]>>({});
const errors = ref<Record<string, string>>({});
const busyId = ref<string | null>(null);
const page = useHomeworkPage(items);

async function load(): Promise<void> {
  items.value = await myHomework();
  // Бейдж у вкладки «ДЗ» считает несданные задания - после сдачи он должен погаснуть
  // сразу, не дожидаясь следующего опроса.
  notifications.refresh();
}

function setFiles(submissionId: string, picked: File[]): void {
  files.value = { ...files.value, [submissionId]: picked };
  errors.value = { ...errors.value, [submissionId]: attachmentsProblem(picked) ?? "" };
}

function pickedFiles(submissionId: string): File[] {
  return files.value[submissionId] ?? [];
}

// Всего к сдаче - не больше MAX_HOMEWORK_FILES, вместе с уже отправленными.
function roomFor(item: StudentHomework): number {
  return Math.max(0, MAX_HOMEWORK_FILES - item.files.length);
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
  const picked = pickedFiles(item.submission_id);
  if (picked.length === 0) return;
  const problem = attachmentsProblem(picked);
  if (problem) {
    errors.value = { ...errors.value, [item.submission_id]: problem };
    return;
  }
  busyId.value = item.submission_id;
  errors.value = { ...errors.value, [item.submission_id]: "" };
  try {
    await uploadSubmission(item.submission_id, picked);
    setFiles(item.submission_id, []);
    await load();
  } catch (err) {
    setError(item.submission_id, err, "Не удалось отправить файлы");
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
      v-for="item in page.visible.value"
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
        <HomeworkMaterialLinks :url="item.content_url" :files="item.content_files" />
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
          <template v-if="roomFor(item) > 0">
            <FileDropZone
              :model-value="pickedFiles(item.submission_id)"
              :max="roomFor(item)"
              :disabled="busyId === item.submission_id"
              @update:model-value="setFiles(item.submission_id, $event)"
            />
            <div class="flex items-center gap-2">
              <button
                type="button"
                :disabled="pickedFiles(item.submission_id).length === 0 || busyId === item.submission_id"
                class="rounded-md bg-brand-500 px-3 py-1.5 text-xs text-white disabled:opacity-50"
                @click="upload(item)"
              >
                {{
                  busyId === item.submission_id
                    ? "Отправляем…"
                    : item.files.length > 0
                      ? pickedFiles(item.submission_id).length > 1 ? "Добавить файлы" : "Добавить файл"
                      : "Отправить"
                }}
              </button>
            </div>
          </template>
          <p v-else class="text-xs text-slate-400">
            Приложено {{ MAX_HOMEWORK_FILES }} файлов - больше нельзя. Уберите лишний, чтобы добавить другой.
          </p>
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
    <ShowMoreHomework :remaining="page.remaining.value" @more="page.showMore" />
  </div>
</template>
