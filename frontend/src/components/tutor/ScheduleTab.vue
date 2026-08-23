<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  createLessonType,
  deleteLessonType,
  getMyAvailability,
  getMyLessonTypes,
  getMyProfile,
  replaceMyAvailability,
  updateLessonType,
  updateMyProfile,
} from "@/api/tutors";
import type { LessonType, TutorProfile } from "@/types/tutor";

interface EditableInterval {
  weekday: number;
  start_time: string;
  end_time: string;
}

const weekdayNames = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];
const intervals = ref<EditableInterval[]>([]);
const profile = ref<TutorProfile | null>(null);
const savedMessage = ref("");
const settingsSavedMessage = ref("");
const isSaving = ref(false);
const isSavingSettings = ref(false);

// --- Lesson types (moved here from the old, now-removed "Типы занятий" tab - a
// separate tab for this felt like one tab too many; it belongs next to schedule
// settings since together they define what can be booked and when). ---
const types = ref<LessonType[]>([]);
const name = ref("");
const format = ref<"individual" | "group">("individual");
const duration = ref(60);
const price = ref(1000);
const typeError = ref("");

const editingId = ref<string | null>(null);
const editName = ref("");
const editDuration = ref(60);
const editPrice = ref(0);
const editError = ref("");

const isAdding = ref(false);

const hasActiveIndividualType = computed(() => types.value.some((t) => t.format === "individual" && t.is_active));
const hasActiveGroupType = computed(() => types.value.some((t) => t.format === "group" && t.is_active));

async function load(): Promise<void> {
  const [rows, profileData, lessonTypes] = await Promise.all([getMyAvailability(), getMyProfile(), getMyLessonTypes()]);
  intervals.value = rows.map((r) => ({ weekday: r.weekday, start_time: r.start_time.slice(0, 5), end_time: r.end_time.slice(0, 5) }));
  profile.value = profileData;
  types.value = lessonTypes;
}

function openAdd(): void {
  name.value = "";
  format.value = "individual";
  duration.value = 60;
  price.value = 1000;
  typeError.value = "";
  isAdding.value = true;
}

function cancelAdd(): void {
  isAdding.value = false;
  typeError.value = "";
}

async function createType(): Promise<void> {
  typeError.value = "";
  try {
    await createLessonType({ name: name.value, format: format.value, duration_minutes: duration.value, price: price.value });
    isAdding.value = false;
    types.value = await getMyLessonTypes();
  } catch {
    typeError.value = "Не удалось создать тип занятия (длительность должна быть кратна шагу сетки расписания).";
  }
}

function startEditType(type: LessonType): void {
  editingId.value = type.id;
  editName.value = type.name;
  editDuration.value = type.duration_minutes;
  editPrice.value = type.price;
  editError.value = "";
}

function cancelEditType(): void {
  editingId.value = null;
  editError.value = "";
}

async function saveEditType(type: LessonType): Promise<void> {
  editError.value = "";
  try {
    await updateLessonType(type.id, {
      name: editName.value,
      duration_minutes: editDuration.value,
      price: editPrice.value,
    });
    editingId.value = null;
    types.value = await getMyLessonTypes();
  } catch {
    editError.value = "Не удалось сохранить (длительность должна быть кратна шагу сетки расписания).";
  }
}

async function toggleTypeActive(type: LessonType): Promise<void> {
  await updateLessonType(type.id, { is_active: !type.is_active });
  types.value = await getMyLessonTypes();
}

async function removeType(type: LessonType): Promise<void> {
  await deleteLessonType(type.id);
  types.value = await getMyLessonTypes();
}
// --- end lesson types ---

function addInterval(weekday: number): void {
  intervals.value.push({ weekday, start_time: "09:00", end_time: "18:00" });
}

function removeInterval(index: number): void {
  intervals.value.splice(index, 1);
}

async function save(): Promise<void> {
  isSaving.value = true;
  savedMessage.value = "";
  try {
    await replaceMyAvailability(
      intervals.value.map((i) => ({ weekday: i.weekday, start_time: `${i.start_time}:00`, end_time: `${i.end_time}:00` })),
    );
    savedMessage.value = "Сохранено";
  } finally {
    isSaving.value = false;
  }
}

