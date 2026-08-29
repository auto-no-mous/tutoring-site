<script setup lang="ts">
import { X, ZoomIn, ZoomOut } from "lucide-vue-next";
import { DialogClose, DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui";
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";

import { clampView, coverScale, cropSourceRect, initialView, rescaleAroundCenter } from "@/utils/cropGeometry";

const props = defineProps<{ file: File }>();
const emit = defineEmits<{ close: []; cropped: [blob: Blob] }>();

// Сторона рамки на экране. 256 - чтобы влезало и на экране 320px вместе с отступами
// диалога. Сохраняем крупнее (см. OUTPUT_SIZE): рамка нужна для наводки, а не для
// качества.
const VIEWPORT = 256;
// Фото показывается максимум на 144px (карточка каталога и страница профиля), так что
// 512 хватает с запасом даже на экранах с двойной плотностью.
const OUTPUT_SIZE = 512;
const MAX_ZOOM = 4;
const JPEG_QUALITY = 0.9;

const objectUrl = ref("");
const image = shallowRef<HTMLImageElement | null>(null);
const view = ref(initialView(1, 1, VIEWPORT));
const isSaving = ref(false);
const error = ref("");

const minScale = computed(() =>
  image.value ? coverScale(image.value.naturalWidth, image.value.naturalHeight, VIEWPORT) : 1,
);
const maxScale = computed(() => minScale.value * MAX_ZOOM);

// Картинка позиционируется натуральным размером, умноженным на масштаб. max-w-none
// обязателен: глобальные стили ужимают изображения по ширине контейнера.
const imageStyle = computed(() => {
  const img = image.value;
  if (!img) return {};
  return {
    width: `${img.naturalWidth * view.value.scale}px`,
    height: `${img.naturalHeight * view.value.scale}px`,
    transform: `translate(${view.value.offsetX}px, ${view.value.offsetY}px)`,
  };
});

watch(
  () => props.file,
  (file) => {
    if (objectUrl.value) URL.revokeObjectURL(objectUrl.value);
    error.value = "";
    objectUrl.value = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      image.value = img;
      view.value = initialView(img.naturalWidth, img.naturalHeight, VIEWPORT);
    };
    img.onerror = () => {
      error.value = "Не удалось открыть изображение. Выберите другой файл.";
    };
    img.src = objectUrl.value;
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value);
});

// --- Перетаскивание -------------------------------------------------------------
// Pointer events, а не mouse и touch по отдельности: один обработчик покрывает мышь,
// палец и стилус. setPointerCapture нужен, чтобы кадр не терялся, если курсор вышел
// за пределы рамки с зажатой кнопкой.

let dragPointerId: number | null = null;
let dragStartX = 0;
let dragStartY = 0;
let dragStartOffsetX = 0;
let dragStartOffsetY = 0;

function onPointerDown(event: PointerEvent): void {
  if (!image.value) return;
  dragPointerId = event.pointerId;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  dragStartX = event.clientX;
  dragStartY = event.clientY;
  dragStartOffsetX = view.value.offsetX;
  dragStartOffsetY = view.value.offsetY;
}

function onPointerMove(event: PointerEvent): void {
  if (dragPointerId !== event.pointerId || !image.value) return;
  view.value = clampView(
    {
      scale: view.value.scale,
      offsetX: dragStartOffsetX + (event.clientX - dragStartX),
      offsetY: dragStartOffsetY + (event.clientY - dragStartY),
    },
    image.value.naturalWidth,
    image.value.naturalHeight,
    VIEWPORT,
  );
}

function onPointerUp(event: PointerEvent): void {
  if (dragPointerId !== event.pointerId) return;
  (event.currentTarget as HTMLElement).releasePointerCapture(event.pointerId);
  dragPointerId = null;
}

function setScale(next: number): void {
  if (!image.value) return;
  const clamped = Math.min(maxScale.value, Math.max(minScale.value, next));
  view.value = rescaleAroundCenter(
    view.value,
    clamped,
    image.value.naturalWidth,
    image.value.naturalHeight,
    VIEWPORT,
  );
}

