<script setup lang="ts">
import { X } from "lucide-vue-next";
import { DialogClose, DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui";
import { computed } from "vue";

import { formatLongDate, formatTime } from "@/utils/time";

// Окно занятия из недельного вида ученика. Шапка - как у окна занятия репетитора
// (BookingDetailsModal): дата и время крупно; ниже - обычная карточка занятия со
// всеми её действиями (слот), чтобы ученик мог то же, что и в списке.
const props = defineProps<{ startAt: string; endAt: string; isGroup?: boolean }>();
const emit = defineEmits<{ close: [] }>();

const isOver = computed(() => new Date(props.endAt) < new Date());
const isNow = computed(() => Date.now() >= new Date(props.startAt).getTime() && !isOver.value);
</script>

<template>
  <DialogRoot :open="true" @update:open="(open) => !open && emit('close')">
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-50 bg-black/40 data-[state=closed]:animate-fade-out data-[state=open]:animate-fade-in"
      />
      <DialogContent
        class="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-y-auto rounded-2xl bg-white shadow-xl
          data-[state=closed]:animate-pop-out data-[state=open]:animate-pop-in dark:bg-slate-900"
        :aria-describedby="undefined"
      >
        <div
          class="rounded-t-2xl px-6 pb-4 pt-5"
          :class="isGroup ? 'bg-sky-50 dark:bg-sky-950/40' : 'bg-brand-50 dark:bg-brand-900/30'"
        >
          <div class="flex items-start justify-between gap-4">
            <div>
              <div
                class="text-sm font-medium"
                :class="isGroup ? 'text-sky-700 dark:text-sky-300' : 'text-brand-700 dark:text-brand-300'"
              >
                {{ formatLongDate(startAt) }}
              </div>
              <DialogTitle class="mt-0.5 text-3xl font-semibold tabular-nums">
                {{ formatTime(startAt) }}–{{ formatTime(endAt) }}
                <span class="text-base font-normal text-slate-500">МСК</span>
              </DialogTitle>
            </div>
            <DialogClose class="rounded-md p-1 text-slate-400 hover:bg-white/60 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200">
              <X class="h-5 w-5" />
            </DialogClose>
          </div>
          <div v-if="isNow || isOver" class="mt-3 flex flex-wrap gap-1.5 text-xs">
            <span v-if="isNow" class="rounded-full bg-brand-500 px-2 py-0.5 font-medium text-white">Идёт сейчас</span>
            <span v-else class="rounded-full bg-slate-200 px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">Прошло</span>
          </div>
        </div>
        <div class="px-6 py-5">
          <slot />
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