async function saveSettings(): Promise<void> {
  if (!profile.value) return;
  isSavingSettings.value = true;
  settingsSavedMessage.value = "";
  try {
    profile.value = await updateMyProfile({
      slot_granularity_minutes: profile.value.slot_granularity_minutes,
      break_between_lessons_minutes: profile.value.break_between_lessons_minutes,
      min_lead_time_hours: profile.value.min_lead_time_hours,
      allow_individual_bookings: profile.value.allow_individual_bookings,
      allow_group_bookings: profile.value.allow_group_bookings,
    });
    settingsSavedMessage.value = "Сохранено";
  } finally {
    isSavingSettings.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="flex max-w-2xl flex-col gap-8">
    <section class="flex flex-col gap-4">
      <h2 class="text-lg font-medium">Типы занятий</h2>
      <div class="flex flex-col gap-2">
        <div v-for="type in types" :key="type.id" class="rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
          <template v-if="editingId === type.id">
            <div class="flex flex-wrap items-end gap-2">
              <label class="flex flex-col gap-1 text-xs">
                Название
                <input v-model="editName" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
              </label>
              <label class="flex flex-col gap-1 text-xs">
                Длительность, мин
                <input v-model.number="editDuration" type="number" min="1" class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
              </label>
              <label class="flex flex-col gap-1 text-xs">
                Цена, ₽
                <input v-model.number="editPrice" type="number" min="0" class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
              </label>
              <button type="button" class="rounded-md bg-brand-500 px-2 py-1 text-xs text-white" @click="saveEditType(type)">
                Сохранить
              </button>
              <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="cancelEditType">
                Отмена
              </button>
            </div>
            <p v-if="editError" class="mt-1 text-xs text-red-600 dark:text-red-400">{{ editError }}</p>
          </template>
          <div v-else class="flex items-center justify-between">
            <div>
              <div class="font-medium">{{ type.name }} <span class="text-slate-400">({{ type.format === "individual" ? "инд." : "групп." }})</span></div>
              <div class="text-slate-500">{{ type.duration_minutes }} мин · {{ type.price }} ₽ · {{ type.is_active ? "активен" : "выключен" }}</div>
            </div>
            <div class="flex gap-2">
              <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="startEditType(type)">
                Изменить
              </button>
              <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="toggleTypeActive(type)">
                {{ type.is_active ? "Выключить" : "Включить" }}
              </button>
              <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="removeType(type)">
                Удалить
              </button>
            </div>
          </div>
        </div>
      </div>

      <button
        v-if="!isAdding"
        type="button"
        class="w-fit rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
        @click="openAdd"
      >
        Добавить +
      </button>

      <form v-else class="flex flex-wrap items-end gap-2 rounded-lg border border-slate-200 p-4 dark:border-slate-800" @submit.prevent="createType">
        <label class="flex flex-col gap-1 text-sm">
          Название
          <input v-model="name" required class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Формат
          <select v-model="format" class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700">
            <option value="individual">Индивидуальное</option>
            <option value="group">Групповое</option>
          </select>
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Длительность, мин
          <input v-model.number="duration" type="number" min="1" class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Цена, ₽
          <input v-model.number="price" type="number" min="0" class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <button type="submit" class="rounded-md bg-brand-500 px-3 py-1.5 text-sm text-white">Сохранить</button>
        <button type="button" class="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700" @click="cancelAdd">Отмена</button>
        <p v-if="typeError" class="w-full text-sm text-red-600 dark:text-red-400">{{ typeError }}</p>
      </form>
    </section>

    <section v-if="profile" class="flex flex-col gap-3">
      <h2 class="text-lg font-medium">Настройки расписания</h2>

      <div class="flex flex-col gap-2">
        <label class="flex items-center gap-2 text-sm" :class="{ 'opacity-50': !hasActiveIndividualType }">
          <input v-model="profile.allow_individual_bookings" type="checkbox" :disabled="!hasActiveIndividualType" />
          Разрешить запись на индивидуальные занятия
        </label>
        <p v-if="!hasActiveIndividualType" class="pl-6 text-xs text-slate-400">
          Нет ни одного активного типа занятия «индивидуальное» — добавьте его выше.
        </p>
        <label class="flex items-center gap-2 text-sm" :class="{ 'opacity-50': !hasActiveGroupType }">
          <input v-model="profile.allow_group_bookings" type="checkbox" :disabled="!hasActiveGroupType" />
          Разрешить запись на групповые занятия
        </label>
        <p v-if="!hasActiveGroupType" class="pl-6 text-xs text-slate-400">
          Нет ни одного активного типа занятия «групповое» — добавьте его выше.
        </p>
      </div>

      <div class="grid grid-cols-2 gap-3 text-sm">
        <label class="flex flex-col gap-1">
          Шаг сетки, мин
          <select v-model.number="profile.slot_granularity_minutes" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700">
            <option :value="10">10</option>
            <option :value="15">15</option>
            <option :value="20">20</option>
            <option :value="30">30</option>
          </select>
        </label>
        <label class="flex flex-col gap-1">
          Перерыв между занятиями, мин
          <input v-model.number="profile.break_between_lessons_minutes" type="number" min="0" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1">
          Мин. запас времени перед записью, ч
          <input v-model.number="profile.min_lead_time_hours" type="number" min="0" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        </label>
      </div>
      <div class="flex items-center gap-3">
        <button type="button" :disabled="isSavingSettings" class="w-fit rounded-md bg-brand-500 px-4 py-2 text-sm text-white disabled:opacity-50" @click="saveSettings">
          Сохранить настройки
        </button>
        <span v-if="settingsSavedMessage" class="text-sm text-green-600 dark:text-green-400">{{ settingsSavedMessage }}</span>
      </div>
    </section>

    <section class="flex flex-col gap-4">
      <h2 class="text-lg font-medium">Рабочие интервалы</h2>
      <p class="text-sm text-slate-500">
        Расписание отображается по МСК. Границы интервалов должны быть кратны шагу сетки выше.
      </p>
      <div v-for="(name, weekday) in weekdayNames" :key="weekday" class="rounded-md border border-slate-200 p-3 dark:border-slate-800">
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ name }}</span>
          <button type="button" class="text-xs text-slate-500 underline" @click="addInterval(weekday)">+ интервал</button>
        </div>
        <div
          v-for="(interval, index) in intervals.filter((i) => i.weekday === weekday)"
          :key="index"
          class="mt-2 flex items-center gap-2 text-sm"
        >
          <input v-model="interval.start_time" type="time" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
          <span>—</span>
          <input v-model="interval.end_time" type="time" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
          <button type="button" class="text-xs text-red-600" @click="removeInterval(intervals.indexOf(interval))">Удалить</button>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button type="button" :disabled="isSaving" class="w-fit rounded-md bg-brand-500 px-4 py-2 text-sm text-white disabled:opacity-50" @click="save">
          Сохранить расписание
        </button>
        <span v-if="savedMessage" class="text-sm text-green-600 dark:text-green-400">{{ savedMessage }}</span>
      </div>
    </section>
  </div>
</template>
