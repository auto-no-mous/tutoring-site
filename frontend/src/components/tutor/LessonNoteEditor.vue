<script setup lang="ts">
import { StickyNote } from "lucide-vue-next";
import { nextTick, ref } from "vue";

// Примечание репетитора к занятию: видно только ему (сервер ученику его не отдаёт).
// Один и тот же редактор в карточке списка (BookingCard) и в окне занятия
// (BookingDetailsModal) - чтобы примечание правилось одинаково в обоих видах.
const props = defineProps<{ note: string | null; busy?: boolean; size?: "sm" | "md" }>();
const emit = defineEmits<{ save: [string | null] }>();

const NOTES_MAX_LENGTH = 2000;

const isEditing = ref(false);
const draft = ref("");
const textarea = ref<HTMLTextAreaElement | null>(null);

async function startEdit(): Promise<void> {
  draft.value = props.note ?? "";
  isEditing.value = true;
  await nextTick();
  textarea.value?.focus();
}

function save(): void {
  emit("save", draft.value.trim() || null);
  isEditing.value = false;
}
</script>

<template>
  <div :class="size === 'md' ? 'text-sm' : 'text-xs'">
    <div v-if="isEditing" class="flex flex-col gap-1.5">
      <textarea
        ref="textarea"
        v-model="draft"
        :rows="size === 'md' ? 3 : 2"
        :maxlength="NOTES_MAX_LENGTH"
        placeholder="Например: начать с проверки ДЗ, повторить дроби"
        aria-label="Примечание к занятию"
        class="w-full rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
        @keydown.ctrl.enter="save"
        @keydown.meta.enter="save"
        @keydown.esc.stop="isEditing = false"
      />
      <div class="flex items-center gap-2">
        <button type="button" class="rounded-md bg-brand-500 px-2.5 py-1 text-white disabled:opacity-50" :disabled="busy" @click="save">
          Сохранить
        </button>
        <button type="button" class="text-slate-500 underline" @click="isEditing = false">Отмена</button>
        <span class="ml-auto text-slate-400">Видно только вам</span>
      </div>
    </div>
    <button
      v-else-if="note"
      type="button"
      class="group flex w-full items-start gap-1.5 rounded-md bg-amber-50 px-2 py-1.5 text-left text-slate-700 transition-colors hover:bg-amber-100 dark:bg-amber-950/40 dark:text-slate-200 dark:hover:bg-amber-950/70"
      title="Изменить примечание"
      @click="startEdit"
    >
      <StickyNote class="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-400" />
      <span class="whitespace-pre-wrap break-words">{{ note }}</span>
    </button>
    <button
      v-else
      type="button"
      class="inline-flex items-center gap-1 text-slate-500 underline transition-colors hover:text-brand-600 dark:hover:text-brand-300"
      @click="startEdit"
    >
      <StickyNote class="h-3.5 w-3.5" />Добавить примечание
    </button>
  </div>
</template>
