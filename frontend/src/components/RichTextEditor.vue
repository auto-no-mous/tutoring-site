<script setup lang="ts">
import { onMounted, ref, watch } from "vue";

import { IMG_ALIGN_CLASSES, sanitizeRichText } from "@/utils/richText";

const props = defineProps<{ modelValue: string; uploadImage?: (file: File) => Promise<string> }>();
const emit = defineEmits<{ "update:modelValue": [string] }>();

const editorRef = ref<HTMLDivElement | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const activeImage = ref<HTMLImageElement | null>(null);
const isUploading = ref(false);
const uploadError = ref("");
let skipNextExternalSync = false;

function emitSanitized(): void {
  if (!editorRef.value) return;
  const clean = sanitizeRichText(editorRef.value.innerHTML);
  skipNextExternalSync = true;
  emit("update:modelValue", clean);
}

function exec(command: string, value?: string): void {
  editorRef.value?.focus();
  document.execCommand(command, false, value);
  emitSanitized();
}

function insertLink(): void {
  const url = window.prompt("Ссылка (https://…)");
  if (!url) return;
  exec("createLink", url);
}

function clearActiveImageOutline(): void {
  if (activeImage.value) activeImage.value.style.outline = "";
}

function onEditorClick(event: MouseEvent): void {
  clearActiveImageOutline();
  const target = event.target;
  if (target instanceof HTMLImageElement) {
    activeImage.value = target;
    target.style.outline = "2px solid #3b82f6";
  } else {
    activeImage.value = null;
  }
}

function setAlignment(align: (typeof IMG_ALIGN_CLASSES)[number]): void {
  if (!activeImage.value) return;
  activeImage.value.classList.remove(...IMG_ALIGN_CLASSES);
  activeImage.value.classList.add(align);
  emitSanitized();
}

function triggerImagePicker(): void {
  fileInputRef.value?.click();
}

async function onImageSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || !props.uploadImage) return;

  uploadError.value = "";
  isUploading.value = true;
  try {
    const url = await props.uploadImage(file);
    editorRef.value?.focus();
    const marker = `rt-pending-${Date.now()}`;
    document.execCommand("insertHTML", false, `<img src="${url}" data-marker="${marker}" class="rt-img-center">`);
    const inserted = editorRef.value?.querySelector<HTMLImageElement>(`img[data-marker="${marker}"]`);
    inserted?.removeAttribute("data-marker");
    emitSanitized();
  } catch {
    uploadError.value = "Не удалось загрузить изображение";
  } finally {
    isUploading.value = false;
  }
}

onMounted(() => {
  if (editorRef.value) editorRef.value.innerHTML = props.modelValue;
});

watch(
  () => props.modelValue,
  (value) => {
    if (skipNextExternalSync) {
      skipNextExternalSync = false;
      return;
    }
    if (editorRef.value && editorRef.value.innerHTML !== value) {
      editorRef.value.innerHTML = value;
    }
  },
);
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="flex flex-wrap gap-1">
      <button type="button" title="Жирный" class="w-8 rounded-md border border-slate-300 py-1 text-sm font-bold dark:border-slate-700" @click="exec('bold')">Ж</button>
      <button type="button" title="Курсив" class="w-8 rounded-md border border-slate-300 py-1 text-sm italic dark:border-slate-700" @click="exec('italic')">К</button>
      <button type="button" title="Подчёркнутый" class="w-8 rounded-md border border-slate-300 py-1 text-sm underline dark:border-slate-700" @click="exec('underline')">Ч</button>
      <button type="button" title="Заголовок" class="w-8 rounded-md border border-slate-300 py-1 text-sm font-semibold dark:border-slate-700" @click="exec('formatBlock', 'H2')">H</button>
      <button type="button" title="Список" class="w-8 rounded-md border border-slate-300 py-1 text-sm dark:border-slate-700" @click="exec('insertUnorderedList')">•≡</button>
      <button type="button" title="Вставить ссылку" class="rounded-md border border-slate-300 px-2 py-1 text-sm dark:border-slate-700" @click="insertLink">Ссылка</button>
      <button
        v-if="uploadImage"
        type="button"
        title="Вставить изображение"
        :disabled="isUploading"
        class="rounded-md border border-slate-300 px-2 py-1 text-sm disabled:opacity-50 dark:border-slate-700"
        @click="triggerImagePicker"
      >
        {{ isUploading ? "Загрузка…" : "🖼 Изображение" }}
      </button>
      <div v-if="uploadImage" class="ml-2 flex gap-1 border-l border-slate-300 pl-2 dark:border-slate-700">
        <button
          type="button"
          title="Изображение слева"
          :disabled="!activeImage"
          class="w-8 rounded-md border border-slate-300 py-1 text-sm disabled:opacity-30 dark:border-slate-700"
          @click="setAlignment('rt-img-left')"
        >
          ⇤
        </button>
        <button
          type="button"
          title="Изображение по центру"
          :disabled="!activeImage"
          class="w-8 rounded-md border border-slate-300 py-1 text-sm disabled:opacity-30 dark:border-slate-700"
          @click="setAlignment('rt-img-center')"
        >
          ⇔
        </button>
        <button
          type="button"
          title="Изображение справа"
          :disabled="!activeImage"
          class="w-8 rounded-md border border-slate-300 py-1 text-sm disabled:opacity-30 dark:border-slate-700"
          @click="setAlignment('rt-img-right')"
        >
          ⇥
        </button>
        <button
          type="button"
          title="Изображение на всю ширину"
          :disabled="!activeImage"
          class="w-8 rounded-md border border-slate-300 py-1 text-sm disabled:opacity-30 dark:border-slate-700"
          @click="setAlignment('rt-img-full')"
        >
          ⬌
        </button>
      </div>
      <input ref="fileInputRef" type="file" accept="image/*" class="hidden" @change="onImageSelected" />
    </div>
    <p v-if="uploadError" class="text-xs text-red-600 dark:text-red-400">{{ uploadError }}</p>
    <p v-if="uploadImage" class="text-xs text-slate-400">Кликните по изображению в тексте, чтобы выбрать выравнивание.</p>
    <div
      ref="editorRef"
      contenteditable="true"
      class="min-h-64 flow-root rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm focus:outline-none dark:border-slate-700"
      @input="emitSanitized"
      @blur="emitSanitized"
      @click="onEditorClick"
    ></div>
  </div>
</template>
