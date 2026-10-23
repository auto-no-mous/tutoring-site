<script lang="ts">
// Вставку слушаем на всём документе, а не на самой зоне: paste приходит только
// элементу в фокусе, а зона получала фокус лишь кликом, который тут же открывал диалог
// выбора файла. Ученики жали Ctrl+V, ничего не происходило, и срабатывало только после
// «кликнуть - закрыть диалог - вставить». Зон на странице бывает несколько (по одной на
// задание), поэтому картинка уходит в ту, внутри которой фокус, над которой курсор или
// с которой работали последней, а если ни в одну - в верхнюю, то есть в самое свежее
// задание. Вставка в текстовые поля (чат и т.п.) остаётся им.
type Zone = { el: HTMLElement; isDisabled: () => boolean; paste: (event: ClipboardEvent) => boolean };

const zones = new Set<Zone>();
let hovered: Zone | null = null;
let lastActive: Zone | null = null;

function isEditable(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || target instanceof HTMLTextAreaElement || (target instanceof HTMLInputElement && target.type !== "file"))
  );
}

function topmost(candidates: Zone[]): Zone | undefined {
  return candidates.sort((a, b) => (a.el.compareDocumentPosition(b.el) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1))[0];
}

function onDocumentPaste(event: ClipboardEvent): void {
  const enabled = [...zones].filter((zone) => zone.el.isConnected && !zone.isDisabled());
  const target = event.target instanceof Node ? event.target : null;
  const inside = enabled.find((zone) => target && zone.el.contains(target));
  if (!inside && isEditable(event.target)) return;

  const zone =
    inside ??
    (hovered && enabled.includes(hovered) ? hovered : undefined) ??
    (lastActive && enabled.includes(lastActive) ? lastActive : undefined) ??
    topmost(enabled);
  if (zone?.paste(event)) event.preventDefault();
}

function register(zone: Zone): void {
  if (zones.size === 0) document.addEventListener("paste", onDocumentPaste);
  zones.add(zone);
}

function unregister(zone: Zone): void {
  zones.delete(zone);
  if (hovered === zone) hovered = null;
  if (lastActive === zone) lastActive = null;
  if (zones.size === 0) document.removeEventListener("paste", onDocumentPaste);
}
</script>

<script setup lang="ts">
import { ImagePlus, X } from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

// Ученик чаще всего сдаёт домашку скриншотом, а скриншот живёт в буфере обмена, а не
// файлом на диске. Поэтому зона принимает три способа сразу: клик по ней открывает
// обычный выбор файла, файл можно перетащить, а можно просто нажать Ctrl+V где угодно
// на странице (как выбирается зона - см. onDocumentPaste выше).
// hideTypeHint - не писать «не изображение» под файлом: это подсказка ученику, который
// обычно сдаёт скриншот, а для материала задания (PDF, Word) она звучит странно.
const props = defineProps<{ modelValue: File | null; disabled?: boolean; accept?: string; hideTypeHint?: boolean }>();
const emit = defineEmits<{ "update:modelValue": [File | null] }>();

const input = ref<HTMLInputElement | null>(null);
const root = ref<HTMLElement | null>(null);
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

let zone: Zone | null = null;

function onPointerEnter(): void {
  hovered = zone;
}

function onPointerLeave(): void {
  if (hovered === zone) hovered = null;
}

function markActive(): void {
  lastActive = zone;
}

onMounted(() => {
  zone = { el: root.value!, isDisabled: () => Boolean(props.disabled), paste: onPaste };
  register(zone);
});

onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  if (zone) unregister(zone);
});

function pick(file: File | null | undefined): void {
  if (props.disabled || !file) return;
  emit("update:modelValue", file);
}

function onDrop(event: DragEvent): void {
  isDragging.value = false;
  markActive();
  pick(event.dataTransfer?.files?.[0]);
}

// true - файл из буфера принят.
function onPaste(event: ClipboardEvent): boolean {
  if (props.disabled) return false;
  const items = Array.from(event.clipboardData?.items ?? []);
  const image = items.find((item) => item.kind === "file" && item.type.startsWith("image/"));
  const file = image?.getAsFile() ?? event.clipboardData?.files?.[0] ?? null;
  if (!file) return false;

  // У картинки из буфера имени может не быть вовсе - подставляем своё, чтобы файл
  // не уехал на сервер безымянным. Расширение сервер всё равно берёт из типа.
  const named =
    file.name && file.name !== "image.png"
      ? file
      : new File([file], `screenshot-${Date.now()}.${file.type.split("/")[1] || "png"}`, {
          type: file.type,
        });
  markActive();
  pick(named);
  return true;
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
      ref="root"
      class="flex cursor-pointer items-center gap-3 rounded-md border border-dashed px-3 py-2 text-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
      :class="[
        isDragging
          ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/30'
          : 'border-slate-300 hover:border-brand-400 dark:border-slate-700',
        disabled ? 'cursor-not-allowed opacity-50' : '',
      ]"
      tabindex="0"
      role="button"
      @pointerenter="onPointerEnter"
      @pointerleave="onPointerLeave"
      @focusin="markActive"
      @click="!disabled && input?.click()"
      @keydown.enter.prevent="!disabled && input?.click()"
      @keydown.space.prevent="!disabled && input?.click()"
      @dragover.prevent="isDragging = !disabled"
      @dragleave="isDragging = false"
      @drop.prevent="onDrop"
    >
      <img v-if="previewUrl" :src="previewUrl" alt="" class="h-12 w-12 rounded object-cover" />
      <ImagePlus v-else class="h-5 w-5 shrink-0 text-slate-400" />

      <div class="flex min-w-0 flex-col">
        <template v-if="modelValue">
          <span class="truncate font-medium">{{ modelValue.name }}</span>
          <span class="text-slate-400">
            {{ humanSize(modelValue.size) }}{{ isImage || hideTypeHint ? "" : " · не изображение" }}
          </span>
        </template>
        <template v-else>
          <span>Перетащите файл, вставьте скриншот (Ctrl+V) или выберите на диске</span>
          <span class="text-slate-400">Скопируйте скриншот и просто нажмите Ctrl+V</span>
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
