<script setup lang="ts">
import { ChevronDown, Mail, MailWarning, Search, Send } from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";

import { getEmailStats, listEmails, listStudents, listTutors, sendAdminEmail } from "@/api/admin";
import { useToastStore } from "@/stores/toast";
import type { EmailLogEntry, EmailStats } from "@/types/email";
import { formatDateTimeWithMsk } from "@/utils/time";

const toast = useToastStore();

const PAGE_SIZE = 50;

const KIND_LABELS: Record<string, string> = {
  verification: "Подтверждение почты",
  password_reset: "Сброс пароля",
  admin: "Письмо администратора",
  notification: "Уведомление о занятии",
  inbound: "Входящее",
  other: "Прочее",
};

const stats = ref<EmailStats | null>(null);
const entries = ref<EmailLogEntry[]>([]);
const total = ref(0);
const page = ref(1);
const isLoading = ref(false);

const direction = ref("");
const status = ref("");
const kind = ref("");
const search = ref("");

// --- Написать письмо ---
const showCompose = ref(false);
const recipients = ref<{ id: string; label: string; email: string; role: string }[]>([]);
const selectedIds = ref<string[]>([]);
const recipientSearch = ref("");
const extraEmails = ref("");
const subject = ref("");
const body = ref("");
const isSending = ref(false);

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)));

const filteredRecipients = computed(() => {
  const query = recipientSearch.value.trim().toLowerCase();
  if (!query) return recipients.value;
  return recipients.value.filter(
    (r) => r.label.toLowerCase().includes(query) || r.email.toLowerCase().includes(query),
  );
});

const selectedCount = computed(
  () => selectedIds.value.length + extraEmails.value.split(",").filter((e) => e.trim()).length,
);

async function loadLog(): Promise<void> {
  isLoading.value = true;
  try {
    const result = await listEmails({
      direction: direction.value || undefined,
      status: status.value || undefined,
      kind: kind.value || undefined,
      q: search.value.trim() || undefined,
      page: page.value,
      page_size: PAGE_SIZE,
    });
    entries.value = result.entries;
    total.value = result.total;
  } finally {
    isLoading.value = false;
  }
}

async function loadStats(): Promise<void> {
  stats.value = await getEmailStats();
}

// Список получателей для формы письма: ученики и репетиторы, у которых есть почта.
async function loadRecipients(): Promise<void> {
  const [students, tutors] = await Promise.all([listStudents(), listTutors()]);
  recipients.value = [
    ...students
      .filter((s) => s.email)
      .map((s) => ({
        id: s.id,
        label: `${s.last_name} ${s.first_name}`.trim() || s.display_name,
        email: s.email as string,
        role: "Ученик",
      })),
    ...tutors
      .filter((t) => t.email)
      .map((t) => ({
        id: t.user_id,
        label: t.display_name ?? `${t.last_name ?? ""} ${t.first_name ?? ""}`.trim(),
        email: t.email as string,
        role: "Репетитор",
      })),
  ];
}

function toggleRecipient(id: string): void {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter((x) => x !== id)
    : [...selectedIds.value, id];
}

async function submit(): Promise<void> {
  isSending.value = true;
  try {
    const result = await sendAdminEmail({
      user_ids: selectedIds.value,
      emails: extraEmails.value
        .split(",")
        .map((e) => e.trim())
        .filter(Boolean),
      subject: subject.value.trim(),
      body: body.value,
    });
    toast.show(
      result.failed > 0
        ? `Отправлено: ${result.sent}, не удалось: ${result.failed}`
        : `Отправлено писем: ${result.sent}`,
    );
    if (result.sent > 0) {
      subject.value = "";
      body.value = "";
      selectedIds.value = [];
      extraEmails.value = "";
      showCompose.value = false;
      await Promise.all([loadLog(), loadStats()]);
    }
  } finally {
    isSending.value = false;
  }
}

// Смена фильтра всегда возвращает на первую страницу: иначе на 3-й странице с
// новым фильтром окажется пустой список.
watch([direction, status, kind], () => {
  page.value = 1;
  loadLog();
});
watch(page, loadLog);

onMounted(async () => {
  await Promise.all([loadStats(), loadLog(), loadRecipients()]);
});
</script>

