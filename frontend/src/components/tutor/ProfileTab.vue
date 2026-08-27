<script setup lang="ts">
import { X } from "lucide-vue-next";
import axios from "axios";
import { computed, onMounted, reactive, ref } from "vue";

import { listSubjects } from "@/api/subjects";
import { getMyProfile, getMySubjects, replaceMySubjects, updateMyProfile, uploadAboutImage, uploadMyPhoto } from "@/api/tutors";
import RichTextEditor from "@/components/RichTextEditor.vue";
import { useAuthStore } from "@/stores/auth";
import type { Subject } from "@/types/subject";
import type { TutorExtraLink, TutorProfile } from "@/types/tutor";

const auth = useAuthStore();

const profile = ref<TutorProfile | null>(null);
const isSaving = ref(false);
const savedMessage = ref("");

const slugInput = ref("");
const isSavingSlug = ref(false);
const slugError = ref("");
const linkCopied = ref(false);

const profileUrl = computed(() => {
  if (!profile.value) return "";
  return `${window.location.origin}/tutors/${profile.value.slug ?? profile.value.id}`;
});

async function copyProfileUrl(): Promise<void> {
  await navigator.clipboard.writeText(profileUrl.value);
  linkCopied.value = true;
  setTimeout(() => {
    linkCopied.value = false;
  }, 2000);
}

async function saveSlug(): Promise<void> {
  if (!profile.value) return;
  const nextSlug = slugInput.value.trim() || null;
  if (nextSlug === profile.value.slug) return;
  if (
    profile.value.slug &&
    !window.confirm("Ссылка на ваш профиль изменится, старая ссылка перестанет работать. Продолжить?")
  ) {
    return;
  }
  slugError.value = "";
  isSavingSlug.value = true;
  try {
    profile.value = await updateMyProfile({ slug: nextSlug });
    slugInput.value = profile.value.slug ?? "";
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 409) {
      slugError.value = "Этот ник уже занят другим репетитором";
    } else if (axios.isAxiosError(err) && err.response?.status === 422) {
      slugError.value = "Ник может содержать только строчные латинские буквы, цифры и дефис (3-64 символа)";
    } else {
      slugError.value = "Не удалось сохранить ник";
    }
  } finally {
    isSavingSlug.value = false;
  }
}

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
  slugInput.value = profileData.slug ?? "";
  telegramInput.value = profileData.telegram_url ?? "";
  vkInput.value = profileData.vk_url ?? "";
  youtubeInput.value = profileData.youtube_url ?? "";
  videoInput.value = profileData.video_url ?? "";
  extraLinksInput.splice(0, extraLinksInput.length, ...profileData.extra_links);
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

const telegramInput = ref("");
const vkInput = ref("");
const youtubeInput = ref("");
const videoInput = ref("");
const extraLinksInput = reactive<TutorExtraLink[]>([]);
const saveError = ref("");

function addExtraLink(): void {
  extraLinksInput.push({ label: "", url: "" });
}

function removeExtraLink(index: number): void {
  extraLinksInput.splice(index, 1);
}

async function save(): Promise<void> {
  if (!profile.value) return;
  isSaving.value = true;
  savedMessage.value = "";
  saveError.value = "";
  try {
    profile.value = await updateMyProfile({
      about: profile.value.about,
      is_hidden: profile.value.is_hidden,
      telegram_url: telegramInput.value.trim() || null,
      vk_url: vkInput.value.trim() || null,
      youtube_url: youtubeInput.value.trim() || null,
      video_url: videoInput.value.trim() || null,
      extra_links: extraLinksInput
        .map((link) => ({ label: link.label.trim(), url: link.url.trim() }))
        .filter((link) => link.label && link.url),
    });
    telegramInput.value = profile.value.telegram_url ?? "";
    vkInput.value = profile.value.vk_url ?? "";
    youtubeInput.value = profile.value.youtube_url ?? "";
    videoInput.value = profile.value.video_url ?? "";
    extraLinksInput.splice(0, extraLinksInput.length, ...profile.value.extra_links);
    savedMessage.value = "Сохранено";
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 422) {
      saveError.value = videoInput.value.trim()
        ? "Проверьте ссылки: обычные должны начинаться с http:// или https://, а видео — быть ссылкой на ролик с YouTube, RuTube или VK Видео"
        : "Проверьте правильность ссылок — они должны начинаться с http:// или https://";
    } else {
      saveError.value = "Не удалось сохранить профиль";
    }
  } finally {
    isSaving.value = false;
  }
}

async function onPhotoChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  profile.value = await uploadMyPhoto(file);
  auth.setTutorPhotoUrl(profile.value.photo_url);
}

onMounted(load);
</script>

