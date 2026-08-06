<script setup lang="ts">
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
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="emit('close')">
    <div class="w-full max-w-sm rounded-lg bg-white p-4 shadow-xl dark:bg-slate-900">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-medium">Ссылка на занятие</h2>
        <button type="button" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200" @click="emit('close')">✕</button>
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
          <button type="submit" class="rounded-md bg-slate-900 px-4 py-1.5 text-sm text-white dark:bg-white dark:text-slate-900">
            Сохранить
          </button>
          <button type="button" class="rounded-md border border-slate-300 px-4 py-1.5 text-sm dark:border-slate-700" @click="emit('close')">
            Отмена
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
