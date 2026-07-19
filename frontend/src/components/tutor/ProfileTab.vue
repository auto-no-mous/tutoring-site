<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { listSubjects } from "@/api/subjects";
import { getMyProfile, getMySubjects, replaceMySubjects, updateMyProfile, uploadMyPhoto } from "@/api/tutors";
import type { Subject } from "@/types/subject";
import type { TutorProfile } from "@/types/tutor";

const profile = ref<TutorProfile | null>(null);
const isSaving = ref(false);
const savedMessage = ref("");

const allSubjects = ref<Subject[]>([]);
const checkedSubjects = reactive(new Set<string>());
const checkedDirections = reactive(new Map<string, Set<string>>());
const isSavingSubjects = ref(false);
const subjectsSavedMessage = ref("");

async function load(): Promise<void> {
  const [profileData, subjectsData, mySubjectsData] = await Promise.all([
    getMyProfile(),
    listSubjects(),
    getMySubjects(),
  ]);
  profile.value = profileData;
  allSubjects.value = subjectsData;
  for (const entry of mySubjectsData) {
    checkedSubjects.add(entry.subject_id);
    checkedDirections.set(entry.subject_id, new Set(entry.directions.map((d) => d.id)));
  }
}

function toggleSubject(subjectId: string): void {
  if (checkedSubjects.has(subjectId)) {
    checkedSubjects.delete(subjectId);
    checkedDirections.delete(subjectId);
  } else {
    checkedSubjects.add(subjectId);
    checkedDirections.set(subjectId, new Set());
  }
}

function toggleDirection(subjectId: string, directionId: string): void {
  const set = checkedDirections.get(subjectId) ?? new Set<string>();
  if (set.has(directionId)) {
    set.delete(directionId);
  } else {
    set.add(directionId);
  }
  checkedDirections.set(subjectId, set);
}

async function saveSubjects(): Promise<void> {
  isSavingSubjects.value = true;
  subjectsSavedMessage.value = "";
  try {
    await replaceMySubjects(
      [...checkedSubjects].map((subjectId) => ({
        subject_id: subjectId,
        direction_ids: [...(checkedDirections.get(subjectId) ?? [])],
      })),
    );
    subjectsSavedMessage.value = "Сохранено";
  } finally {
    isSavingSubjects.value = false;
  }
}

async function save(): Promise<void> {
  if (!profile.value) return;
  isSaving.value = true;
  savedMessage.value = "";
  try {
    profile.value = await updateMyProfile({
      about: profile.value.about,
      achievements: profile.value.achievements,
      is_hidden: profile.value.is_hidden,
    });
    savedMessage.value = "Сохранено";
  } finally {
    isSaving.value = false;
  }
}

async function onPhotoChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  profile.value = await uploadMyPhoto(file);
}

onMounted(load);
</script>

<template>
  <div v-if="profile" class="flex max-w-xl flex-col gap-8">
    <section class="flex flex-col gap-4">
      <div class="flex items-center gap-4">
        <img v-if="profile.photo_url" :src="profile.photo_url" alt="" class="h-20 w-20 rounded-full object-cover" />
        <div v-else class="h-20 w-20 rounded-full bg-slate-200 dark:bg-slate-800"></div>
        <input type="file" accept="image/*" @change="onPhotoChange" />
      </div>

      <label class="flex flex-col gap-1 text-sm">
        О себе
        <textarea v-model="profile.about" rows="4" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"></textarea>
      </label>

      <label class="flex flex-col gap-1 text-sm">
        Достижения
        <textarea v-model="profile.achievements" rows="3" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"></textarea>
      </label>

      <label class="flex items-center gap-2 text-sm">
        <input v-model="profile.is_hidden" type="checkbox" />
        Скрыть анкету из каталога (доступна только по прямой ссылке)
      </label>

      <div class="flex items-center gap-3">
        <button type="button" :disabled="isSaving" class="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-slate-900" @click="save">
          Сохранить
        </button>
        <span v-if="savedMessage" class="text-sm text-green-600 dark:text-green-400">{{ savedMessage }}</span>
      </div>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-lg font-medium">Предметы и направления подготовки</h2>
      <p class="text-sm text-slate-500">Отметьте предметы, которые вы ведёте, и направления по каждому из них.</p>

      <div v-if="allSubjects.length === 0" class="text-sm text-slate-400">
        Список предметов пока пуст — обратитесь к администратору.
      </div>
      <div v-for="subject in allSubjects" :key="subject.id" class="rounded-md border border-slate-200 p-3 dark:border-slate-800">
        <label class="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" :checked="checkedSubjects.has(subject.id)" @change="toggleSubject(subject.id)" />
          {{ subject.name }}
        </label>
        <div v-if="checkedSubjects.has(subject.id) && subject.directions.length > 0" class="mt-2 flex flex-wrap gap-3 pl-6">
          <label v-for="direction in subject.directions" :key="direction.id" class="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              :checked="checkedDirections.get(subject.id)?.has(direction.id) ?? false"
              @change="toggleDirection(subject.id, direction.id)"
            />
            {{ direction.name }}
          </label>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button
          type="button"
          :disabled="isSavingSubjects"
          class="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"
          @click="saveSubjects"
        >
          Сохранить предметы
        </button>
        <span v-if="subjectsSavedMessage" class="text-sm text-green-600 dark:text-green-400">{{ subjectsSavedMessage }}</span>
      </div>
    </section>
  </div>
</template>
