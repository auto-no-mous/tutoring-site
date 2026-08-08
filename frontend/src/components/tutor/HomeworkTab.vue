<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { listMyGroups } from "@/api/groups";
import {
  createHomework,
  deleteAssignment,
  duplicateHomework,
  listMyAssignments,
  listSubmissions,
  updateHomework,
} from "@/api/homework";
import { getMyStudents } from "@/api/tutors";
import HomeworkRecipientPicker from "@/components/tutor/HomeworkRecipientPicker.vue";
import type { Group } from "@/types/group";
import type { HomeworkAssignment, HomeworkSubmission } from "@/types/homework";
import type { TutorStudent } from "@/types/tutor";
import { formatDate, formatDateTimeWithMsk } from "@/utils/time";

const SUBMISSION_MODES: { value: "mark_done" | "file_upload"; label: string }[] = [
  { value: "mark_done", label: "Отметить «выполнено»" },
  { value: "file_upload", label: "Загрузить файл" },
];

const assignments = ref<HomeworkAssignment[]>([]);
const groups = ref<Group[]>([]);
const students = ref<TutorStudent[]>([]);
const submissionsByAssignment = ref<Record<string, HomeworkSubmission[]>>({});

async function load(): Promise<void> {
  const [assignmentsData, groupsData, studentsData] = await Promise.all([
    listMyAssignments(),
    listMyGroups(),
    getMyStudents(),
  ]);
  assignments.value = assignmentsData;
  groups.value = groupsData;
  students.value = studentsData;
}

function studentLabel(student: TutorStudent): string {
  const name = `${student.last_name} ${student.first_name}`.trim();
  return student.grade ? `${name}, ${student.grade}-й класс` : name;
}

function recipientLabel(assignment: HomeworkAssignment): string {
  if (assignment.group_id) return `Группа «${assignment.group_name ?? ""}»`;
  return assignment.student_display_name ?? "Ученик";
}

function submissionModeLabel(mode: string): string {
  return mode === "mark_done" ? "отметка «выполнено»" : "загрузка файла";
}

// --- Create form -------------------------------------------------------------

const showCreateForm = ref(false);
const createTitle = ref("");
const createSubmissionMode = ref<"mark_done" | "file_upload">("mark_done");
const createStudentIds = ref<string[]>([]);
const createGroupIds = ref<string[]>([]);
const createContentUrl = ref("");
const createFile = ref<File | null>(null);
const createFileInputEl = ref<HTMLInputElement | null>(null);
const createError = ref("");

function resetCreateForm(): void {
  createTitle.value = "";
  createSubmissionMode.value = "mark_done";
  createStudentIds.value = [];
  createGroupIds.value = [];
  createContentUrl.value = "";
  createFile.value = null;
  if (createFileInputEl.value) createFileInputEl.value.value = "";
  createError.value = "";
}

function toggleCreateForm(): void {
  showCreateForm.value = !showCreateForm.value;
  if (!showCreateForm.value) resetCreateForm();
}

function onCreateFileChange(event: Event): void {
  createFile.value = (event.target as HTMLInputElement).files?.[0] ?? null;
}

async function submitCreate(): Promise<void> {
  createError.value = "";
  if (createStudentIds.value.length === 0 && createGroupIds.value.length === 0) {
    createError.value = "Выберите хотя бы одного получателя.";
    return;
  }
  if (!createContentUrl.value.trim() && !createFile.value) {
    createError.value = "Укажите ссылку на материал или прикрепите файл.";
    return;
  }
  try {
    await createHomework({
      title: createTitle.value.trim() || undefined,
      submission_mode: createSubmissionMode.value,
      student_ids: createStudentIds.value,
      group_ids: createGroupIds.value,
      content_url: createContentUrl.value.trim() || undefined,
      file: createFile.value ?? undefined,
    });
    resetCreateForm();
    showCreateForm.value = false;
    await load();
  } catch {
    createError.value = "Не удалось создать задание. Проверьте введённые данные.";
  }
}

// --- Edit modal ----------------------------------------------------------------

