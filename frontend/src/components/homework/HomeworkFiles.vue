<script setup lang="ts">
import type { HomeworkSubmissionFile } from "@/types/homework";
import { homeworkFileName } from "@/utils/homework";
import { formatDateTimeWithMsk } from "@/utils/time";

// Файлов у сдачи может быть несколько: ученик добавляет ещё один скриншот или убирает
// ошибочный. Список рисуют и вкладка ученика, и карточки репетитора.
defineProps<{
  files: HomeworkSubmissionFile[];
  removable?: boolean;
  disabled?: boolean;
}>();

const emit = defineEmits<{ remove: [fileId: string] }>();
</script>

<template>
  <div v-if="files.length > 0" class="flex flex-col gap-1">
    <div v-for="file in files" :key="file.id" class="flex items-center gap-2 text-xs">
      <a :href="file.file_path" target="_blank" class="underline" :title="formatDateTimeWithMsk(file.uploaded_at)">
        {{ homeworkFileName(file.file_path) }}
      </a>
      <span class="text-slate-400">{{ formatDateTimeWithMsk(file.uploaded_at) }}</span>
      <button
        v-if="removable"
        type="button"
        :disabled="disabled"
        class="text-slate-400 hover:text-red-600 disabled:opacity-50 dark:hover:text-red-400"
        title="Убрать файл"
        @click="emit('remove', file.id)"
      >
        ✕
      </button>
    </div>
  </div>
</template>
