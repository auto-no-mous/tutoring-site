<script setup lang="ts">
import { TriangleAlert } from "lucide-vue-next";
import { DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui";

// Еженедельный повтор не получился - говорим об этом отдельным окном, а не строкой
// под «Вы записаны»: строку легко пропустить, и ученик уходил уверенным, что записан
// надолго.
defineProps<{ lessonDate: string }>();
const emit = defineEmits<{ close: [] }>();
</script>

<template>
  <DialogRoot :open="true" @update:open="(open) => !open && emit('close')">
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-50 bg-black/50 data-[state=closed]:animate-fade-out data-[state=open]:animate-fade-in"
      />
      <DialogContent
        role="alertdialog"
        class="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-2xl border-2 border-amber-400 bg-white shadow-xl
          data-[state=closed]:animate-pop-out data-[state=open]:animate-pop-in dark:border-amber-600 dark:bg-slate-900"
      >
        <div class="flex items-center gap-3 bg-amber-100 px-5 py-4 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200">
          <TriangleAlert class="h-7 w-7 shrink-0" />
          <DialogTitle class="text-lg font-semibold">Еженедельная запись не создана</DialogTitle>
        </div>
        <DialogDescription class="flex flex-col gap-2 px-5 py-4 text-base">
          <span>
            На следующих неделях это время уже занято, поэтому повторять занятие каждую неделю не получится.
          </span>
          <span class="font-medium">Вы записаны только на одно занятие: {{ lessonDate }}.</span>
          <span>Напишите репетитору, чтобы подобрать постоянное время, - он тоже получил уведомление.</span>
        </DialogDescription>
        <div class="px-5 pb-5">
          <button
            type="button"
            class="w-full rounded-lg bg-amber-500 px-4 py-2.5 font-medium text-white hover:bg-amber-600"
            @click="emit('close')"
          >
            Понятно
          </button>
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
