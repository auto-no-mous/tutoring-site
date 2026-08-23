<script setup lang="ts">
import { onMounted, ref } from "vue";

import { markDone, myHomework, uploadSubmission } from "@/api/homework";
import type { StudentHomework } from "@/types/homework";
import { formatDateTimeWithMsk } from "@/utils/time";

const items = ref<StudentHomework[]>([]);
const files = ref<Record<string, File | null>>({});

async function load(): Promise<void> {
  items.value = await myHomework();
}

function onFileChange(submissionId: string, event: Event): void {
  files.value[submissionId] = (event.target as HTMLInputElement).files?.[0] ?? null;
}

async function complete(item: StudentHomework): Promise<void> {
  await markDone(item.submission_id);
  await load();
}

async function upload(item: StudentHomework): Promise<void> {
  const file = files.value[item.submission_id];
  if (!file) return;
  await uploadSubmission(item.submission_id, file);
  await load();
}

const statusLabels: Record<string, string> = { pending: "не выполнено", submitted: "отправлено", done: "выполнено" };

onMounted(load);
</script>

<template>
  <div class="flex max-w-2xl flex-col gap-3">
    <p v-if="items.length === 0" class="text-sm text-slate-400">Домашних заданий пока нет.</p>
    <div v-for="item in items" :key="item.submission_id" class="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
      <div class="flex items-center justify-between">
        <div class="font-medium">{{ item.title }}</div>
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
        <div v-else class="flex items-center gap-2">
          <input
            type="file"
            class="text-xs file:mr-2 file:rounded-md file:border-0 file:bg-brand-500 file:px-2.5 file:py-1 file:text-xs file:font-medium file:text-white hover:file:bg-slate-700 dark:file:bg-white dark:file:text-slate-900 dark:hover:file:bg-slate-200"
            @change="onFileChange(item.submission_id, $event)"
          />
          <button type="button" class="rounded-md bg-brand-500 px-3 py-1.5 text-xs text-white" @click="upload(item)">
            Отправить
          </button>
        </div>
      </div>
      <a v-else-if="item.file_path" :href="item.file_path" target="_blank" class="mt-2 block text-xs underline">Ваш файл</a>
    </div>
  </div>
</template>
