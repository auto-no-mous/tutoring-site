<script setup lang="ts">
import { onMounted, ref } from "vue";

import { listMyRecurringSeries, stopSeries } from "@/api/bookings";
import { getMyProfile, updateMyProfile } from "@/api/tutors";
import { updateMySettings } from "@/api/users";
import { useAuthStore } from "@/stores/auth";
import type { RecurringSeriesDetail } from "@/types/booking";
import type { TutorProfile } from "@/types/tutor";

const WEEKDAY_NAMES = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

const auth = useAuthStore();
const firstName = ref(auth.user?.first_name ?? "");
const lastName = ref(auth.user?.last_name ?? "");
const patronymic = ref(auth.user?.patronymic ?? "");
const email = ref(auth.user?.email ?? "");
const timezone = ref(auth.user?.timezone ?? "Europe/Moscow");
const telegramChatId = ref(auth.user?.telegram_chat_id ?? "");
const emailNotifications = ref(auth.user?.email_notifications_enabled ?? true);
const savedMessage = ref("");
const emailError = ref("");

const tutorProfile = ref<TutorProfile | null>(null);
const policySavedMessage = ref("");
const isSavingPolicy = ref(false);

const recurringSeries = ref<RecurringSeriesDetail[]>([]);

async function load(): Promise<void> {
  if (auth.user?.role === "tutor") {
    tutorProfile.value = await getMyProfile();
  }
  if (auth.user?.role === "student") {
    recurringSeries.value = await listMyRecurringSeries();
  }
}

async function stopOneSeries(series: RecurringSeriesDetail): Promise<void> {
  if (!window.confirm("Остановить еженедельную регулярность? Уже созданные занятия останутся.")) return;
  await stopSeries(series.id);
  recurringSeries.value = await listMyRecurringSeries();
}

async function save(): Promise<void> {
  savedMessage.value = "";
  emailError.value = "";
  try {
    const updated = await updateMySettings({
      first_name: firstName.value,
      last_name: lastName.value,
      patronymic: patronymic.value || null,
      email: email.value || undefined,
      timezone: timezone.value,
      telegram_chat_id: telegramChatId.value || null,
      email_notifications_enabled: emailNotifications.value,
    });
    auth.user = updated;
    savedMessage.value = "Сохранено";
  } catch (err: any) {
    if (err?.response?.status === 409) {
      emailError.value = "Эта почта уже используется другим аккаунтом";
    } else {
      emailError.value = "Не удалось сохранить";
    }
  }
}

async function savePolicy(): Promise<void> {
  if (!tutorProfile.value) return;
  isSavingPolicy.value = true;
  policySavedMessage.value = "";
  try {
    tutorProfile.value = await updateMyProfile({
      cancel_min_hours_before: tutorProfile.value.cancel_min_hours_before,
      cancel_max_per_month: tutorProfile.value.cancel_max_per_month,
      reschedule_min_hours_before: tutorProfile.value.reschedule_min_hours_before,
      reschedule_max_per_month: tutorProfile.value.reschedule_max_per_month,
    });
    policySavedMessage.value = "Сохранено";
  } finally {
    isSavingPolicy.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="flex max-w-md flex-col gap-8">
    <section class="flex flex-col gap-4">
      <h2 class="text-lg font-medium">Личные данные</h2>
      <div class="flex gap-2">
        <label class="flex w-1/2 flex-col gap-1 text-sm">
          Фамилия
          <input v-model="lastName" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        </label>
        <label class="flex w-1/2 flex-col gap-1 text-sm">
          Имя
          <input v-model="firstName" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        </label>
      </div>
      <label class="flex flex-col gap-1 text-sm">
        Отчество (необязательно)
        <input v-model="patronymic" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
      </label>

      <label class="flex flex-col gap-1 text-sm">
        Почта
        <input v-model="email" type="email" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        <span v-if="auth.user?.email && !auth.user?.email_verified" class="text-xs text-amber-600 dark:text-amber-400">
          Почта не подтверждена
        </span>
        <span class="text-xs text-slate-400">При смене почты потребуется подтвердить её заново.</span>
        <span v-if="emailError" class="text-xs text-red-600 dark:text-red-400">{{ emailError }}</span>
      </label>

      <label v-if="auth.user?.role === 'student'" class="flex flex-col gap-1 text-sm">
        Часовой пояс
        <input v-model="timezone" placeholder="Europe/Moscow" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        <span class="text-xs text-slate-400">Определяется автоматически, можно скорректировать вручную.</span>
      </label>

      <label class="flex flex-col gap-1 text-sm">
        Telegram chat ID (для уведомлений)
        <input v-model="telegramChatId" placeholder="напишите боту, чтобы узнать свой ID" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
      </label>

      <label class="flex items-center gap-2 text-sm">
        <input v-model="emailNotifications" type="checkbox" />
        Получать уведомления на почту
      </label>

      <div class="flex items-center gap-3">
        <button type="button" class="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm text-white dark:bg-white dark:text-slate-900" @click="save">
          Сохранить
        </button>
        <span v-if="savedMessage" class="text-sm text-green-600 dark:text-green-400">{{ savedMessage }}</span>
      </div>
    </section>

    <section v-if="auth.user?.role === 'student'" class="flex flex-col gap-3">
      <h2 class="text-lg font-medium">Регулярные занятия</h2>
      <p v-if="recurringSeries.length === 0" class="text-sm text-slate-400">
        Еженедельных записей нет.
      </p>
      <div
        v-for="series in recurringSeries"
        :key="series.id"
        class="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800"
      >
        <div>
          {{ WEEKDAY_NAMES[series.weekday] }}, {{ series.start_time.slice(0, 5) }} — {{ series.lesson_type_name }}.
          Репетитор {{ series.tutor_display_name }}
        </div>
        <button
          type="button"
          class="shrink-0 rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800"
          @click="stopOneSeries(series)"
        >
          Остановить
        </button>
      </div>
    </section>

    <section v-if="tutorProfile" class="flex flex-col gap-3">
      <h2 class="text-lg font-medium">Отмена и перенос (индивидуальные занятия)</h2>
      <div class="grid grid-cols-2 gap-3 text-sm">
        <label class="flex flex-col gap-1">
          Отмена не позднее, ч
          <input v-model.number="tutorProfile.cancel_min_hours_before" type="number" min="0" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1">
          Лимит отмен в месяц
          <input v-model.number="tutorProfile.cancel_max_per_month" type="number" min="0" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1">
          Перенос не позднее, ч
          <input v-model.number="tutorProfile.reschedule_min_hours_before" type="number" min="0" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1">
          Лимит переносов в месяц
          <input v-model.number="tutorProfile.reschedule_max_per_month" type="number" min="0" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        </label>
      </div>
      <div class="flex items-center gap-3">
        <button type="button" :disabled="isSavingPolicy" class="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-slate-900" @click="savePolicy">
          Сохранить
        </button>
        <span v-if="policySavedMessage" class="text-sm text-green-600 dark:text-green-400">{{ policySavedMessage }}</span>
      </div>
    </section>
  </div>
</template>
