<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";

import { listMessageableStudents, listMessages, listThreads, openThreadWithStudent, sendMessage } from "@/api/chat";
import { listSystemNotifications, markSystemNotificationsRead } from "@/api/notifications";
import { useAuthStore } from "@/stores/auth";
import { useNotificationsStore } from "@/stores/notifications";
import type { ChatMessage, ChatThread } from "@/types/chat";
import type { SystemNotification } from "@/types/notification";
import type { TutorStudent } from "@/types/tutor";
import { formatDayLabel, formatThreadTimestamp, formatTime } from "@/utils/time";

// Lets other tabs (e.g. tutor/GroupsTab.vue's "написать" / "чат группы" buttons) deep-
// link straight into a specific thread instead of always landing on the first one -
// see CabinetView.vue, which resolves this from the ?thread= query param. "system" is
// a reserved id for the pseudo-thread below, not a real ChatThread.
const props = defineProps<{ initialThreadId?: string | null }>();

const SYSTEM_THREAD_ID = "system";

const auth = useAuthStore();
const notifications = useNotificationsStore();
const threads = ref<ChatThread[]>([]);
const activeThread = ref<ChatThread | null>(null);
const messages = ref<ChatMessage[]>([]);
const draft = ref("");
const file = ref<File | null>(null);
const isSending = ref(false);
const sendError = ref("");
const fileInputEl = ref<HTMLInputElement | null>(null);
const messagesEl = ref<HTMLElement | null>(null);

// "Системные уведомления" - a read-only pseudo-thread (not backed by ChatThread/
// ChatMessage) rendered as if it were an ordinary chat, per the product requirement
// that schedule-change/login/homework etc. notifications look like messages from a
// "Системные уведомления" sender. The user can never reply to it.
const isSystemThreadActive = ref(false);
const systemNotifications = ref<SystemNotification[]>([]);
const systemUnreadCount = computed(() => systemNotifications.value.filter((n) => !n.read_at).length);

// Tutor-only "start a new chat" picker (there's no equivalent for students - they
// reach a tutor via the "Написать сообщение" button on the tutor's public profile).
const showNewChatPicker = ref(false);
const messageableStudents = ref<TutorStudent[]>([]);
const isLoadingMessageableStudents = ref(false);

// Polling, not a websocket - keeps the backend simple while still feeling live. The
// thread list ticks slower since it only needs to surface new threads/unread counts;
// the open thread ticks faster since that's where a live conversation happens.
const MESSAGES_POLL_MS = 4000;
const THREADS_POLL_MS = 7000;
let messagesPollId: ReturnType<typeof setInterval> | null = null;
let threadsPollId: ReturnType<typeof setInterval> | null = null;

interface MessageGroup {
  dayLabel: string;
  messages: ChatMessage[];
}

// Consecutive messages from the same calendar day are grouped under one date
// separator, like every other chat app - makes long histories scannable.
const messageGroups = computed<MessageGroup[]>(() => {
  const groups: MessageGroup[] = [];
  for (const message of messages.value) {
    const label = formatDayLabel(message.created_at);
    const last = groups[groups.length - 1];
    if (last && last.dayLabel === label) {
      last.messages.push(message);
    } else {
      groups.push({ dayLabel: label, messages: [message] });
    }
  }
  return groups;
});

interface SystemNotificationGroup {
  dayLabel: string;
  notifications: SystemNotification[];
}

const systemMessageGroups = computed<SystemNotificationGroup[]>(() => {
  const groups: SystemNotificationGroup[] = [];
  // Oldest first, same convention as messageGroups above - list_for_user returns
  // newest-first for the list view, so reverse for chronological chat rendering.
  for (const item of [...systemNotifications.value].reverse()) {
    const label = formatDayLabel(item.created_at);
    const last = groups[groups.length - 1];
    if (last && last.dayLabel === label) {
      last.notifications.push(item);
    } else {
      groups.push({ dayLabel: label, notifications: [item] });
    }
  }
  return groups;
});

function threadInitial(thread: ChatThread): string {
  return (thread.display_title || "?").charAt(0).toUpperCase();
}

function isImagePath(path: string): boolean {
  return /\.(png|jpe?g|gif|webp)$/i.test(path);
}

function studentLabel(student: TutorStudent): string {
  const name = `${student.last_name} ${student.first_name}`.trim();
  return student.grade ? `${name}, ${student.grade}-й класс` : name;
}