const editing = ref<HomeworkAssignment | null>(null);
const editTitle = ref("");
const editSubmissionMode = ref<"mark_done" | "file_upload">("mark_done");
const editReplaceContent = ref(false);
const editContentUrl = ref("");
const editFile = ref<File | null>(null);
const editError = ref("");

function openEdit(assignment: HomeworkAssignment): void {
  editing.value = assignment;
  editTitle.value = assignment.title ?? "";
  editSubmissionMode.value = assignment.submission_mode as "mark_done" | "file_upload";
  editReplaceContent.value = false;
  editContentUrl.value = "";
  editFile.value = null;
  editError.value = "";
}

function closeEdit(): void {
  editing.value = null;
}

function onEditFileChange(event: Event): void {
  editFile.value = (event.target as HTMLInputElement).files?.[0] ?? null;
}

async function submitEdit(): Promise<void> {
  if (!editing.value) return;
  editError.value = "";
  if (editReplaceContent.value && !editContentUrl.value.trim() && !editFile.value) {
    editError.value = "Укажите ссылку на материал или прикрепите файл — или отмените замену материала.";
    return;
  }
  try {
    await updateHomework(editing.value.id, {
      title: editTitle.value.trim() || undefined,
      submission_mode: editSubmissionMode.value,
      content_url: editReplaceContent.value ? editContentUrl.value.trim() || undefined : undefined,
      file: editReplaceContent.value ? editFile.value ?? undefined : undefined,
    });
    closeEdit();
    await load();
  } catch {
    editError.value = "Не удалось сохранить изменения.";
  }
}

// --- Duplicate modal -------------------------------------------------------------

const duplicating = ref<HomeworkAssignment | null>(null);
const duplicateStudentIds = ref<string[]>([]);
const duplicateGroupIds = ref<string[]>([]);
const duplicateError = ref("");

function openDuplicate(assignment: HomeworkAssignment): void {
  duplicating.value = assignment;
  duplicateStudentIds.value = [];
  duplicateGroupIds.value = [];
  duplicateError.value = "";
}

function closeDuplicate(): void {
  duplicating.value = null;
}

async function submitDuplicate(): Promise<void> {
  if (!duplicating.value) return;
  duplicateError.value = "";
  if (duplicateStudentIds.value.length === 0 && duplicateGroupIds.value.length === 0) {
    duplicateError.value = "Выберите хотя бы одного получателя.";
    return;
  }
  try {
    await duplicateHomework(duplicating.value.id, duplicateStudentIds.value, duplicateGroupIds.value);
    closeDuplicate();
    await load();
  } catch {
    duplicateError.value = "Не удалось отправить копию задания.";
  }
}

// --- List: filters + submissions toggle + delete --------------------------------

const showFilters = ref(false);
const filterStudentId = ref("");
const filterStatus = ref<"all" | "pending" | "done">("all");
const filterDateFrom = ref("");
const filterDateTo = ref("");

const hasActiveFilters = computed(
  () => filterStudentId.value !== "" || filterStatus.value !== "all" || filterDateFrom.value !== "" || filterDateTo.value !== "",
);

function clearFilters(): void {
  filterStudentId.value = "";
  filterStatus.value = "all";
  filterDateFrom.value = "";
  filterDateTo.value = "";
}

const filteredAssignments = computed(() => {
  return assignments.value.filter((a) => {
    if (filterStudentId.value && a.student_id !== filterStudentId.value) return false;
    if (filterStatus.value !== "all" && a.status !== filterStatus.value) return false;
    const issuedDate = a.created_at.slice(0, 10);
    if (filterDateFrom.value && issuedDate < filterDateFrom.value) return false;
    if (filterDateTo.value && issuedDate > filterDateTo.value) return false;
    return true;
  });
});

async function toggleSubmissions(assignmentId: string): Promise<void> {
  if (submissionsByAssignment.value[assignmentId]) {
    delete submissionsByAssignment.value[assignmentId];
    return;
  }
  submissionsByAssignment.value[assignmentId] = await listSubmissions(assignmentId);
}