<template>
  <div v-if="profile" class="flex max-w-xl flex-col gap-8">
    <section class="flex flex-col gap-4">
      <div class="flex items-center gap-4">
        <img v-if="profile.photo_url" :src="profile.photo_url" alt="" class="h-20 w-20 rounded-md object-cover" />
        <div v-else class="h-20 w-20 rounded-md bg-slate-200 dark:bg-slate-800"></div>
        <input
          type="file"
          accept="image/*"
          class="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-brand-500 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700 dark:file:bg-white dark:file:text-slate-900 dark:hover:file:bg-slate-200"
          @change="onPhotoChange"
        />
      </div>

      <div class="flex flex-col gap-2 text-sm">
        Ссылка на мой профиль
        <div class="flex items-center gap-2">
          <input
            :value="profileUrl"
            readonly
            class="flex-1 rounded-md border border-slate-300 bg-slate-50 px-2 py-1.5 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-800"
          />
          <button
            type="button"
            title="Скопировать ссылку"
            class="shrink-0 rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
            @click="copyProfileUrl"
          >
            {{ linkCopied ? "✓ Скопировано" : "📋 Копировать" }}
          </button>
        </div>
        <div class="mt-1 flex flex-wrap items-end gap-2">
          <label class="flex flex-col gap-1 text-xs">
            Ник (для красивой ссылки, необязательно)
            <input
              v-model="slugInput"
              placeholder="например, smoke-tutor"
              class="w-56 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700"
            />
          </label>
          <button
            type="button"
            :disabled="isSavingSlug"
            class="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-slate-700"
            @click="saveSlug"
          >
            Сохранить ник
          </button>
        </div>
        <p v-if="slugError" class="text-xs text-red-600 dark:text-red-400">{{ slugError }}</p>
      </div>

      <div class="flex flex-col gap-3 text-sm">
        <span class="font-medium">Контакты и соцсети</span>
        <p class="text-xs text-slate-500">Будут показаны на вашей публичной странице как иконки-ссылки.</p>
        <label class="flex flex-col gap-1 text-xs">
          Telegram
          <input
            v-model="telegramInput"
            type="url"
            placeholder="https://t.me/username"
            class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700"
          />
        </label>
        <label class="flex flex-col gap-1 text-xs">
          ВКонтакте
          <input
            v-model="vkInput"
            type="url"
            placeholder="https://vk.com/username"
            class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700"
          />
        </label>
        <label class="flex flex-col gap-1 text-xs">
          YouTube
          <input
            v-model="youtubeInput"
            type="url"
            placeholder="https://youtube.com/@username"
            class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700"
          />
        </label>

        <div class="flex flex-col gap-2">
          <div v-for="(link, index) in extraLinksInput" :key="index" class="flex items-end gap-2">
            <label class="flex flex-col gap-1 text-xs">
              Название
              <input
                v-model="link.label"
                placeholder="например, Личный сайт"
                class="w-40 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700"
              />
            </label>
            <label class="flex flex-1 flex-col gap-1 text-xs">
              Ссылка
              <input
                v-model="link.url"
                type="url"
                placeholder="https://…"
                class="w-full rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700"
              />
            </label>
            <button
              type="button"
              title="Удалить ссылку"
              class="shrink-0 rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
              @click="removeExtraLink(index)"
            >
              <X class="h-4 w-4" />
            </button>
          </div>
          <button
            v-if="extraLinksInput.length < 10"
            type="button"
            class="w-fit rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
            @click="addExtraLink"
          >
            + Добавить ссылку
          </button>
        </div>
      </div>

      <div class="flex flex-col gap-2 text-sm">
        <span class="font-medium">Видео на странице</span>
        <p class="text-xs text-slate-500">
          Ролик с YouTube, RuTube или VK Видео — будет встроен в вашу публичную страницу под описанием.
          Вставьте обычную ссылку на видео, например https://youtu.be/xxxxxxxxxxx. Оставьте поле пустым, чтобы убрать видео.
        </p>
        <input
          v-model="videoInput"
          type="url"
          placeholder="https://youtu.be/…, https://rutube.ru/video/… или https://vk.com/video-…"
          class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700"
        />
      </div>

      <div class="flex flex-col gap-1 text-sm">
        О себе
        <RichTextEditor v-model="profile.about" :upload-image="uploadAboutImage" />
      </div>

      <label class="flex items-center gap-2 text-sm">
        <input v-model="profile.is_hidden" type="checkbox" />
        Скрыть анкету из каталога (доступна только по прямой ссылке)
      </label>

      <div class="flex items-center gap-3">
        <button type="button" :disabled="isSaving" class="w-fit rounded-md bg-brand-500 px-4 py-2 text-sm text-white disabled:opacity-50" @click="save">
          Сохранить
        </button>
        <span v-if="savedMessage" class="text-sm text-green-600 dark:text-green-400">{{ savedMessage }}</span>
        <span v-if="saveError" class="text-sm text-red-600 dark:text-red-400">{{ saveError }}</span>
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
          class="w-fit rounded-md bg-brand-500 px-4 py-2 text-sm text-white disabled:opacity-50"
          @click="saveSubjects"
        >
          Сохранить предметы
        </button>
        <span v-if="subjectsSavedMessage" class="text-sm text-green-600 dark:text-green-400">{{ subjectsSavedMessage }}</span>
      </div>
    </section>
  </div>
</template>
