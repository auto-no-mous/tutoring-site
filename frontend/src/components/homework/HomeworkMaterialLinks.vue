<script setup lang="ts">
import type { HomeworkAssignmentFile } from "@/types/homework";

// Ссылки на материал задания - ссылка или несколько файлов. Имена файлов на сервере
// случайные, поэтому файлы просто нумеруются, если их больше одного.
defineProps<{ url: string | null; files: HomeworkAssignmentFile[] }>();
</script>

<template>
  <a v-if="url" :href="url" target="_blank" class="underline">Материал (ссылка)</a>
  <a
    v-for="(file, index) in files"
    :key="file.id"
    :href="file.file_path"
    target="_blank"
    class="underline"
  >
    {{ files.length > 1 ? `Материал (файл ${index + 1})` : "Материал (файл)" }}
  </a>
</template>
