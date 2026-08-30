<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  createManualBooking,
  listTutorRecurringSeries,
  stopSeries,
  type TutorRecurringSeries,
} from "@/api/bookings";
import {
  createClaimLink,
  createManagedStudent,
  deleteManagedStudent,
  getMyStudentsWithStats,
  setStudentNote,
  updateManagedStudent,
  type TutorStudentStats,
} from "@/api/tutors";
import { getMyLessonTypes } from "@/api/tutors";
import type { LessonType } from "@/types/tutor";
import { apiErrorMessage } from "@/utils/apiError";
import { formatDateTimeWithMsk, mskDateTimeToUtcIso, nextMskDateForWeekday } from "@/utils/time";

const emit = defineEmits<{ created: [student: TutorStudentStats] }>();

const students = ref<TutorStudentStats[]>([]);
const isLoading = ref(true);
const error = ref("");

// Форма заведения ученика вручную. Почты и пароля здесь нет намеренно: их задаёт сам
// ученик, если однажды заберёт профиль по ссылке-приглашению.
const showForm = ref(false);
const editingId = ref<string | null>(null);
const firstName = ref("");
const lastName = ref("");
const patronymic = ref("");
const grade = ref<number | null>(null);
const isSaving = ref(false);

// Примечание правится по месту, у каждой строки своё состояние.
const noteDrafts = ref<Record<string, string>>({});
const openNoteId = ref<string | null>(null);
const claimLinks = ref<Record<string, string>>({});
const copiedId = ref<string | null>(null);

// --- Еженедельные занятия ---------------------------------------------------------

const WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

const series = ref<TutorRecurringSeries[]>([]);
const lessonTypes = ref<LessonType[]>([]);
const openSeriesStudentId = ref<string | null>(null);
const seriesWeekday = ref(0);
const seriesTime = ref("18:00");
const seriesLessonTypeId = ref("");
const isSavingSeries = ref(false);

function seriesFor(studentId: string): TutorRecurringSeries[] {
  return series.value.filter((row) => row.student_id === studentId);
}

async function openSeriesForm(student: TutorStudentStats): Promise<void> {
  error.value = "";
  openSeriesStudentId.value = openSeriesStudentId.value === student.id ? null : student.id;
  if (openSeriesStudentId.value === null) return;
  if (lessonTypes.value.length === 0) {
    lessonTypes.value = (await getMyLessonTypes()).filter((t) => t.format === "individual");
  }
  seriesLessonTypeId.value = lessonTypes.value[0]?.id ?? "";
}

async function createSeries(student: TutorStudentStats): Promise<void> {
  const lessonType = lessonTypes.value.find((t) => t.id === seriesLessonTypeId.value);
  if (!lessonType) {
    error.value = "Сначала добавьте тип индивидуального занятия во вкладке «Расписание»";
    return;
  }
  error.value = "";
  isSavingSeries.value = true;
  try {
    const startIso = mskDateTimeToUtcIso(
      nextMskDateForWeekday(seriesWeekday.value, seriesTime.value),
      seriesTime.value,
    );
    const endIso = new Date(
      new Date(startIso).getTime() + lessonType.duration_minutes * 60000,
    ).toISOString();
    await createManualBooking({
      student_id: student.id,
      lesson_type_id: lessonType.id,
      start_at: startIso,
      end_at: endIso,
      repeat_weekly: true,
    });
    openSeriesStudentId.value = null;
    await load();
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось назначить занятие");
  } finally {
    isSavingSeries.value = false;
  }
}

async function stopOneSeries(row: TutorRecurringSeries): Promise<void> {
  const when = `${WEEKDAYS[row.weekday].toLowerCase()} в ${row.start_time.slice(0, 5)}`;
  if (
    !window.confirm(
      `Остановить еженедельные занятия (${when})? Уже созданные занятия останутся в расписании.`,
    )
  ) {
    return;
  }
  error.value = "";
  try {
    await stopSeries(row.id);
    await load();
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось остановить серию");
  }
}

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    [students.value, series.value] = await Promise.all([
      getMyStudentsWithStats(),
      listTutorRecurringSeries(),
    ]);
  } finally {
    isLoading.value = false;
  }
}

function fullName(student: TutorStudentStats): string {
  return [student.last_name, student.first_name, student.patronymic].filter(Boolean).join(" ");
}

function startCreate(): void {
  editingId.value = null;
  firstName.value = "";
  lastName.value = "";
  patronymic.value = "";
  grade.value = null;
  showForm.value = true;
}

function startEdit(student: TutorStudentStats): void {
  editingId.value = student.id;
  firstName.value = student.first_name;
  lastName.value = student.last_name;
  patronymic.value = student.patronymic ?? "";
  grade.value = student.grade;
  showForm.value = true;
}

