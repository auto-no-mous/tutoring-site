<script setup lang="ts">
import { Eye, EyeOff, Pencil, Plus, Trash2 } from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";

import {
  createBlogPost,
  deleteBlogPost,
  listBlogPostsAdmin,
  updateBlogPost,
  uploadBlogImage,
} from "@/api/admin";
import RichTextEditor from "@/components/RichTextEditor.vue";
import { useToastStore } from "@/stores/toast";
import type { BlogPostAdmin, BlogPostPayload } from "@/types/blog";
import { formatArticleDate } from "@/utils/time";

const toast = useToastStore();

const posts = ref<BlogPostAdmin[]>([]);
const isLoading = ref(true);
const error = ref("");

// null - форма закрыта, "" - создаём новую статью, id - редактируем существующую.
const editingId = ref<string | null>(null);
const form = ref<BlogPostPayload>(emptyForm());
const isSaving = ref(false);

function emptyForm(): BlogPostPayload {
  return { title: "", body: "", summary: "", cover_image_url: null, slug: null, is_published: false };
}

const isEditing = computed(() => editingId.value !== null);

async function load(): Promise<void> {
  posts.value = await listBlogPostsAdmin();
}

function startCreate(): void {
  editingId.value = "";
  form.value = emptyForm();
  error.value = "";
}

function startEdit(post: BlogPostAdmin): void {
  editingId.value = post.id;
  form.value = {
    title: post.title,
    body: post.body,
    summary: post.summary,
    cover_image_url: post.cover_image_url,
    slug: post.slug,
    is_published: post.is_published,
  };
  error.value = "";
}

function cancel(): void {
  editingId.value = null;
  error.value = "";
}

async function save(): Promise<void> {
  error.value = "";
  if (!form.value.title.trim()) {
    error.value = "Заголовок обязателен.";
    return;
  }
  isSaving.value = true;
  try {
    if (editingId.value) {
      await updateBlogPost(editingId.value, form.value);
    } else {
      await createBlogPost(form.value);
    }
    editingId.value = null;
    await load();
    toast.show("Статья сохранена");
  } catch {
    error.value = "Не удалось сохранить статью.";
  } finally {
    isSaving.value = false;
  }
}

// Публикация и снятие с публикации - прямо из списка, без открытия формы: это самое
// частое действие над уже написанной статьёй.
async function togglePublished(post: BlogPostAdmin): Promise<void> {
  await updateBlogPost(post.id, { is_published: !post.is_published });
  await load();
  toast.show(post.is_published ? "Статья снята с публикации" : "Статья опубликована");
}

async function remove(post: BlogPostAdmin): Promise<void> {
  if (!window.confirm(`Удалить статью «${post.title}»? Это действие необратимо.`)) return;
  await deleteBlogPost(post.id);
  if (editingId.value === post.id) editingId.value = null;
  await load();
  toast.show("Статья удалена");
}

async function onCoverSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  try {
    form.value.cover_image_url = await uploadBlogImage(file);
  } catch {
    error.value = "Не удалось загрузить обложку.";
  }
}

