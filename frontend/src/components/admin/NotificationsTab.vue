<script setup lang="ts">
import { onMounted, ref } from "vue";

import { listNotificationTemplates, updateNotificationTemplate } from "@/api/admin";
import type { NotificationTemplate } from "@/types/notification";

const EVENT_LABELS: Record<string, string> = {
  login_success: "Вход в систему",
  login_failed: "Неудачная попытка входа",
  welcome: "Приветствие после регистрации",
  booking_cancelled_by_student: "Ученик отменил занятие",
  booking_rescheduled_by_student: "Ученик перенёс занятие",
  group_application_received: "Новая заявка в группу",
  group_member_left: "Ученик покинул группу",
  booking_cancelled_by_tutor: "Репетитор отменил занятие",
  booking_rescheduled_by_tutor: "Репетитор перенёс занятие",
  group_schedule_changed: "Изменилось расписание группы",
  group_application_accepted: "Заявка в группу принята",
  group_application_rejected: "Заявка в группу отклонена",
  homework_assigned: "Новое домашнее задание",
};

const ROLE_LABELS: Record<string, string> = {
  tutor: "Репетитор",
  student: "Ученик",
};

const templates = ref<NotificationTemplate[]>([]);
const isLoading = ref(true);
const editingId = ref<string | null>(null);
const editTitle = ref("");
const editBody = ref("");
const savingId = ref<string | null>(null);

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    templates.value = await listNotificationTemplates();
  } finally {
    isLoading.value = false;
  }
}

function eventLabel(eventType: string): string {
  return EVENT_LABELS[eventType] ?? eventType;
}

function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role;
}

function startEdit(template: NotificationTemplate): void {
  editingId.value = template.id;
  editTitle.value = template.title;
  editBody.value = template.body;
}

function cancelEdit(): void {
  editingId.value = null;
}

async function save(template: NotificationTemplate): Promise<void> {
  savingId.value = template.id;
  try {
    const updated = await updateNotificationTemplate(template.id, editTitle.value, editBody.value);
    const index = templates.value.findIndex((t) => t.id === template.id);
    if (index !== -1) templates.value[index] = updated;
    editingId.value = null;
  } finally {
    savingId.value = null;
  }
}

onMounted(load);
</script>

<template>
  <div class="flex max-w-3xl flex-col gap-4">
    <p class="text-sm text-slate-500">
      Тексты уведомлений, которые пользователи получают в разделе «Чат» → «Системные уведомления».
      Доступны плейсхолдеры вида <code>{name}</code>, <code>{date}</code>, <code>{time}</code> - неизвестные
      плейсхолдеры просто заменяются на пустую строку.
    </p>
    <p v-if="isLoading" class="text-sm text-slate-400">Загрузка…</p>
    <div v-else class="flex flex-col gap-3">
      <div
        v-for="template in templates"
        :key="template.id"
        class="rounded-md border border-slate-200 p-3 dark:border-slate-800"
      >
        <div class="flex items-center justify-between">
          <div>
            <span class="font-medium">{{ eventLabel(template.event_type) }}</span>
            <span class="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500 dark:bg-slate-800">
              {{ roleLabel(template.role) }}
            </span>
          </div>
          <button
            v-if="editingId !== template.id"
            type="button"
            class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700"
            @click="startEdit(template)"
          >
            Изменить
          </button>
        </div>

        <template v-if="editingId === template.id">
          <label class="mt-2 flex flex-col gap-1 text-sm">
            Заголовок
            <input v-model="editTitle" class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
          </label>
          <label class="mt-2 flex flex-col gap-1 text-sm">
            Текст
            <textarea
              v-model="editBody"
              rows="3"
              class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
            ></textarea>
          </label>
          <div class="mt-2 flex gap-2">
            <button
              type="button"
              :disabled="savingId === template.id"
              class="rounded-md bg-brand-500 px-3 py-1.5 text-xs text-white disabled:opacity-50"
              @click="save(template)"
            >
              Сохранить
            </button>
            <button
              type="button"
              class="rounded-md border border-slate-300 px-3 py-1.5 text-xs dark:border-slate-700"
              @click="cancelEdit"
            >
              Отмена
            </button>
          </div>
        </template>
        <template v-else>
          <p class="mt-2 text-sm font-medium">{{ template.title }}</p>
          <p class="text-sm text-slate-500">{{ template.body }}</p>
        </template>
      </div>
    </div>
  </div>
</template>