async function save(): Promise<void> {
  error.value = "";
  isSaving.value = true;
  try {
    const payload = {
      first_name: firstName.value.trim(),
      last_name: lastName.value.trim(),
      patronymic: patronymic.value.trim() || null,
      grade: grade.value,
    };
    if (editingId.value) {
      await updateManagedStudent(editingId.value, payload);
    } else {
      const created = await createManagedStudent(payload);
      // Форма записи вручную открыта на той же странице кабинета - пусть сразу
      // увидит нового ученика в своём списке.
      emit("created", created);
    }
    showForm.value = false;
    await load();
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось сохранить ученика");
  } finally {
    isSaving.value = false;
  }
}

async function remove(student: TutorStudentStats): Promise<void> {
  if (
    !window.confirm(
      `Удалить ученика «${fullName(student)}»? Его занятия останутся в расписании как ` +
        "свободные блоки времени, домашние задания и участие в группах будут удалены.",
    )
  ) {
    return;
  }
  error.value = "";
  try {
    await deleteManagedStudent(student.id);
    await load();
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось удалить ученика");
  }
}

function toggleNote(student: TutorStudentStats): void {
  openNoteId.value = openNoteId.value === student.id ? null : student.id;
  noteDrafts.value = { ...noteDrafts.value, [student.id]: student.note ?? "" };
}

async function saveNote(student: TutorStudentStats): Promise<void> {
  error.value = "";
  try {
    await setStudentNote(student.id, noteDrafts.value[student.id] ?? "");
    openNoteId.value = null;
    await load();
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось сохранить примечание");
  }
}

async function makeClaimLink(student: TutorStudentStats): Promise<void> {
  error.value = "";
  try {
    const link = await createClaimLink(student.id);
    claimLinks.value = { ...claimLinks.value, [student.id]: link.url };
    try {
      await navigator.clipboard.writeText(link.url);
      copiedId.value = student.id;
      window.setTimeout(() => (copiedId.value = null), 2000);
    } catch {
      // Буфер может быть недоступен (нет https, отказ в правах) - ссылка всё равно
      // показана рядом, её можно скопировать руками.
    }
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось создать ссылку");
  }
}

defineExpose({ reload: load });
onMounted(load);
</script>

