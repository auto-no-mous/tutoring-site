<script setup lang="ts">
import { Link2, Paperclip } from "lucide-vue-next";
import { computed } from "vue";

import FileDropZone from "@/components/FileDropZone.vue";
import { ATTACHMENT_ACCEPT, attachmentProblem } from "@/utils/attachments";
import { emptyHomeworkMaterial, type HomeworkMaterial } from "@/utils/homework";

// Материал задания - либо ссылка, либо файл. Раньше оба поля стояли рядом, и форма
// как будто разрешала заполнить оба, а сервер принимает ровно один вариант. Теперь
// сначала выбирается вид, и на экране только его поле; второе при переключении
// очищается, чтобы в запрос не уехало забытое значение.
const props = defineProps<{ modelValue: HomeworkMaterial }>();
const emit = defineEmits<{ "update:modelValue": [HomeworkMaterial] }>();

const KINDS = [
  { value: "link", label: "Ссылка", icon: Link2 },
  { value: "file", label: "Файл", icon: Paperclip },
] as const;

const fileProblem = computed(() => (props.modelValue.file ? attachmentProblem(props.modelValue.file) : null));

function setKind(kind: HomeworkMaterial["kind"]): void {
  if (kind === props.modelValue.kind) return;
  emit("update:modelValue", emptyHomeworkMaterial(kind));
}
</script>

<template>
  <div class="flex flex-col gap-1.5 text-sm">
    <span>Материал задания</span>
    <div class="inline-flex w-fit rounded-md border border-slate-300 p-0.5 dark:border-slate-700" role="radiogroup" aria-label="Материал задания">
      <button
        v-for="k in KINDS"
        :key="k.value"
        type="button"
        role="radio"
        :aria-checked="modelValue.kind === k.value"
        class="inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs"
        :class="modelValue.kind === k.value ? 'bg-brand-500 text-white' : 'text-slate-500'"
        @click="setKind(k.value)"
      >
        <component :is="k.icon" class="h-3.5 w-3.5" />{{ k.label }}
      </button>
    </div>

    <input
      v-if="modelValue.kind === 'link'"
      :value="modelValue.url"
      type="url"
      inputmode="url"
      placeholder="https://…"
      aria-label="Ссылка на материал"
      class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
      @input="emit('update:modelValue', { ...modelValue, url: ($event.target as HTMLInputElement).value })"
    />
    <template v-else>
      <FileDropZone
        :model-value="modelValue.file"
        :accept="ATTACHMENT_ACCEPT"
        hide-type-hint
        @update:model-value="emit('update:modelValue', { ...modelValue, file: $event })"
      />
      <p v-if="fileProblem" class="text-xs text-red-600 dark:text-red-400">{{ fileProblem }}</p>
    </template>
  </div>
</template>
