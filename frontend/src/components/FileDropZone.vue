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
// Файлов можно набрать несколько (до max): задание из нескольких листов, решение на
// нескольких скриншотах. Каждый новый файл добавляется к уже выбранным.
// hideTypeHint - не писать «не изображение» под файлом: это подсказка ученику, который
// обычно сдаёт скриншот, а для материала задания (PDF, Word) она звучит странно.
const props = withDefaults(
  defineProps<{ modelValue: File[]; disabled?: boolean; accept?: string; hideTypeHint?: boolean; max?: number }>(),
  { max: 10 },
);
const emit = defineEmits<{ "update:modelValue": [File[]] }>();

const input = ref<HTMLInputElement | null>(null);
const root = ref<HTMLElement | null>(null);
const isDragging = ref(false);
const overflowNote = ref("");

const isFull = computed(() => props.modelValue.length >= props.max);
const isBlocked = computed(() => Boolean(props.disabled) || isFull.value);

// Превью держим на objectURL и обязательно отзываем: иначе каждый вставленный
// скриншот остаётся висеть в памяти вкладки до перезагрузки.
const previews = new Map<File, string>();
const previewUrls = ref<Map<File, string>>(new Map());

watch(
  () => props.modelValue,
  (files) => {
    for (const [file, url] of previews) {
      if (!files.includes(file)) {
        URL.revokeObjectURL(url);
        previews.delete(file);
      }
    }
    for (const file of files) {
      if (!previews.has(file) && file.type.startsWith("image/")) previews.set(file, URL.createObjectURL(file));
    }
    previewUrls.value = new Map(previews);
    if (files.length < props.max) overflowNote.value = "";
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
  zone = { el: root.value!, isDisabled: () => isBlocked.value, paste: onPaste };
  register(zone);
});

onBeforeUnmount(() => {
  for (const url of previews.values()) URL.revokeObjectURL(url);
  previews.clear();
  if (zone) unregister(zone);
});

function add(files: File[]): void {
  if (props.disabled || files.length === 0) return;
  const room = props.max - props.modelValue.length;
  if (room <= 0) return;
  overflowNote.value = files.length > room ? `Можно приложить не больше ${props.max} файлов - лишние не добавлены.` : "";
  emit("update:modelValue", [...props.modelValue, ...files.slice(0, room)]);
}

function onDrop(event: DragEvent): void {
  isDragging.value = false;
  markActive();
  add(Array.from(event.dataTransfer?.files ?? []));
}

function onPick(event: Event): void {
  const target = event.target as HTMLInputElement;
  add(Array.from(target.files ?? []));
  // Иначе повторный выбор того же файла не вызвал бы change.
  target.value = "";
}

// true - файл из буфера принят.
function onPaste(event: ClipboardEvent): boolean {
  if (isBlocked.value) return false;
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
  add([named]);
  return true;
}

function remove(file: File): void {
  emit(
    "update:modelValue",
    props.modelValue.filter((f) => f !== file),
  );
}

function openPicker(): void {
  if (!isBlocked.value) input.value?.click();
}

function humanSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} КБ`
    : `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div v-if="modelValue.length > 0" class="flex flex-col gap-1">
      <div
        v-for="file in modelValue"
        :key="`${file.name}-${file.size}-${file.lastModified}`"
        data-picked-file
        class="flex items-center gap-3 rounded-md border border-slate-200 px-3 py-1.5 text-xs dark:border-slate-800"
      >
        <img v-if="previewUrls.get(file)" :src="previewUrls.get(file)" alt="" class="h-10 w-10 rounded object-cover" />
        <div class="flex min-w-0 flex-col">
          <span class="truncate font-medium">{{ file.name }}</span>
          <span class="text-slate-400">
            {{ humanSize(file.size) }}{{ file.type.startsWith("image/") || hideTypeHint ? "" : " · не изображение" }}
          </span>
        </div>
        <button
          type="button"
          class="ml-auto shrink-0 rounded p-1 text-slate-400 hover:text-red-600 disabled:opacity-50"
          title="Убрать файл"
          :disabled="disabled"
          @click="remove(file)"
        >
          <X class="h-4 w-4" />
        </button>
      </div>
    </div>

    <div
      ref="root"
      class="flex cursor-pointer items-center gap-3 rounded-md border border-dashed px-3 py-2 text-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
      :class="[
        isDragging
          ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/30'
          : 'border-slate-300 hover:border-brand-400 dark:border-slate-700',
        isBlocked ? 'cursor-not-allowed opacity-50' : '',
      ]"
      tabindex="0"
      role="button"
      @pointerenter="onPointerEnter"
      @pointerleave="onPointerLeave"
      @focusin="markActive"
      @click="openPicker"
      @keydown.enter.prevent="openPicker"
      @keydown.space.prevent="openPicker"
      @dragover.prevent="isDragging = !isBlocked"
      @dragleave="isDragging = false"
      @drop.prevent="onDrop"
    >
      <ImagePlus class="h-5 w-5 shrink-0 text-slate-400" />
      <div class="flex min-w-0 flex-col">
        <template v-if="isFull">
          <span>Выбрано {{ modelValue.length }} из {{ max }} - больше не добавить</span>
        </template>
        <template v-else>
          <span>
            {{ modelValue.length > 0 ? "Добавьте ещё файл" : "Перетащите файлы, вставьте скриншот (Ctrl+V) или выберите на диске" }}
          </span>
          <span class="text-slate-400">
            Скопируйте скриншот и просто нажмите Ctrl+V · до {{ max }} {{ max === 1 ? "файла" : "файлов" }}
          </span>
        </template>
      </div>
    </div>
    <p v-if="overflowNote" class="text-xs text-amber-600 dark:text-amber-400">{{ overflowNote }}</p>

    <input
      ref="input"
      type="file"
      class="hidden"
      multiple
      :accept="accept"
      :disabled="isBlocked"
      @change="onPick"
    />
  </div>
</template>