<template>
  <section>
    <div class="flex items-center justify-between gap-3">
      <h2 class="text-lg font-medium">Ученики</h2>
      <button
        type="button"
        class="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
        @click="showForm ? (showForm = false) : startCreate()"
      >
        {{ showForm ? "Отмена" : "+ Новый ученик" }}
      </button>
    </div>

    <form
      v-if="showForm"
      class="mt-3 flex flex-col gap-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800"
      @submit.prevent="save"
    >
      <p class="text-sm text-slate-500">
        {{
          editingId
            ? "Данные ученика видны только вам."
            : "Ученик без аккаунта: вы сможете записывать его на занятия и добавлять в группы. Позже он сможет забрать профиль себе по ссылке."
        }}
      </p>
      <div class="flex flex-wrap gap-2">
        <label class="flex flex-col gap-1 text-sm">
          Фамилия
          <input v-model="lastName" required class="w-44 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Имя
          <input v-model="firstName" required class="w-44 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Отчество
          <input v-model="patronymic" class="w-44 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Класс
          <select v-model.number="grade" class="w-32 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700">
            <option :value="null">—</option>
            <option v-for="n in 11" :key="n" :value="n">{{ n }}-й класс</option>
          </select>
        </label>
      </div>
      <button type="submit" :disabled="isSaving" class="w-fit rounded-md bg-brand-500 px-3 py-1.5 text-sm text-white disabled:opacity-50">
        {{ editingId ? "Сохранить" : "Создать ученика" }}
      </button>
    </form>

    <p v-if="error" class="mt-3 text-sm text-red-600 dark:text-red-400">{{ error }}</p>
    <p v-if="isLoading" class="mt-3 text-sm text-slate-400">Загрузка…</p>
    <p v-else-if="students.length === 0" class="mt-3 text-sm text-slate-400">
      Учеников пока нет. Они появятся здесь после первой записи — или заведите ученика вручную.
    </p>

    <div v-else class="mt-3 flex flex-col gap-2">
      <div
        v-for="student in students"
        :key="student.id"
        class="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800"
      >
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div class="flex items-center gap-3">
            <img v-if="student.photo_url" :src="student.photo_url" alt="" class="h-10 w-10 rounded-full object-cover" />
            <div>
              <RouterLink :to="`/students/${student.id}`" class="font-medium hover:underline">
                {{ fullName(student) }}
              </RouterLink>
              <span v-if="student.grade" class="text-slate-500 dark:text-slate-400"> · {{ student.grade }}-й класс</span>
              <span
                v-if="student.is_managed"
                class="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                title="Профиль заведён вами: ученик пока не может войти на сайт"
              >
                без аккаунта
              </span>
            </div>
          </div>
          <div class="flex flex-wrap gap-2 text-xs">
            <button type="button" class="text-slate-500 underline" @click="toggleNote(student)">
              {{ student.note ? "Примечание" : "+ Примечание" }}
            </button>
            <button type="button" class="text-slate-500 underline" @click="openSeriesForm(student)">
              {{ openSeriesStudentId === student.id ? "Отмена" : "+ Еженедельное занятие" }}
            </button>
            <template v-if="student.is_managed">
              <button type="button" class="text-slate-500 underline" @click="startEdit(student)">Изменить</button>
              <button type="button" class="text-slate-500 underline" @click="makeClaimLink(student)">
                {{ copiedId === student.id ? "Ссылка скопирована" : "Ссылка для входа" }}
              </button>
              <button type="button" class="text-red-600 underline dark:text-red-400" @click="remove(student)">Удалить</button>
            </template>
          </div>
        </div>

        <div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
          <span>занятий: {{ student.lessons_held }}</span>
          <span v-if="student.no_shows > 0">пропусков: {{ student.no_shows }}</span>
          <span v-if="student.next_lesson_at">ближайшее: {{ formatDateTimeWithMsk(student.next_lesson_at) }}</span>
          <span v-else-if="student.last_lesson_at">последнее: {{ formatDateTimeWithMsk(student.last_lesson_at) }}</span>
          <span v-if="student.homework_done + student.homework_pending > 0">
            домашних заданий: {{ student.homework_done }} сдано, {{ student.homework_pending }} нет
          </span>
        </div>

        <div v-if="seriesFor(student.id).length > 0" class="mt-2 flex flex-col gap-1">
          <div
            v-for="row in seriesFor(student.id)"
            :key="row.id"
            class="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300"
          >
            <span>
              Еженедельно: {{ WEEKDAYS[row.weekday].toLowerCase() }}, {{ row.start_time.slice(0, 5) }} (МСК) —
              {{ row.lesson_type_name }}
            </span>
            <button type="button" class="text-slate-500 underline" @click="stopOneSeries(row)">Остановить</button>
          </div>
        </div>

        <div
          v-if="openSeriesStudentId === student.id"
          class="mt-2 flex flex-col gap-2 rounded-md border border-slate-200 p-3 dark:border-slate-800"
        >
          <div class="flex flex-wrap items-end gap-2">
            <label class="flex flex-col gap-1 text-xs">
              День недели
              <select v-model.number="seriesWeekday" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700">
                <option v-for="(day, index) in WEEKDAYS" :key="index" :value="index">{{ day }}</option>
              </select>
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Время (МСК)
              <input v-model="seriesTime" type="time" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Тип занятия
              <select v-model="seriesLessonTypeId" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700">
                <option v-for="type in lessonTypes" :key="type.id" :value="type.id">
                  {{ type.name }} ({{ type.duration_minutes }} мин)
                </option>
              </select>
            </label>
            <button
              type="button"
              :disabled="isSavingSeries || !seriesLessonTypeId"
              class="rounded-md bg-brand-500 px-3 py-1.5 text-sm text-white disabled:opacity-50"
              @click="createSeries(student)"
            >
              Назначить
            </button>
          </div>
          <span class="text-xs text-slate-400">
            Первое занятие — в ближайший {{ WEEKDAYS[seriesWeekday].toLowerCase() }}, дальше каждую неделю.
            Занятия создаются на 8 недель вперёд; недели, где время уже занято, пропускаются.
          </span>
        </div>

        <p v-if="student.note && openNoteId !== student.id" class="mt-2 whitespace-pre-wrap text-slate-600 dark:text-slate-300">
          {{ student.note }}
        </p>

        <div v-if="openNoteId === student.id" class="mt-2 flex flex-col gap-2">
          <textarea
            v-model="noteDrafts[student.id]"
            rows="3"
            maxlength="2000"
            placeholder="Например: повторить системы счисления на следующем занятии"
            class="w-full rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
          ></textarea>
          <div class="flex items-center gap-2">
            <button type="button" class="rounded-md bg-brand-500 px-3 py-1 text-xs text-white" @click="saveNote(student)">
              Сохранить
            </button>
            <span class="text-xs text-slate-400">Видно только вам. Пустое поле удалит примечание.</span>
          </div>
        </div>

        <div v-if="claimLinks[student.id]" class="mt-2 flex flex-col gap-1">
          <span class="text-xs text-slate-400">
            Отправьте ссылку ученику — по ней он задаст себе вход и получит этот профиль вместе со всеми занятиями. Ссылка действует 30 дней.
          </span>
          <input
            :value="claimLinks[student.id]"
            readonly
            class="w-full rounded-md border border-slate-300 bg-slate-50 px-2 py-1 text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-800"
          />
        </div>
      </div>
    </div>
  </section>
</template>
