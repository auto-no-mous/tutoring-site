<script setup lang="ts">
import axios from "axios";
import { onMounted, ref } from "vue";

import { deleteTutor, listTutors, updateTutor } from "@/api/admin";
import ResetPasswordButton from "@/components/admin/ResetPasswordButton.vue";
import RichTextEditor from "@/components/RichTextEditor.vue";
import type { TutorProfile } from "@/types/tutor";
import { sanitizeRichText } from "@/utils/richText";

const tutors = ref<TutorProfile[]>([]);
const editingId = ref<string | null>(null);

const editLastName = ref("");
const editFirstName = ref("");
const editPatronymic = ref("");
const editEmail = ref("");
const editAbout = ref("");
const editIsHidden = ref(false);
const editCancelMinHours = ref(0);
const editCancelMaxPerMonth = ref(0);
const editRescheduleMinHours = ref(0);
const editRescheduleMaxPerMonth = ref(0);
const error = ref("");

async function load(): Promise<void> {
  tutors.value = await listTutors();
}

function aboutPreview(tutor: TutorProfile): string {
  return tutor.about ? sanitizeRichText(tutor.about) : "";
}

function startEdit(tutor: TutorProfile): void {
  editingId.value = tutor.id;
  editLastName.value = tutor.last_name ?? "";
  editFirstName.value = tutor.first_name ?? "";
  editPatronymic.value = tutor.patronymic ?? "";
  editEmail.value = tutor.email ?? "";
  editAbout.value = tutor.about;
  editIsHidden.value = tutor.is_hidden;
  editCancelMinHours.value = tutor.cancel_min_hours_before;
  editCancelMaxPerMonth.value = tutor.cancel_max_per_month;
  editRescheduleMinHours.value = tutor.reschedule_min_hours_before;
  editRescheduleMaxPerMonth.value = tutor.reschedule_max_per_month;
  error.value = "";
}

function cancelEdit(): void {
  editingId.value = null;
}

async function saveEdit(tutor: TutorProfile): Promise<void> {
  error.value = "";
  try {
    await updateTutor(tutor.id, {
      last_name: editLastName.value,
      first_name: editFirstName.value,
      patronymic: editPatronymic.value || null,
      email: editEmail.value || undefined,
      about: editAbout.value,
      is_hidden: editIsHidden.value,
      cancel_min_hours_before: editCancelMinHours.value,
      cancel_max_per_month: editCancelMaxPerMonth.value,
      reschedule_min_hours_before: editRescheduleMinHours.value,
      reschedule_max_per_month: editRescheduleMaxPerMonth.value,
    });
    editingId.value = null;
    await load();
  } catch (err) {
    error.value =
      axios.isAxiosError(err) && err.response?.status === 409 ? "Эта почта уже используется другим аккаунтом" : "Не удалось сохранить";
  }
}

async function toggleActive(tutor: TutorProfile): Promise<void> {
  await updateTutor(tutor.id, { is_active: !tutor.is_active });
  await load();
}

async function remove(tutor: TutorProfile): Promise<void> {
  if (!window.confirm(`Удалить репетитора «${tutor.display_name}» безвозвратно?`)) return;
  await deleteTutor(tutor.id);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex flex-col gap-2">
    <div v-for="tutor in tutors" :key="tutor.id" class="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
      <template v-if="editingId === tutor.id">
        <div class="flex flex-col gap-3">
          <div class="flex flex-wrap gap-2">
            <label class="flex flex-col gap-1 text-xs">
              Фамилия
              <input v-model="editLastName" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Имя
              <input v-model="editFirstName" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Отчество
              <input v-model="editPatronymic" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1 text-xs">
              Почта
              <input v-model="editEmail" type="email" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
          </div>

          <div class="flex flex-col gap-1 text-xs">
            О себе
            <RichTextEditor v-model="editAbout" />
          </div>

          <label class="flex items-center gap-2 text-xs">
            <input v-model="editIsHidden" type="checkbox" />
            Скрыть анкету из каталога
          </label>

          <div class="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <label class="flex flex-col gap-1">
              Отмена не позднее, ч
              <input v-model.number="editCancelMinHours" type="number" min="0" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1">
              Лимит отмен в месяц
              <input v-model.number="editCancelMaxPerMonth" type="number" min="0" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1">
              Перенос не позднее, ч
              <input v-model.number="editRescheduleMinHours" type="number" min="0" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
            <label class="flex flex-col gap-1">
              Лимит переносов в месяц
              <input v-model.number="editRescheduleMaxPerMonth" type="number" min="0" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" />
            </label>
          </div>

          <p v-if="error" class="text-xs text-red-600 dark:text-red-400">{{ error }}</p>
          <div class="flex gap-2">
            <button type="button" class="rounded-md bg-brand-500 px-3 py-1.5 text-xs text-white" @click="saveEdit(tutor)">
              Сохранить
            </button>
            <button type="button" class="rounded-md border border-slate-300 px-3 py-1.5 text-xs dark:border-slate-700" @click="cancelEdit">
              Отмена
            </button>
          </div>
        </div>
      </template>
      <div v-else class="flex items-center justify-between">
        <div>
          <div class="font-medium">
            {{ tutor.display_name }}
            <span v-if="tutor.is_active === false" class="ml-1 text-xs text-red-600 dark:text-red-400">(заблокирован)</span>
            <span v-if="tutor.is_hidden" class="ml-1 text-xs text-slate-400">(скрыт из каталога)</span>
          </div>
          <div class="text-slate-500">
            {{ tutor.email }}
            <span
              v-if="tutor.email_verified === false"
              class="ml-1 text-xs text-amber-600 dark:text-amber-400"
              title="Пользователь не переходил по ссылке из письма подтверждения"
              >почта не подтверждена</span
            >
          </div>
          <div v-if="aboutPreview(tutor)" class="mt-1 line-clamp-2 text-slate-500" v-html="aboutPreview(tutor)"></div>
          <div v-else class="mt-1 text-slate-400">—</div>
        </div>
        <div class="flex shrink-0 gap-2">
          <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="startEdit(tutor)">
            Изменить
          </button>
          <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="toggleActive(tutor)">
            {{ tutor.is_active === false ? "Разблокировать" : "Заблокировать" }}
          </button>
          <ResetPasswordButton :user-id="tutor.user_id" :display-name="tutor.display_name ?? ''" />
          <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="remove(tutor)">
            Удалить
          </button>
        </div>
      </div>
    </div>
    <p v-if="tutors.length === 0" class="text-sm text-slate-400">Репетиторов пока нет.</p>
  </div>
</template>
