<script setup lang="ts">
import { X } from "lucide-vue-next";
import { DialogClose, DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui";
import { ref } from "vue";

import type { Booking } from "@/types/booking";

const props = defineProps<{ booking: Booking }>();
const emit = defineEmits<{ close: []; save: [link: string, applyToStudent: boolean] }>();

const link = ref(props.booking.meeting_link ?? "");
const applyToStudent = ref(false);

function submit(): void {
  emit("save", link.value.trim(), applyToStudent.value);
}
</script>

<template>
  <!-- Диалог Reka UI: фокус запирается внутри окна, Escape и клик по подложке
       закрывают его, а фокус возвращается на вызвавшую кнопку. -->
  <DialogRoot :open="true" @update:open="(open) => !open && emit('close')">
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-50 bg-black/40 data-[state=closed]:animate-fade-out data-[state=open]:animate-fade-in"
      />
      <DialogContent
        class="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-5 shadow-xl
          data-[state=closed]:animate-pop-out data-[state=open]:animate-pop-in dark:bg-slate-900"
        :aria-describedby="undefined"
      >
        <div class="flex items-center justify-between gap-4">
          <DialogTitle class="text-lg font-semibold">Ссылка на занятие</DialogTitle>
          <DialogClose class="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200">
            <X class="h-4 w-4" />
          </DialogClose>
        </div>
        <form class="mt-4 flex flex-col gap-3" @submit.prevent="submit">
          <input
            v-model="link"
            type="text"
            placeholder="https://…"
            autofocus
            class="rounded-md border border-slate-300 bg-transparent px-3 py-1.5 text-sm dark:border-slate-700"
          />
          <label v-if="booking.student_id" class="flex items-start gap-2 text-sm">
            <input v-model="applyToStudent" type="checkbox" class="mt-0.5" />
            Постоянная ссылка на занятия с этим учеником
          </label>
          <div class="flex gap-2">
            <button type="submit" class="rounded-md bg-brand-500 px-4 py-1.5 text-sm text-white">
              Сохранить
            </button>
            <button type="button" class="rounded-md border border-slate-300 px-4 py-1.5 text-sm dark:border-slate-700" @click="emit('close')">
              Отмена
            </button>
          </div>
        </form>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
