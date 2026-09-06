<script setup lang="ts">
import { ImagePlus, X } from "lucide-vue-next";
import { computed, onBeforeUnmount, ref, watch } from "vue";

// Ученик чаще всего сдаёт домашку скриншотом, а скриншот живёт в буфере обмена, а не
// файлом на диске. Поэтому зона принимает три способа сразу: клик по ней открывает
// обычный выбор файла, файл можно перетащить, а можно просто нажать на зону и
// вставить из буфера - Ctrl+V срабатывает, пока зона в фокусе.
const props = defineProps<{ modelValue: File | null; disabled?: boolean; accept?: string }>();
const emit = defineEmits<{ "update:modelValue": [File | null] }>();

const input = ref<HTMLInputElement | null>(null);
const isDragging = ref(false);
const previewUrl = ref<string | null>(null);

const isImage = computed(() => props.modelValue?.type.startsWith("image/") ?? false);

// Превью держим на objectURL и обязательно отзываем: иначе каждый вставленный
// скриншот остаётся висеть в памяти вкладки до перезагрузки.
watch(
  () => props.modelValue,
  (file) => {
    if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = file && file.type.startsWith("image/") ? URL.createObjectURL(file) : null;
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
});

function pick(file: File | null | undefined): void {
  if (props.disabled || !file) return;
  emit("update:modelValue", file);
}

function onDrop(event: DragEvent): void {
  isDragging.value = false;
  pick(event.dataTransfer?.files?.[0]);
}

function onPaste(event: ClipboardEvent): void {
  const items = Array.from(event.clipboardData?.items ?? []);
  const image = items.find((item) => item.kind === "file" && item.type.startsWith("image/"));
  const file = image?.getAsFile() ?? event.clipboardData?.files?.[0] ?? null;
  if (!file) return;

  // У картинки из буфера имени может не быть вовсе - подставляем своё, чтобы файл
  // не уехал на сервер безымянным. Расширение сервер всё равно берёт из типа.
  const named =
    file.name && file.name !== "image.png"
      ? file
      : new File([file], `screenshot-${Date.now()}.${file.type.split("/")[1] || "png"}`, {
          type: file.type,
        });
  pick(named);
  event.preventDefault();
}

function clear(): void {
  emit("update:modelValue", null);
  if (input.value) input.value.value = "";
}

function humanSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} КБ`
    : `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div
      class="flex cursor-pointer items-center gap-3 rounded-md border border-dashed px-3 py-2 text-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
      :class="[
        isDragging
          ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/30'
          : 'border-slate-300 hover:border-brand-400 dark:border-slate-700',
        disabled ? 'cursor-not-allowed opacity-50' : '',
      ]"
      tabindex="0"
      role="button"
      @click="!disabled && input?.click()"
      @keydown.enter.prevent="!disabled && input?.click()"
      @keydown.space.prevent="!disabled && input?.click()"
      @dragover.prevent="isDragging = !disabled"
      @dragleave="isDragging = false"
      @drop.prevent="onDrop"
      @paste="onPaste"
    >
      <img v-if="previewUrl" :src="previewUrl" alt="" class="h-12 w-12 rounded object-cover" />
      <ImagePlus v-else class="h-5 w-5 shrink-0 text-slate-400" />

      <div class="flex min-w-0 flex-col">
        <template v-if="modelValue">
          <span class="truncate font-medium">{{ modelValue.name }}</span>
          <span class="text-slate-400">
            {{ humanSize(modelValue.size) }}{{ isImage ? "" : " · не изображение" }}
          </span>
        </template>
        <template v-else>
          <span>Перетащите файл, вставьте скриншот (Ctrl+V) или выберите на диске</span>
          <span class="text-slate-400">Скриншот вставляется прямо из буфера — нажмите сюда и Ctrl+V</span>
        </template>
      </div>

      <button
        v-if="modelValue"
        type="button"
        class="ml-auto shrink-0 rounded p-1 text-slate-400 hover:text-red-600"
        title="Убрать файл"
        @click.stop="clear"
      >
        <X class="h-4 w-4" />
      </button>
    </div>

    <input
      ref="input"
      type="file"
      class="hidden"
      :accept="accept"
      :disabled="disabled"
      @change="pick(($event.target as HTMLInputElement).files?.[0])"
    />
  </div>
</template>