function onWheel(event: WheelEvent): void {
  event.preventDefault();
  setScale(view.value.scale * (event.deltaY < 0 ? 1.1 : 1 / 1.1));
}

// --- Сохранение ------------------------------------------------------------------

async function save(): Promise<void> {
  const img = image.value;
  if (!img) return;
  isSaving.value = true;
  error.value = "";
  try {
    const canvas = document.createElement("canvas");
    canvas.width = OUTPUT_SIZE;
    canvas.height = OUTPUT_SIZE;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("canvas 2d context unavailable");

    // Белая подложка: сохраняем в JPEG, а он не умеет прозрачность - без заливки
    // прозрачные края PNG стали бы чёрными.
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, OUTPUT_SIZE, OUTPUT_SIZE);

    const rect = cropSourceRect(view.value, VIEWPORT);
    ctx.drawImage(img, rect.sx, rect.sy, rect.size, rect.size, 0, 0, OUTPUT_SIZE, OUTPUT_SIZE);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
    );
    if (!blob) throw new Error("toBlob returned null");
    emit("cropped", blob);
  } catch {
    error.value = "Не удалось обработать изображение. Попробуйте другой файл.";
  } finally {
    isSaving.value = false;
  }
}
</script>

<template>
  <DialogRoot :open="true" @update:open="(open) => !open && emit('close')">
    <DialogPortal>
      <DialogOverlay class="fixed inset-0 z-50 bg-black/40 data-[state=closed]:animate-fade-out data-[state=open]:animate-fade-in" />
      <DialogContent
        class="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-5 shadow-xl
          data-[state=closed]:animate-pop-out data-[state=open]:animate-pop-in dark:bg-slate-900"
      >
        <div class="flex items-center justify-between gap-4">
          <DialogTitle class="text-lg font-semibold">Кадрирование фото</DialogTitle>
          <DialogClose class="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200">
            <X class="h-4 w-4" />
          </DialogClose>
        </div>
        <DialogDescription class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Перетащите фото, чтобы выбрать видимую часть, и подберите масштаб.
        </DialogDescription>

        <p v-if="error" class="mt-4 text-sm text-red-600 dark:text-red-400">{{ error }}</p>

        <template v-else>
          <!-- touch-none: иначе перетаскивание на телефоне прокручивало бы страницу
               вместо того, чтобы двигать кадр. -->
          <div
            class="relative mx-auto mt-4 h-64 w-64 cursor-move touch-none overflow-hidden rounded-xl bg-slate-100 dark:bg-slate-800"
            @pointerdown="onPointerDown"
            @pointermove="onPointerMove"
            @pointerup="onPointerUp"
            @pointercancel="onPointerUp"
            @wheel="onWheel"
          >
            <img
              v-if="objectUrl"
              :src="objectUrl"
              alt=""
              draggable="false"
              class="absolute left-0 top-0 max-w-none select-none"
              :style="imageStyle"
            />
          </div>

          <!-- Ползунок появляется только вместе с картинкой: до её загрузки границы
               масштаба ещё неизвестны. -->
          <div v-if="image" class="mt-4 flex items-center gap-3">
            <ZoomOut class="h-4 w-4 shrink-0 text-slate-400" />
            <input
              :value="view.scale"
              type="range"
              :min="minScale"
              :max="maxScale"
              :step="(maxScale - minScale) / 100 || 0.01"
              aria-label="Масштаб"
              class="w-full"
              @input="setScale(Number(($event.target as HTMLInputElement).value))"
            />
            <ZoomIn class="h-4 w-4 shrink-0 text-slate-400" />
          </div>

          <div class="mt-4 flex gap-2">
            <button
              type="button"
              :disabled="isSaving || !image"
              class="rounded-md bg-brand-500 px-4 py-1.5 text-sm text-white disabled:opacity-50"
              @click="save"
            >
              Сохранить фото
            </button>
            <button type="button" class="rounded-md border border-slate-300 px-4 py-1.5 text-sm dark:border-slate-700" @click="emit('close')">
              Отмена
            </button>
          </div>
        </template>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