async function remove(assignmentId: string): Promise<void> {
  if (!window.confirm("Удалить это домашнее задание?")) return;
  await deleteAssignment(assignmentId);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex max-w-2xl flex-col gap-6">
    <div>
      <button
        type="button"
        class="rounded-md bg-slate-900 px-4 py-2 text-sm text-white dark:bg-white dark:text-slate-900"
        @click="toggleCreateForm"
      >
        {{ showCreateForm ? "Отмена" : "+ ДЗ" }}
      </button>

      <form
        v-if="showCreateForm"
        class="mt-3 flex flex-col gap-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800"
        @submit.prevent="submitCreate"
      >
        <label class="flex flex-col gap-1 text-sm">
          Получатели
          <HomeworkRecipientPicker
            :students="students"
            :groups="groups"
            :student-ids="createStudentIds"
            :group-ids="createGroupIds"
            @update:student-ids="createStudentIds = $event"
            @update:group-ids="createGroupIds = $event"
          />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Название задания
          <input
            v-model="createTitle"
            placeholder="необязательно"
            class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
          />
        </label>
        <div class="flex flex-col gap-1 text-sm">
          Что должен сделать ученик
          <div class="inline-flex w-fit rounded-md border border-slate-300 p-0.5 text-xs dark:border-slate-700">
            <button
              v-for="mode in SUBMISSION_MODES"
              :key="mode.value"
              type="button"
              class="rounded px-2.5 py-1"
              :class="createSubmissionMode === mode.value ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900' : 'text-slate-500'"
              @click="createSubmissionMode = mode.value"
            >
              {{ mode.label }}
            </button>
          </div>
        </div>
        <label class="flex flex-col gap-1 text-sm">
          Ссылка на материал
          <input
            v-model="createContentUrl"
            placeholder="необязательно"
            class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
          />
        </label>
        <input
          ref="createFileInputEl"
          type="file"
          class="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700 dark:file:bg-white dark:file:text-slate-900 dark:hover:file:bg-slate-200"
          @change="onCreateFileChange"
        />
        <p v-if="createError" class="text-sm text-red-600 dark:text-red-400">{{ createError }}</p>
        <button type="submit" class="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm text-white dark:bg-white dark:text-slate-900">
          Отправить
        </button>
      </form>
    </div>

    <div>
      <button
        type="button"
        class="text-sm text-slate-500 underline"
        @click="showFilters = !showFilters"
      >
        {{ showFilters ? "Скрыть фильтры" : "Фильтры" }}{{ hasActiveFilters ? " (активны)" : "" }}
      </button>
      <div v-if="showFilters" class="mt-2 flex flex-wrap items-end gap-3 rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
        <label class="flex flex-col gap-1">
          Ученик
          <select v-model="filterStudentId" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700">
            <option value="">Все</option>
            <option v-for="student in students" :key="student.id" :value="student.id">{{ studentLabel(student) }}</option>
          </select>
        </label>
        <label class="flex flex-col gap-1">
          Статус
          <select v-model="filterStatus" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700">
            <option value="all">Все</option>
            <option value="done">Выполнено</option>
            <option value="pending">Не выполнено</option>
          </select>
        </label>
        <label class="flex flex-col gap-1">
          Выдано с
          <input v-model="filterDateFrom" type="date" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1">
          Выдано по
          <input v-model="filterDateTo" type="date" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
        </label>
        <button type="button" class="text-xs text-slate-500 underline" @click="clearFilters">Сбросить</button>
      </div>
    </div>

    <div class="flex flex-col gap-2">
      <p v-if="assignments.length === 0" class="text-sm text-slate-400">Заданий пока нет.</p>
      <p v-else-if="filteredAssignments.length === 0" class="text-sm text-slate-400">Ничего не найдено по выбранным фильтрам.</p>
      <div v-for="assignment in filteredAssignments" :key="assignment.id" class="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
        <div class="flex items-start justify-between gap-2">
          <div>
            <div class="font-medium">{{ assignment.title || "Без названия" }}</div>
            <div class="text-slate-500">
              {{ recipientLabel(assignment) }} · {{ submissionModeLabel(assignment.submission_mode) }} ·
              <span :class="assignment.status === 'done' ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'">
                {{ assignment.status === "done" ? "выполнено" : "не выполнено" }}
              </span>
            </div>
            <div class="text-xs text-slate-400">Выдано {{ formatDate(assignment.created_at) }}</div>
          </div>
          <div class="flex shrink-0 gap-1.5">
            <button type="button" title="Сдачи" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="toggleSubmissions(assignment.id)">
              Сдачи
            </button>
            <button type="button" title="Изменить" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="openEdit(assignment)">
              ✏️
            </button>
            <button type="button" title="Скопировать" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="openDuplicate(assignment)">
              📋
            </button>
            <button type="button" title="Удалить" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="remove(assignment.id)">
              🗑️
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

    <!-- Edit modal -->
    <div v-if="editing" class="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4" @click.self="closeEdit">
      <div class="w-full max-w-md rounded-lg bg-white p-4 dark:bg-slate-900">
        <h3 class="text-sm font-semibold">Изменить задание</h3>
        <form class="mt-3 flex flex-col gap-3" @submit.prevent="submitEdit">
          <label class="flex flex-col gap-1 text-sm">
            Название задания
            <input v-model="editTitle" placeholder="необязательно" class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
          </label>
          <div class="flex flex-col gap-1 text-sm">
            Что должен сделать ученик
            <div class="inline-flex w-fit rounded-md border border-slate-300 p-0.5 text-xs dark:border-slate-700">
              <button
                v-for="mode in SUBMISSION_MODES"
                :key="mode.value"
                type="button"
                class="rounded px-2.5 py-1"
                :class="editSubmissionMode === mode.value ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900' : 'text-slate-500'"
                @click="editSubmissionMode = mode.value"
              >
                {{ mode.label }}
              </button>
            </div>
          </div>
          <div class="text-sm">
            <p class="text-slate-500">
              Текущий материал:
              <a v-if="editing.content_url" :href="editing.content_url" target="_blank" class="underline">ссылка</a>
              <a v-else-if="editing.content_file_path" :href="editing.content_file_path" target="_blank" class="underline">файл</a>
              <span v-else>не указан</span>
            </p>
            <label class="mt-1 flex items-center gap-2">
              <input v-model="editReplaceContent" type="checkbox" />
              Заменить материал
            </label>
            <template v-if="editReplaceContent">
              <input
                v-model="editContentUrl"
                placeholder="Ссылка на материал (необязательно)"
                class="mt-2 w-full rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
              />
              <input
                type="file"
                class="mt-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700 dark:file:bg-white dark:file:text-slate-900 dark:hover:file:bg-slate-200"
                @change="onEditFileChange"
              />
            </template>
          </div>
          <p v-if="editError" class="text-sm text-red-600 dark:text-red-400">{{ editError }}</p>
          <div class="flex gap-2">
            <button type="submit" class="rounded-md bg-slate-900 px-4 py-2 text-sm text-white dark:bg-white dark:text-slate-900">Сохранить</button>
            <button type="button" class="rounded-md border border-slate-300 px-4 py-2 text-sm dark:border-slate-700" @click="closeEdit">Отмена</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Duplicate modal -->
    <div v-if="duplicating" class="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4" @click.self="closeDuplicate">
      <div class="w-full max-w-md rounded-lg bg-white p-4 dark:bg-slate-900">
        <h3 class="text-sm font-semibold">Отправить копию: «{{ duplicating.title || "Без названия" }}»</h3>
        <p class="mt-1 text-xs text-slate-500">Содержимое задания останется таким же, выберите новых получателей.</p>
        <div class="mt-3">
          <HomeworkRecipientPicker
            :students="students"
            :groups="groups"
            :student-ids="duplicateStudentIds"
            :group-ids="duplicateGroupIds"
            @update:student-ids="duplicateStudentIds = $event"
            @update:group-ids="duplicateGroupIds = $event"
          />
        </div>
        <p v-if="duplicateError" class="mt-2 text-sm text-red-600 dark:text-red-400">{{ duplicateError }}</p>
        <div class="mt-3 flex gap-2">
          <button type="button" class="rounded-md bg-slate-900 px-4 py-2 text-sm text-white dark:bg-white dark:text-slate-900" @click="submitDuplicate">
            Отправить копию
          </button>
          <button type="button" class="rounded-md border border-slate-300 px-4 py-2 text-sm dark:border-slate-700" @click="closeDuplicate">Отмена</button>
        </div>
      </div>
    </div>
  </div>
</template>
