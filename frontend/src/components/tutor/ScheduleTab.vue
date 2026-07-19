<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getMyAvailability, getMyProfile, replaceMyAvailability, updateMyProfile } from "@/api/tutors";
import type { TutorProfile } from "@/types/tutor";

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

async function load(): Promise<void> {
  const [rows, profileData] = await Promise.all([getMyAvailability(), getMyProfile()]);
  intervals.value = rows.map((r) => ({ weekday: r.weekday, start_time: r.start_time.slice(0, 5), end_time: r.end_time.slice(0, 5) }));
  profile.value = profileData;
}

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
    <section v-if="profile" class="flex flex-col gap-3">
      <h2 class="text-lg font-medium">Настройки расписания</h2>
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
        <button type="button" :disabled="isSavingSettings" class="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-slate-900" @click="saveSettings">
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
        <button type="button" :disabled="isSaving" class="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-slate-900" @click="save">
          Сохранить расписание
        </button>
        <span v-if="savedMessage" class="text-sm text-green-600 dark:text-green-400">{{ savedMessage }}</span>
      </div>
    </section>
  </div>
</template>