async function toggleNewChatPicker(): Promise<void> {
  showNewChatPicker.value = !showNewChatPicker.value;
  if (!showNewChatPicker.value || messageableStudents.value.length > 0) return;
  isLoadingMessageableStudents.value = true;
  try {
    messageableStudents.value = await listMessageableStudents();
  } finally {
    isLoadingMessageableStudents.value = false;
  }
}

async function startChatWith(student: TutorStudent): Promise<void> {
  showNewChatPicker.value = false;
  const thread = await openThreadWithStudent(student.id);
  await loadThreads();
  const target = threads.value.find((t) => t.id === thread.id) ?? thread;
  await openThread(target);
}

function isNearBottom(): boolean {
  const el = messagesEl.value;
  if (!el) return true;
  return el.scrollHeight - el.scrollTop - el.clientHeight < 80;
}

function scrollToBottom(): void {
  const el = messagesEl.value;
  if (el) el.scrollTop = el.scrollHeight;
}

async function loadThreads(): Promise<void> {
  const data = await listThreads();
  threads.value = data;
  // Read-only refresh for the sidebar preview/badge - marking notifications as read
  // only happens while the pseudo-thread is actually open (see loadSystemNotifications,
  // only called from openSystemThread/startMessagePolling below).
  if (!isSystemThreadActive.value) {
    systemNotifications.value = await listSystemNotifications();
  }
  if (activeThread.value || isSystemThreadActive.value) {
    // Keep the open thread's own metadata (title, unread_count) in sync with the
    // list poll, without disturbing which thread is currently open.
    if (activeThread.value) {
      const refreshed = data.find((t) => t.id === activeThread.value?.id);
      if (refreshed) activeThread.value = refreshed;
    }
    return;
  }
  if (props.initialThreadId === SYSTEM_THREAD_ID) {
    await openSystemThread();
    return;
  }
  const target = props.initialThreadId ? data.find((t) => t.id === props.initialThreadId) : null;
  if (target) {
    await openThread(target);
  } else if (data.length > 0) {
    await openThread(data[0]);
  } else {
    await openSystemThread();
  }
}

async function loadMessages(): Promise<void> {
  if (!activeThread.value) return;
  const wasNearBottom = isNearBottom();
  const hadMessages = messages.value.length;
  const data = await listMessages(activeThread.value.id);
  const grew = data.length > hadMessages;
  messages.value = data;
  if (activeThread.value) activeThread.value.unread_count = 0;
  // Only yank the scroll position to the bottom if new messages actually arrived,
  // and only if the reader was already near the bottom (or this is the first load) -
  // otherwise a poll tick would rudely interrupt someone reading older history.
  if (grew && (wasNearBottom || hadMessages === 0)) {
    await nextTick();
    scrollToBottom();
  }
}

async function loadSystemNotifications(): Promise<void> {
  const wasNearBottom = isNearBottom();
  const hadItems = systemNotifications.value.length;
  const data = await listSystemNotifications();
  const grew = data.length > hadItems;
  systemNotifications.value = data;
  if (systemUnreadCount.value > 0) {
    await markSystemNotificationsRead();
    systemNotifications.value = systemNotifications.value.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() }));
    await notifications.refresh();
  }
  if (grew && (wasNearBottom || hadItems === 0)) {
    await nextTick();
    scrollToBottom();
  }
}

function stopMessagePolling(): void {
  if (messagesPollId) clearInterval(messagesPollId);
  messagesPollId = null;
}

function startMessagePolling(): void {
  stopMessagePolling();
  messagesPollId = setInterval(() => {
    if (document.visibilityState !== "visible") return;
    if (isSystemThreadActive.value) loadSystemNotifications();
    else loadMessages();
  }, MESSAGES_POLL_MS);
}

async function openSystemThread(): Promise<void> {
  activeThread.value = null;
  isSystemThreadActive.value = true;
  systemNotifications.value = [];
  await loadSystemNotifications();
  startMessagePolling();
}

async function openThread(thread: ChatThread): Promise<void> {
  activeThread.value = thread;
  isSystemThreadActive.value = false;
  messages.value = [];
  await loadMessages();
  startMessagePolling();
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  file.value = input.files?.[0] ?? null;
}

function clearFile(): void {
  file.value = null;
  if (fileInputEl.value) fileInputEl.value.value = "";
}

async function send(): Promise<void> {
  if (!activeThread.value || (!draft.value.trim() && !file.value)) return;
  isSending.value = true;
  sendError.value = "";
  try {
    const message = await sendMessage(activeThread.value.id, draft.value.trim() || undefined, file.value ?? undefined);
    messages.value.push(message);
    draft.value = "";
    clearFile();
    await nextTick();
    scrollToBottom();
    // Refresh the thread list right away so this thread's preview/order updates
    // immediately instead of waiting for the next poll tick.
    await loadThreads();
  } catch {
    sendError.value = "Не удалось отправить сообщение.";
  } finally {
    isSending.value = false;
  }
}

