<script setup lang="ts">
import { Trash2, X } from "lucide-vue-next";
import { DialogClose, DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui";
import { ref } from "vue";

import {
  createWhiteboard,
  deleteWhiteboard,
  updateWhiteboard,
  type Whiteboard,
} from "@/api/whiteboards";
import { apiErrorMessage } from "@/utils/apiError";

// Владелец досок - ученик или группа; ровно одно из двух, как и на сервере.
const props = defineProps<{
  boards: Whiteboard[];
  studentId?: string | null;
  groupId?: string | null;
  ownerName?: string;
}>();
const emit = defineEmits<{ close: []; changed: [] }>();

const items = ref<Whiteboard[]>([...props.boards]);
const newUrl = ref("");
const newTitle = ref("");
const error = ref("");
const isBusy = ref(false);

async function add(): Promise<void> {
  error.value = "";
  isBusy.value = true;
  try {
    const board = await createWhiteboard({
      student_id: props.studentId ?? null,
      group_id: props.groupId ?? null,
      url: newUrl.value.trim(),
      title: newTitle.value.trim() || null,
    });
    items.value = [board, ...items.value];
    newUrl.value = "";
    newTitle.value = "";
    emit("changed");
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось добавить доску");
  } finally {
    isBusy.value = false;
  }
}

async function rename(board: Whiteboard, title: string): Promise<void> {
  error.value = "";
  try {
    const updated = await updateWhiteboard(board.id, { title: title.trim() || null });
    items.value = items.value.map((b) => (b.id === board.id ? updated : b));
    emit("changed");
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось сохранить название");
  }
}

async function remove(board: Whiteboard): Promise<void> {
  if (!window.confirm(`Удалить доску «${board.title || board.url}»? Сама доска не пострадает — уйдёт только ссылка.`)) {
    return;
  }
  error.value = "";
  try {
    await deleteWhiteboard(board.id);
    items.value = items.value.filter((b) => b.id !== board.id);
    emit("changed");
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось удалить доску");
  }
}
</script>

<template>
  <DialogRoot :open="true" @update:open="(open) => !open && emit('close')">
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-50 bg-black/40 data-[state=closed]:animate-fade-out data-[state=open]:animate-fade-in"
      />
      <DialogContent
        class="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-5 shadow-xl
          data-[state=closed]:animate-pop-out data-[state=open]:animate-pop-in dark:bg-slate-900"
        :aria-describedby="undefined"
      >
        <div class="flex items-center justify-between gap-4">
          <DialogTitle class="text-lg font-semibold">
            Онлайн-доски<span v-if="ownerName" class="font-normal text-slate-500"> — {{ ownerName }}</span>
          </DialogTitle>
          <DialogClose class="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200">
            <X class="h-4 w-4" />
          </DialogClose>
        </div>

        <p class="mt-2 text-xs text-slate-500">
          Ссылки видны и вам, и ученику на карточках занятий. Сверху показывается та доска, которую открывали последней.
        </p>

        <div v-if="items.length > 0" class="mt-3 flex flex-col gap-2">
          <div
            v-for="board in items"
            :key="board.id"
            class="flex items-center gap-2 rounded-md border border-slate-200 px-2 py-1.5 dark:border-slate-800"
          >
            <input
              :value="board.title ?? ''"
              placeholder="Без названия"
              class="w-32 shrink-0 rounded-md border border-transparent bg-transparent px-1 py-0.5 text-sm hover:border-slate-300 focus:border-slate-300 dark:hover:border-slate-700"
              @change="rename(board, ($event.target as HTMLInputElement).value)"
            />
            <a
              :href="board.url"
              target="_blank"
              rel="noopener noreferrer"
              class="flex-1 truncate text-xs text-slate-500 underline"
            >
              {{ board.url }}
            </a>
            <button type="button" class="shrink-0 text-slate-400 hover:text-red-600" @click="remove(board)">
              <Trash2 class="h-4 w-4" />
            </button>
          </div>
        </div>

        <form class="mt-4 flex flex-col gap-2 border-t border-slate-200 pt-3 dark:border-slate-800" @submit.prevent="add">
          <div class="flex gap-2">
            <input
              v-model="newTitle"
              placeholder="Название (необязательно)"
              class="w-36 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700"
            />
            <input
              v-model="newUrl"
              type="url"
              required
              placeholder="https://miro.com/…"
              class="flex-1 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-700"
            />
          </div>
          <p v-if="error" class="text-xs text-red-600 dark:text-red-400">{{ error }}</p>
          <button
            type="submit"
            :disabled="isBusy || !newUrl.trim()"
            class="w-fit rounded-md bg-brand-500 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            Добавить доску
          </button>
        </form>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
