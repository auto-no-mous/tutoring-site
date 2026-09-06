<script setup lang="ts">
import { onMounted, ref } from "vue";

import { markDone, myHomework, uploadSubmission } from "@/api/homework";
import FileDropZone from "@/components/FileDropZone.vue";
import type { StudentHomework } from "@/types/homework";
import { apiErrorMessage } from "@/utils/apiError";
import { formatDateTimeWithMsk } from "@/utils/time";

const items = ref<StudentHomework[]>([]);
const files = ref<Record<string, File | null>>({});
const errors = ref<Record<string, string>>({});
const busyId = ref<string | null>(null);

async function load(): Promise<void> {
  items.value = await myHomework();
}

function setFile(submissionId: string, file: File | null): void {
  files.value = { ...files.value, [submissionId]: file };
  errors.value = { ...errors.value, [submissionId]: "" };
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
    // Причину знает сервер: слишком большой файл или неподходящий тип. Раньше
    // ошибка молча терялась, и ученик не понимал, отправилось ли что-нибудь.
    errors.value = {
      ...errors.value,
      [item.submission_id]: apiErrorMessage(err, "Не удалось отправить файл"),
    };
  } finally {
    busyId.value = null;
  }
}

const statusLabels: Record<string, string> = { pending: "не выполнено", submitted: "отправлено", done: "выполнено" };

onMounted(load);
</script>

<template>
  <div class="flex max-w-2xl flex-col gap-3">
    <p v-if="items.length === 0" class="text-sm text-slate-400">Домашних заданий пока нет.</p>
    <div v-for="item in items" :key="item.submission_id" class="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
      <div class="flex items-center justify-between">
        <div class="font-medium">{{ item.title || "Без названия" }}</div>
        <span class="text-xs text-slate-500">{{ statusLabels[item.status] ?? item.status }}</span>
      </div>
      <div class="mt-1 flex gap-3 text-xs text-slate-500">
        <a v-if="item.content_url" :href="item.content_url" target="_blank" class="underline">Материал (ссылка)</a>
        <a v-if="item.content_file_path" :href="item.content_file_path" target="_blank" class="underline">Материал (файл)</a>
        <span v-if="item.due_at">Срок: {{ formatDateTimeWithMsk(item.due_at) }}</span>
      </div>

      <div v-if="item.status === 'pending'" class="mt-2">
        <button
          v-if="item.submission_mode === 'mark_done'"
          type="button"
          class="rounded-md bg-brand-500 px-3 py-1.5 text-xs text-white"
          @click="complete(item)"
        >
          Отметить выполненным
        </button>
        <div v-else class="flex flex-col gap-2">
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
              {{ busyId === item.submission_id ? "Отправляем…" : "Отправить" }}
            </button>
            <span v-if="errors[item.submission_id]" class="text-xs text-red-600 dark:text-red-400">
              {{ errors[item.submission_id] }}
            </span>
          </div>
        </div>
      </div>
      <a v-else-if="item.file_path" :href="item.file_path" target="_blank" class="mt-2 block text-xs underline">Ваш файл</a>
    </div>
  </div>
</template>
