<script setup lang="ts">
import { onMounted, ref } from "vue";

import { listMessages, listThreads, sendMessage } from "@/api/chat";
import { useAuthStore } from "@/stores/auth";
import type { ChatMessage, ChatThread } from "@/types/chat";
import { formatDateTimeWithMsk } from "@/utils/time";

const auth = useAuthStore();
const threads = ref<ChatThread[]>([]);
const activeThread = ref<ChatThread | null>(null);
const messages = ref<ChatMessage[]>([]);
const draft = ref("");
const file = ref<File | null>(null);
const isSending = ref(false);

async function loadThreads(): Promise<void> {
  threads.value = await listThreads();
  if (threads.value.length > 0 && !activeThread.value) {
    await openThread(threads.value[0]);
  }
}

async function openThread(thread: ChatThread): Promise<void> {
  activeThread.value = thread;
  messages.value = await listMessages(thread.id);
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  file.value = input.files?.[0] ?? null;
}

async function send(): Promise<void> {
  if (!activeThread.value || (!draft.value.trim() && !file.value)) return;
  isSending.value = true;
  try {
    const message = await sendMessage(activeThread.value.id, draft.value.trim() || undefined, file.value ?? undefined);
    messages.value.push(message);
    draft.value = "";
    file.value = null;
  } finally {
    isSending.value = false;
  }
}

defineExpose({ loadThreads });
onMounted(loadThreads);
</script>

<template>
  <div class="flex h-[32rem] gap-4 rounded-lg border border-slate-200 dark:border-slate-800">
    <aside class="w-48 shrink-0 overflow-y-auto border-r border-slate-200 dark:border-slate-800">
      <p v-if="threads.length === 0" class="p-3 text-xs text-slate-400">Чатов пока нет.</p>
      <button
        v-for="thread in threads"
        :key="thread.id"
        type="button"
        class="block w-full truncate px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
        :class="activeThread?.id === thread.id ? 'bg-slate-100 font-medium dark:bg-slate-800' : ''"
        @click="openThread(thread)"
      >
        {{ thread.display_title || (thread.type === "group" ? "Группа" : "Личный чат") }}
      </button>
    </aside>

    <div class="flex flex-1 flex-col p-3">
      <template v-if="activeThread">
        <div class="flex-1 overflow-y-auto">
          <div
            v-for="message in messages"
            :key="message.id"
            class="mb-2 max-w-[80%] rounded-md px-3 py-1.5 text-sm"
            :class="
              message.sender_id === auth.user?.id
                ? 'ml-auto bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                : 'bg-slate-100 dark:bg-slate-800'
            "
          >
            <p v-if="message.content">{{ message.content }}</p>
            <a v-if="message.file_path" :href="message.file_path" target="_blank" class="underline">Файл</a>
            <div class="mt-1 text-[10px] opacity-70">{{ formatDateTimeWithMsk(message.created_at) }}</div>
          </div>
        </div>
        <form class="mt-2 flex gap-2" @submit.prevent="send">
          <input
            v-model="draft"
            placeholder="Сообщение…"
            class="flex-1 rounded-md border border-slate-300 bg-transparent px-3 py-1.5 text-sm dark:border-slate-700"
          />
          <input type="file" class="w-32 text-xs" @change="onFileChange" />
          <button
            type="submit"
            :disabled="isSending"
            class="rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"
          >
            Отправить
          </button>
        </form>
      </template>
      <p v-else class="m-auto text-sm text-slate-400">Выберите чат слева.</p>
    </div>
  </div>
</template>