onMounted(async () => {
  try {
    await load();
  } finally {
    isLoading.value = false;
  }
});
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-xl font-semibold">Блог</h2>
      <button v-if="!isEditing" type="button" class="btn-primary text-sm" @click="startCreate">
        <Plus class="h-4 w-4" />
        Новая статья
      </button>
    </div>

    <form v-if="isEditing" class="surface-card animate-pop-in mt-4 flex flex-col gap-3 p-5" @submit.prevent="save">
      <h3 class="text-lg font-semibold">{{ editingId ? "Редактирование статьи" : "Новая статья" }}</h3>

      <label class="text-sm font-medium">
        Заголовок
        <input
          v-model="form.title"
          required
          maxlength="255"
          class="mt-1 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        />
      </label>

      <label class="text-sm font-medium">
        Адрес статьи
        <input
          v-model="form.slug"
          maxlength="64"
          placeholder="Оставьте пустым — соберётся из заголовка"
          class="mt-1 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 font-mono text-sm dark:border-slate-700"
        />
        <span class="mt-1 block text-xs font-normal text-slate-500 dark:text-slate-400">
          Статья будет доступна по адресу /blog/{{ form.slug || "…" }}
        </span>
      </label>

      <label class="text-sm font-medium">
        Краткое описание
        <textarea
          v-model="form.summary"
          rows="2"
          maxlength="400"
          placeholder="Оставьте пустым — возьмётся начало статьи"
          class="mt-1 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        ></textarea>
        <span class="mt-1 block text-xs font-normal text-slate-500 dark:text-slate-400">
          Показывается в карточке на главной и в описании страницы для поисковиков.
        </span>
      </label>

      <div class="text-sm font-medium">
        Обложка
        <div class="mt-1 flex flex-wrap items-center gap-3">
          <img v-if="form.cover_image_url" :src="form.cover_image_url" alt="" class="h-20 w-32 rounded-lg object-cover" />
          <input type="file" accept="image/*" class="text-sm font-normal" @change="onCoverSelected" />
          <button
            v-if="form.cover_image_url"
            type="button"
            class="text-sm font-normal text-slate-500 hover:text-red-600"
            @click="form.cover_image_url = null"
          >
            Убрать
          </button>
        </div>
      </div>

      <div class="text-sm font-medium">
        Текст статьи
        <div class="mt-1">
          <RichTextEditor v-model="form.body" :upload-image="uploadBlogImage" />
        </div>
      </div>

      <label class="flex items-center gap-2 text-sm">
        <input v-model="form.is_published" type="checkbox" />
        Опубликовать (снятая галочка — черновик, виден только здесь)
      </label>

      <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>

      <div class="flex gap-3">
        <button type="submit" class="btn-primary text-sm" :disabled="isSaving">
          {{ isSaving ? "Сохраняем…" : "Сохранить" }}
        </button>
        <button type="button" class="btn-outline text-sm" @click="cancel">Отмена</button>
      </div>
    </form>

    <p v-if="isLoading" class="mt-6 text-base text-slate-400">Загрузка…</p>
    <p v-else-if="posts.length === 0" class="mt-6 text-base text-slate-400">Статей пока нет.</p>

    <div v-else class="mt-6 flex flex-col gap-3">
      <div v-for="post in posts" :key="post.id" class="surface-card flex flex-wrap items-center gap-4 p-4">
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <span class="font-semibold">{{ post.title }}</span>
            <span
              class="rounded-full px-2 py-0.5 text-xs font-medium"
              :class="
                post.is_published
                  ? 'bg-brand-50 text-brand-800 dark:bg-brand-900/40 dark:text-brand-200'
                  : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
              "
            >
              {{ post.is_published ? "Опубликована" : "Черновик" }}
            </span>
          </div>
          <div class="mt-1 truncate text-sm text-slate-500 dark:text-slate-400">
            /blog/{{ post.slug }}
            <template v-if="post.published_at"> · {{ formatArticleDate(post.published_at) }}</template>
          </div>
        </div>
        <div class="flex shrink-0 gap-2">
          <RouterLink
            v-if="post.is_published"
            :to="`/blog/${post.slug}`"
            target="_blank"
            class="btn-outline px-3 py-1.5 text-sm"
          >
            Открыть
          </RouterLink>
          <button
            type="button"
            class="btn-outline px-3 py-1.5 text-sm"
            :title="post.is_published ? 'Снять с публикации' : 'Опубликовать'"
            @click="togglePublished(post)"
          >
            <EyeOff v-if="post.is_published" class="h-4 w-4" />
            <Eye v-else class="h-4 w-4" />
          </button>
          <button type="button" class="btn-outline px-3 py-1.5 text-sm" title="Редактировать" @click="startEdit(post)">
            <Pencil class="h-4 w-4" />
          </button>
          <button
            type="button"
            class="btn-outline px-3 py-1.5 text-sm hover:border-red-300 hover:text-red-600"
            title="Удалить"
            @click="remove(post)"
          >
            <Trash2 class="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