onMounted(() => {
  loadThreads();
  threadsPollId = setInterval(() => {
    if (document.visibilityState === "visible") loadThreads();
  }, THREADS_POLL_MS);
});

onUnmounted(() => {
  stopMessagePolling();
  if (threadsPollId) clearInterval(threadsPollId);
});

defineExpose({ loadThreads });
</script>

<template>
  <div class="flex h-[32rem] gap-4 rounded-lg border border-slate-200 dark:border-slate-800">
    <aside class="flex w-64 shrink-0 flex-col overflow-y-auto border-r border-slate-200 dark:border-slate-800">
      <div v-if="auth.user?.role === 'tutor'" class="border-b border-slate-200 p-2 dark:border-slate-800">
        <button
          type="button"
          class="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700"
          @click="toggleNewChatPicker"
        >
          {{ showNewChatPicker ? "Отмена" : "+ Новый чат" }}
        </button>
        <div v-if="showNewChatPicker" class="mt-2">
          <p v-if="isLoadingMessageableStudents" class="text-xs text-slate-400">Загрузка…</p>
          <p v-else-if="messageableStudents.length === 0" class="text-xs text-slate-400">
            Нет новых контактов.
          </p>
          <button
            v-for="student in messageableStudents"
            :key="student.id"
            type="button"
            class="block w-full truncate rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
            @click="startChatWith(student)"
          >
            {{ studentLabel(student) }}
          </button>
        </div>
      </div>
      <button
        type="button"
        class="flex w-full items-center gap-2.5 border-b border-slate-200 px-3 py-2.5 text-left hover:bg-slate-100 dark:border-slate-800 dark:hover:bg-slate-800"
        :class="isSystemThreadActive ? 'bg-slate-100 dark:bg-slate-800' : ''"
        @click="openSystemThread"
      >
        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm text-blue-700 dark:bg-blue-950 dark:text-blue-300">
          🔔
        </span>
        <span class="min-w-0 flex-1">
          <span class="flex items-center justify-between gap-1">
            <span class="truncate text-sm" :class="systemUnreadCount > 0 ? 'font-semibold' : 'font-medium'">
              Системные уведомления
            </span>
          </span>
          <span class="flex items-center justify-between gap-1">
            <span class="truncate text-xs text-slate-500">
              {{ systemNotifications[0]?.title ?? "Нет уведомлений" }}
            </span>
            <span
              v-if="systemUnreadCount > 0"
              class="flex h-4 min-w-4 shrink-0 items-center justify-center rounded-full bg-slate-900 px-1 text-[10px] font-medium text-white dark:bg-white dark:text-slate-900"
            >
              {{ systemUnreadCount }}
            </span>
          </span>
        </span>
      </button>
      <p v-if="threads.length === 0" class="p-3 text-xs text-slate-400">Чатов пока нет.</p>
      <button
        v-for="thread in threads"
        :key="thread.id"
        type="button"
        class="flex w-full items-center gap-2.5 px-3 py-2.5 text-left hover:bg-slate-100 dark:hover:bg-slate-800"
        :class="activeThread?.id === thread.id ? 'bg-slate-100 dark:bg-slate-800' : ''"
        @click="openThread(thread)"
      >
        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">
          {{ threadInitial(thread) }}
        </span>
        <span class="min-w-0 flex-1">
          <span class="flex items-center justify-between gap-1">
            <span class="truncate text-sm" :class="thread.unread_count > 0 ? 'font-semibold' : 'font-medium'">
              {{ thread.display_title || (thread.type === "group" ? "Группа" : "Личный чат") }}
            </span>
            <span v-if="thread.last_message_at" class="shrink-0 text-[10px] text-slate-400">
              {{ formatThreadTimestamp(thread.last_message_at) }}
            </span>
          </span>
          <span class="flex items-center justify-between gap-1">
            <span class="truncate text-xs text-slate-500">{{ thread.last_message_preview ?? "Нет сообщений" }}</span>
            <span
              v-if="thread.unread_count > 0"
              class="flex h-4 min-w-4 shrink-0 items-center justify-center rounded-full bg-slate-900 px-1 text-[10px] font-medium text-white dark:bg-white dark:text-slate-900"
            >
              {{ thread.unread_count }}
            </span>
          </span>
        </span>
      </button>
    </aside>

    <div class="flex flex-1 flex-col p-3">
      <template v-if="isSystemThreadActive">
        <div class="border-b border-slate-200 pb-2 text-sm font-medium dark:border-slate-800">
          Системные уведомления
        </div>

        <div ref="messagesEl" class="mt-2 flex-1 overflow-y-auto">
          <p v-if="systemNotifications.length === 0" class="m-auto text-sm text-slate-400">Уведомлений пока нет.</p>
          <template v-for="group in systemMessageGroups" :key="group.dayLabel + group.notifications[0].id">
            <div class="my-2 flex justify-center">
              <span class="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {{ group.dayLabel }}
              </span>
            </div>
            <div v-for="item in group.notifications" :key="item.id" class="mb-2 flex flex-col items-start">
              <span class="mb-0.5 px-1 text-[11px] font-medium text-slate-500">Системные уведомления</span>
              <div class="max-w-[80%] rounded-md bg-slate-100 px-3 py-1.5 text-sm dark:bg-slate-800">
                <p class="font-medium">{{ item.title }}</p>
                <p class="whitespace-pre-wrap">{{ item.body }}</p>
                <div class="mt-1 text-[10px] opacity-70">{{ formatTime(item.created_at) }}</div>
              </div>
            </div>
          </template>
        </div>

        <p class="mt-2 text-center text-xs text-slate-400">
          Это системные уведомления - ответить на них нельзя.
        </p>
      </template>
      <template v-else-if="activeThread">
        <div class="border-b border-slate-200 pb-2 text-sm font-medium dark:border-slate-800">
          {{ activeThread.display_title || (activeThread.type === "group" ? "Группа" : "Личный чат") }}
        </div>

        <div ref="messagesEl" class="mt-2 flex-1 overflow-y-auto">
          <template v-for="group in messageGroups" :key="group.dayLabel + group.messages[0].id">
            <div class="my-2 flex justify-center">
              <span class="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {{ group.dayLabel }}
              </span>
            </div>
            <div
              v-for="message in group.messages"
              :key="message.id"
              class="mb-2 flex flex-col"
              :class="message.sender_id === auth.user?.id ? 'items-end' : 'items-start'"
            >
              <span
                v-if="activeThread.type === 'group' && message.sender_id !== auth.user?.id"
                class="mb-0.5 px-1 text-[11px] font-medium text-slate-500"
              >
                {{ message.sender_display_name }}
              </span>
              <div
                class="max-w-[80%] rounded-md px-3 py-1.5 text-sm"
                :class="
                  message.sender_id === auth.user?.id
                    ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                    : 'bg-slate-100 dark:bg-slate-800'
                "
              >
                <p v-if="message.content" class="whitespace-pre-wrap">{{ message.content }}</p>
                <a v-if="message.file_path && isImagePath(message.file_path)" :href="message.file_path" target="_blank">
                  <img :src="message.file_path" alt="" class="mt-1 max-h-48 rounded-md object-cover" />
                </a>
                <a v-else-if="message.file_path" :href="message.file_path" target="_blank" class="mt-1 flex items-center gap-1 underline">
                  📎 Файл
                </a>
                <div class="mt-1 text-[10px] opacity-70">{{ formatTime(message.created_at) }}</div>
              </div>
            </div>
          </template>
        </div>

        <p v-if="file" class="mt-2 flex items-center gap-2 text-xs text-slate-500">
          📎 {{ file.name }}
          <button type="button" class="text-red-600 hover:underline dark:text-red-400" @click="clearFile">Убрать</button>
        </p>
        <p v-if="sendError" class="mt-1 text-xs text-red-600 dark:text-red-400">{{ sendError }}</p>
        <form class="mt-2 flex items-center gap-2" @submit.prevent="send">
          <input ref="fileInputEl" type="file" class="hidden" @change="onFileChange" />
          <button
            type="button"
            title="Прикрепить файл"
            class="shrink-0 rounded-md border border-slate-300 px-2.5 py-1.5 text-sm dark:border-slate-700"
            @click="fileInputEl?.click()"
          >
            📎
          </button>
          <input
            v-model="draft"
            placeholder="Сообщение…"
            class="flex-1 rounded-md border border-slate-300 bg-transparent px-3 py-1.5 text-sm dark:border-slate-700"
          />
          <button
            type="submit"
            :disabled="isSending || (!draft.trim() && !file)"
            class="shrink-0 rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"
          >
            Отправить
          </button>
        </form>
      </template>
      <p v-else class="m-auto text-sm text-slate-400">Выберите чат слева.</p>
    </div>
  </div>
</template>