<template>
  <div class="flex flex-col gap-6">
    <!-- Статистика -->
    <div v-if="stats" class="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="surface-card p-4">
        <div class="text-xs text-slate-500">Отправлено за сутки</div>
        <div class="mt-1 text-2xl font-semibold text-brand-600 dark:text-brand-400">{{ stats.sent_24h }}</div>
      </div>
      <div class="surface-card p-4">
        <div class="text-xs text-slate-500">Ошибок за сутки</div>
        <div class="mt-1 text-2xl font-semibold" :class="stats.failed_24h > 0 ? 'text-red-600 dark:text-red-400' : ''">
          {{ stats.failed_24h }}
        </div>
      </div>
      <div class="surface-card p-4">
        <div class="text-xs text-slate-500">Отправлено за 30 дней</div>
        <div class="mt-1 text-2xl font-semibold">{{ stats.sent_30d }}</div>
        <div v-if="stats.failed_30d > 0" class="text-xs text-red-600 dark:text-red-400">
          ошибок: {{ stats.failed_30d }}
        </div>
      </div>
      <div class="surface-card p-4">
        <div class="text-xs text-slate-500">Входящих за 30 дней</div>
        <div class="mt-1 text-2xl font-semibold">{{ stats.received_30d }}</div>
      </div>
    </div>
    <p v-if="stats?.by_kind && Object.keys(stats.by_kind).length > 0" class="-mt-3 text-xs text-slate-500">
      За 30 дней:
      <span v-for="(count, name) in stats.by_kind" :key="name" class="mr-3">
        {{ KIND_LABELS[name] ?? name }} — {{ count }}
      </span>
      <span v-if="stats.last_sent_at">· последнее письмо {{ formatDateTimeWithMsk(stats.last_sent_at) }}</span>
    </p>

    <!-- Написать письмо -->
    <div class="surface-card p-4">
      <button
        type="button"
        class="flex w-full items-center gap-2 text-left text-base font-semibold"
        @click="showCompose = !showCompose"
      >
        <Send class="h-4 w-4 text-brand-600 dark:text-brand-400" />
        Написать письмо пользователям
        <ChevronDown class="ml-auto h-4 w-4 transition-transform duration-300" :class="{ 'rotate-180': showCompose }" />
      </button>

      <Transition name="collapse">
        <div v-if="showCompose">
          <div class="collapse-inner">
            <form class="mt-4 flex flex-col gap-3" @submit.prevent="submit">
              <label class="flex flex-col gap-1 text-sm">
                Получатели
                <div class="relative">
                  <Search class="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
                  <input
                    v-model="recipientSearch"
                    placeholder="Поиск по имени или почте"
                    class="w-full rounded-lg border border-slate-300 bg-transparent py-2 pl-8 pr-3 text-sm dark:border-slate-700"
                  />
                </div>
              </label>
              <div class="max-h-52 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-800">
                <label
                  v-for="person in filteredRecipients"
                  :key="person.id"
                  class="flex cursor-pointer items-center gap-2 border-b border-slate-100 px-3 py-2 text-sm last:border-0 hover:bg-brand-50 dark:border-slate-800 dark:hover:bg-brand-900/20"
                >
                  <input
                    type="checkbox"
                    :checked="selectedIds.includes(person.id)"
                    class="h-4 w-4"
                    @change="toggleRecipient(person.id)"
                  />
                  <span class="font-medium">{{ person.label }}</span>
                  <span class="text-slate-500">{{ person.email }}</span>
                  <span class="ml-auto text-xs text-slate-400">{{ person.role }}</span>
                </label>
                <p v-if="filteredRecipients.length === 0" class="px-3 py-2 text-sm text-slate-400">
                  Никого не найдено.
                </p>
              </div>

              <label class="flex flex-col gap-1 text-sm">
                Дополнительные адреса (через запятую)
                <input
                  v-model="extraEmails"
                  placeholder="someone@example.com, other@example.com"
                  class="rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-700"
                />
              </label>

              <label class="flex flex-col gap-1 text-sm">
                Тема
                <input
                  v-model="subject"
                  required
                  maxlength="200"
                  class="rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-700"
                />
              </label>

              <label class="flex flex-col gap-1 text-sm">
                Текст письма
                <textarea
                  v-model="body"
                  required
                  rows="6"
                  maxlength="5000"
                  class="rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-700"
                ></textarea>
              </label>

              <p class="text-xs text-slate-500">
                Каждому получателю уходит отдельное письмо в фирменном оформлении — адреса друг друга они не увидят.
                Ответы придут на info@my-tutor.ru и будут пересланы на вашу почту.
              </p>

              <div class="flex items-center gap-3">
                <button type="submit" class="btn-primary text-sm" :disabled="isSending || selectedCount === 0">
                  <Send class="h-4 w-4" />
                  Отправить ({{ selectedCount }})
                </button>
                <span v-if="isSending" class="text-sm text-slate-500">Отправляем…</span>
              </div>
            </form>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Журнал -->
    <div>
      <div class="flex flex-wrap items-end gap-3">
        <h2 class="text-lg font-semibold">Журнал писем</h2>
        <div class="ml-auto flex flex-wrap gap-2">
          <select v-model="direction" class="filter-select py-1.5 text-sm">
            <option value="">Все письма</option>
            <option value="outbound">Исходящие</option>
            <option value="inbound">Входящие</option>
          </select>
          <select v-model="status" class="filter-select py-1.5 text-sm">
            <option value="">Любой статус</option>
            <option value="sent">Отправлено</option>
            <option value="failed">Ошибка</option>
            <option value="received">Получено</option>
          </select>
          <select v-model="kind" class="filter-select py-1.5 text-sm">
            <option value="">Любой тип</option>
            <option v-for="(label, value) in KIND_LABELS" :key="value" :value="value">{{ label }}</option>
          </select>
          <form class="relative" @submit.prevent="((page = 1), loadLog())">
            <Search class="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
            <input
              v-model="search"
              placeholder="Адрес или тема"
              class="w-52 rounded-lg border border-slate-300 bg-transparent py-1.5 pl-8 pr-3 text-sm dark:border-slate-700"
            />
          </form>
        </div>
      </div>

      <p v-if="isLoading" class="mt-4 text-sm text-slate-400">Загрузка…</p>
      <p v-else-if="entries.length === 0" class="mt-4 text-sm text-slate-400">Писем пока нет.</p>

      <div v-else class="mt-3 flex flex-col gap-2">
        <div
          v-for="entry in entries"
          :key="entry.id"
          class="surface-card p-3 text-sm transition-shadow hover:shadow-md"
        >
          <div class="flex flex-wrap items-center gap-2">
            <MailWarning v-if="entry.status === 'failed'" class="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
            <Mail
              v-else
              class="h-4 w-4 shrink-0"
              :class="entry.direction === 'inbound' ? 'text-aqua-500' : 'text-brand-600 dark:text-brand-400'"
            />
            <span class="font-medium">{{ entry.subject || "(без темы)" }}</span>
            <span class="text-slate-500">
              {{ entry.direction === "inbound" ? entry.address_from : entry.address_to }}
            </span>
            <span
              class="rounded-full px-2 py-0.5 text-xs"
              :class="
                entry.status === 'failed'
                  ? 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300'
                  : 'bg-brand-50 text-brand-800 dark:bg-brand-900/40 dark:text-brand-200'
              "
            >
              {{ KIND_LABELS[entry.kind] ?? entry.kind }}
            </span>
            <span class="ml-auto text-xs text-slate-400">{{ formatDateTimeWithMsk(entry.created_at) }}</span>
          </div>
          <p v-if="entry.error" class="mt-1 text-xs text-red-600 dark:text-red-400">{{ entry.error }}</p>
          <p v-else-if="entry.body_preview" class="mt-1 line-clamp-2 text-xs text-slate-500">
            {{ entry.body_preview }}
          </p>
        </div>
      </div>

      <div v-if="pageCount > 1" class="mt-4 flex items-center justify-center gap-3 text-sm">
        <button type="button" class="btn-outline px-3 py-1 text-sm" :disabled="page <= 1" @click="page--">
          Назад
        </button>
        <span class="text-slate-500">{{ page }} из {{ pageCount }}</span>
        <button type="button" class="btn-outline px-3 py-1 text-sm" :disabled="page >= pageCount" @click="page++">
          Вперёд
        </button>
      </div>
    </div>
  </div>
</template>
