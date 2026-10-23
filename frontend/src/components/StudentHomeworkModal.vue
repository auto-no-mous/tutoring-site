<script setup lang="ts">
import { X } from "lucide-vue-next";
import { DialogClose, DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui";
import { onMounted, ref } from "vue";

import { createHomework, getStudentHomeworkForTutor, setSubmissionStatus } from "@/api/homework";
import HomeworkFiles from "@/components/homework/HomeworkFiles.vue";
import HomeworkMaterialPicker from "@/components/homework/HomeworkMaterialPicker.vue";
import ShowMoreHomework from "@/components/homework/ShowMoreHomework.vue";
import type { StudentHomework } from "@/types/homework";
import { apiErrorMessage } from "@/utils/apiError";
import {
  emptyHomeworkMaterial,
  HOMEWORK_STATUS_OPTIONS,
  homeworkCardClass,
  homeworkMaterialPayload,
  homeworkMaterialProblem,
  useHomeworkPage,
} from "@/utils/homework";
import { formatDateTimeWithMsk } from "@/utils/time";

const props = defineProps<{ studentId: string; studentName: string }>();
const emit = defineEmits<{ close: []; changed: [] }>();

const items = ref<StudentHomework[]>([]);
const isLoading = ref(true);
const page = useHomeworkPage(items);
const showForm = ref(false);

const title = ref("");
const submissionMode = ref<"mark_done" | "file_upload">("mark_done");
const material = ref(emptyHomeworkMaterial());
const error = ref("");
const isSaving = ref(false);

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    items.value = await getStudentHomeworkForTutor(props.studentId);
    showForm.value = items.value.length === 0;
    if (showForm.value) resetForm();
  } finally {
    isLoading.value = false;
  }
}

// Новое задание обычно продолжает прошлое, поэтому название, способ сдачи и вид
// материала (ссылка или файл) берём из последнего (список приходит от новых к
// старым). Сам материал - всегда новый, поле пустое.
function resetForm(): void {
  const last = items.value[0];
  title.value = last?.title ?? "";
  submissionMode.value = last?.submission_mode === "file_upload" ? "file_upload" : "mark_done";
  material.value = emptyHomeworkMaterial(last?.content_type === "file" ? "file" : "link");
  error.value = "";
}

function openForm(): void {
  resetForm();
  showForm.value = true;
}

async function create(): Promise<void> {
  error.value = homeworkMaterialProblem(material.value) ?? "";
  if (error.value) return;
  isSaving.value = true;
  try {
    await createHomework({
      title: title.value.trim() || undefined,
      submission_mode: submissionMode.value,
      student_ids: [props.studentId],
      group_ids: [],
      ...homeworkMaterialPayload(material.value),
    });
    showForm.value = false;
    await load();
    emit("changed");
  } catch (err) {
    // Причину знает сервер (тип или размер файла и т.п.). Раньше здесь на любой отказ
    // стояло «укажите ссылку или файл», и отклонённый файл выглядел как невыбранный.
    error.value = apiErrorMessage(err, "Не удалось создать задание");
  } finally {
    isSaving.value = false;
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
  <!-- Диалог Reka UI: фокус запирается внутри окна, Escape и клик по подложке
       закрывают его, а фокус возвращается на вызвавшую кнопку. -->
  <DialogRoot :open="true" @update:open="(open) => !open && emit('close')">
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-50 bg-black/40 data-[state=closed]:animate-fade-out data-[state=open]:animate-fade-in"
      />
      <DialogContent
        class="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-lg flex max-h-[85vh] flex-col -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-5 shadow-xl
          data-[state=closed]:animate-pop-out data-[state=open]:animate-pop-in dark:bg-slate-900"
        :aria-describedby="undefined"
      >
        <div class="flex items-center justify-between gap-4">
          <DialogTitle class="text-lg font-semibold">ДЗ · {{ studentName }}</DialogTitle>
          <DialogClose class="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200">
            <X class="h-4 w-4" />
          </DialogClose>
        </div>

        <p v-if="isLoading" class="mt-4 text-sm text-slate-400">Загрузка…</p>
        <div v-else class="mt-3 flex flex-1 flex-col gap-3 overflow-y-auto">
          <p v-if="items.length === 0" class="text-sm text-slate-400">Заданий пока нет.</p>
          <div
            v-for="item in page.visible.value"
            :key="item.submission_id"
            class="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800"
            :class="homeworkCardClass(item.status)"
          >
            <div class="flex items-center justify-between">
              <div class="font-medium">{{ item.title || "Без названия" }}</div>
              <select
                :value="item.status"
                class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-xs dark:border-slate-700"
                @change="onStatusChange(item, $event)"
              >
                <option v-for="opt in HOMEWORK_STATUS_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>
            <div class="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
              <a v-if="item.content_url" :href="item.content_url" target="_blank" class="underline">Материал (ссылка)</a>
              <a v-if="item.content_file_path" :href="item.content_file_path" target="_blank" class="underline">Материал (файл)</a>
              <span v-if="item.due_at">Срок: {{ formatDateTimeWithMsk(item.due_at) }}</span>
            </div>
            <div v-if="item.files.length > 0" class="mt-1">
              <div class="text-xs text-slate-500">Файлы ученика</div>
              <HomeworkFiles :files="item.files" />
            </div>
            <div v-else-if="item.status !== 'pending'" class="mt-1 text-xs text-slate-400">
              Статус изменён вручную{{ item.submitted_at ? ` · ${formatDateTimeWithMsk(item.submitted_at)}` : "" }}
            </div>
          </div>
          <ShowMoreHomework :remaining="page.remaining.value" @more="page.showMore" />
        </div>

        <div class="mt-3 border-t border-slate-200 pt-3 dark:border-slate-800">
          <button
            v-if="!showForm"
            type="button"
            class="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
            @click="openForm"
          >
            + Новое задание
          </button>
          <form v-else class="flex flex-col gap-2" @submit.prevent="create">
            <label class="flex flex-col gap-1 text-sm">
              Что должен сделать ученик
              <select v-model="submissionMode" class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700">
                <option value="mark_done">Отметить «выполнено»</option>
                <option value="file_upload">Загрузить файл</option>
              </select>
            </label>
            <HomeworkMaterialPicker v-model="material" />
            <label class="flex flex-col gap-1 text-sm">
              Название задания
              <input
                v-model="title"
                placeholder="необязательно"
                class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700"
              />
            </label>
            <p v-if="error" class="text-xs text-red-600 dark:text-red-400">{{ error }}</p>
            <div class="flex items-center gap-2">
              <button
                type="submit"
                :disabled="isSaving"
                class="w-fit rounded-md bg-brand-500 px-4 py-2 text-sm text-white disabled:opacity-50"
              >
                {{ isSaving ? "Отправляем…" : "Отправить" }}
              </button>
              <button v-if="items.length > 0" type="button" class="text-xs text-slate-500 underline" @click="showForm = false">
                Отмена
              </button>
            </div>
          </form>
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
