<script setup lang="ts">
import axios from "axios";
import { onMounted, ref } from "vue";

import {
  listOAuthProviders,
  startOAuth,
  unlinkOAuthProvider,
  type OAuthProviderName,
} from "@/api/auth";
import { listMyRecurringSeries, stopSeries } from "@/api/bookings";
import { getMyProfile, updateMyProfile } from "@/api/tutors";
import {
  deleteMyPhoto,
  getTelegramLinkToken,
  resendVerificationEmail,
  updateMySettings,
  uploadMyPhoto,
} from "@/api/users";
import PhotoCropModal from "@/components/PhotoCropModal.vue";
import { useAuthStore } from "@/stores/auth";
import { apiErrorMessage } from "@/utils/apiError";
import type { RecurringSeriesDetail } from "@/types/booking";
import type { NotificationChannel } from "@/types/user";
import type { TutorProfile } from "@/types/tutor";

// needsTelegram - вариант бессмысленен без привязанного мессенджера: уведомления
// просто некуда слать. Такие кнопки выключаются, пока Telegram не подключён.
const NOTIFICATION_CHANNELS: { value: NotificationChannel; label: string; needsTelegram: boolean }[] = [
  { value: "both", label: "Почта и мессенджер", needsTelegram: true },
  { value: "email", label: "Только почта", needsTelegram: false },
  { value: "telegram", label: "Только мессенджер", needsTelegram: true },
  { value: "off", label: "Не присылать", needsTelegram: false },
];

const WEEKDAY_NAMES = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

const auth = useAuthStore();
const firstName = ref(auth.user?.first_name ?? "");
const lastName = ref(auth.user?.last_name ?? "");
const patronymic = ref(auth.user?.patronymic ?? "");
const grade = ref<number | null>(auth.user?.grade ?? null);
const email = ref(auth.user?.email ?? "");
const timezone = ref(auth.user?.timezone ?? "Europe/Moscow");
const notificationChannel = ref<NotificationChannel>(auth.user?.notification_channel ?? "both");
const reminderLeadMinutes = ref(auth.user?.reminder_lead_minutes ?? 60);
const savedMessage = ref("");
const emailError = ref("");
const resendMessage = ref("");
const isResending = ref(false);

const telegramDeepLink = ref<string | null>(null);
const telegramLinkError = ref("");
const isLinkingTelegram = ref(false);
const isCheckingTelegram = ref(false);

const tutorProfile = ref<TutorProfile | null>(null);
const policySavedMessage = ref("");
const isSavingPolicy = ref(false);

const recurringSeries = ref<RecurringSeriesDetail[]>([]);

// Способы входа: пароль + привязанные провайдеры (auth.user.auth_providers).
const oauthProviders = ref<{ provider: OAuthProviderName; label: string }[]>([]);
const identityError = ref("");
const pendingProvider = ref<OAuthProviderName | null>(null);

function isLinked(provider: OAuthProviderName): boolean {
  return auth.user?.auth_providers.includes(provider) ?? false;
}

async function linkProvider(provider: OAuthProviderName): Promise<void> {
  identityError.value = "";
  pendingProvider.value = provider;
  try {
    // Возвращаемся сразу на эту же вкладку, чтобы список обновился на глазах.
    window.location.href = await startOAuth(provider, "/cabinet?tab=settings");
  } catch (err) {
    identityError.value = apiErrorMessage(err, "Не удалось начать привязку");
    pendingProvider.value = null;
  }
}

async function unlinkProvider(provider: OAuthProviderName): Promise<void> {
  identityError.value = "";
  try {
    auth.user = await unlinkOAuthProvider(provider);
  } catch (err) {
    // Сервер не даёт снять последний способ входа - показываем его формулировку.
    identityError.value = apiErrorMessage(err, "Не удалось отвязать");
  }
}

async function load(): Promise<void> {
  try {
    oauthProviders.value = (await listOAuthProviders()).filter((p) => p.enabled);
  } catch {
    oauthProviders.value = [];
  }
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

// Фото аккаунта. Как и у репетитора в анкете, файл не уходит на сервер сразу:
// сначала пользователь выбирает кадр в PhotoCropModal, иначе квадратная миниатюра
// нередко срезает лицо.
const photoToCrop = ref<File | null>(null);
const photoError = ref("");

function onPhotoChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  // Сбрасываем input сразу: иначе повторный выбор того же файла не вызовет change.
  input.value = "";
  photoToCrop.value = file;
}

async function onPhotoCropped(blob: Blob): Promise<void> {
  photoToCrop.value = null;
  photoError.value = "";
  try {
    auth.user = await uploadMyPhoto(blob);
  } catch (err) {
    photoError.value = apiErrorMessage(err, "Не удалось загрузить фото");
  }
}

async function removePhoto(): Promise<void> {
  photoError.value = "";
  try {
    auth.user = await deleteMyPhoto();
  } catch (err) {
    photoError.value = apiErrorMessage(err, "Не удалось удалить фото");
  }
}

async function save(): Promise<void> {
  savedMessage.value = "";
  emailError.value = "";
  try {
    const updated = await updateMySettings({
      first_name: firstName.value,
      last_name: lastName.value,
      patronymic: patronymic.value || null,
      grade: grade.value,
      email: email.value || undefined,
      timezone: timezone.value,
      notification_channel: notificationChannel.value,
      reminder_lead_minutes: reminderLeadMinutes.value,
    });
    auth.user = updated;
    savedMessage.value = "Сохранено";
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 409) {
      emailError.value = "Эта почта уже используется другим аккаунтом";
    } else {
      emailError.value = "Не удалось сохранить";
    }
  }
}

async function resendVerification(): Promise<void> {
  isResending.value = true;
  resendMessage.value = "";
  try {
    await resendVerificationEmail();
    resendMessage.value = "Письмо отправлено";
  } catch {
    resendMessage.value = "Не удалось отправить письмо";
  } finally {
    isResending.value = false;
  }
}

async function connectTelegram(): Promise<void> {
  isLinkingTelegram.value = true;
  telegramLinkError.value = "";
  try {
    const { deep_link } = await getTelegramLinkToken();
    if (!deep_link) {
      telegramLinkError.value = "Бот пока не настроен на сервере — обратитесь к администратору.";
      return;
    }
    telegramDeepLink.value = deep_link;
    window.open(deep_link, "_blank");
  } finally {
    isLinkingTelegram.value = false;
  }
}

async function checkTelegramLinked(): Promise<void> {
  isCheckingTelegram.value = true;
  try {
    await auth.fetchCurrentUser();
    if (auth.user?.telegram_chat_id) {
      telegramDeepLink.value = null;
      // При привязке сервер сам переводит канал в "Почта и мессенджер"
      // (backend telegram_service.link_chat_by_token) - забираем это значение в
      // форму, иначе она продолжила бы показывать прежний выбор и затёрла бы его
      // при следующем сохранении.
      notificationChannel.value = auth.user.notification_channel;
    }
  } finally {
    isCheckingTelegram.value = false;
  }
}

async function disconnectTelegram(): Promise<void> {
  const updated = await updateMySettings({ telegram_chat_id: null });
  auth.user = updated;
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

      <!-- Репетитор меняет фото в анкете (вкладка "Профиль"), там оно и показывается
           в каталоге; здесь - аватар аккаунта для остальных ролей. -->
      <div v-if="auth.user?.role !== 'tutor'" class="flex flex-col gap-2">
        <div class="flex items-center gap-4">
          <img
            v-if="auth.user?.photo_url"
            :src="auth.user.photo_url"
            alt=""
            class="h-20 w-20 rounded-full object-cover"
          />
          <div v-else class="h-20 w-20 rounded-full bg-slate-200 dark:bg-slate-800"></div>
          <div class="flex flex-col gap-1">
            <input
              type="file"
              accept="image/*"
              class="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-brand-500 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700 dark:file:bg-white dark:file:text-slate-900 dark:hover:file:bg-slate-200"
              @change="onPhotoChange"
            />
            <button
              v-if="auth.user?.photo_url"
              type="button"
              class="w-fit text-xs text-slate-500 underline"
              @click="removePhoto"
            >
              Удалить фото
            </button>
          </div>
        </div>
        <span v-if="photoError" class="text-xs text-red-600 dark:text-red-400">{{ photoError }}</span>
      </div>

      <PhotoCropModal
        v-if="photoToCrop"
        :file="photoToCrop"
        @cropped="onPhotoCropped"
        @close="photoToCrop = null"
      />

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

      <label v-if="auth.user?.role === 'student'" class="flex flex-col gap-1 text-sm">
        Класс
        <select v-model.number="grade" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700">
          <option :value="null">—</option>
          <option v-for="n in 11" :key="n" :value="n">{{ n }}-й класс</option>
        </select>
      </label>

      <label class="flex flex-col gap-1 text-sm">
        Почта
        <input v-model="email" type="email" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        <div v-if="auth.user?.email && !auth.user?.email_verified" class="flex items-center gap-2 text-xs">
          <span class="text-amber-600 dark:text-amber-400">Почта не подтверждена</span>
          <button type="button" :disabled="isResending" class="text-slate-500 underline disabled:opacity-50" @click="resendVerification">
            Отправить письмо ещё раз
          </button>
          <span v-if="resendMessage" class="text-slate-400">{{ resendMessage }}</span>
        </div>
        <span class="text-xs text-slate-400">При смене почты потребуется подтвердить её заново.</span>
        <span v-if="emailError" class="text-xs text-red-600 dark:text-red-400">{{ emailError }}</span>
      </label>

      <label v-if="auth.user?.role === 'student'" class="flex flex-col gap-1 text-sm">
        Часовой пояс
        <input v-model="timezone" placeholder="Europe/Moscow" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
        <span class="text-xs text-slate-400">Определяется автоматически, можно скорректировать вручную.</span>
      </label>

      <div class="flex flex-col gap-1 text-sm">
        Telegram (для уведомлений)
        <div v-if="auth.user?.telegram_chat_id" class="flex items-center gap-2">
          <span class="text-green-600 dark:text-green-400">Подключён</span>
          <button type="button" class="text-xs text-slate-500 underline" @click="disconnectTelegram">Отключить</button>
        </div>
        <div v-else class="flex flex-col gap-1">
          <button
            type="button"
            :disabled="isLinkingTelegram"
            class="w-fit rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-slate-700"
            @click="connectTelegram"
          >
            Подключить Telegram
          </button>
          <div v-if="telegramDeepLink" class="flex items-center gap-2 text-xs">
            <span class="text-slate-400">Откройте бота, нажмите «Запустить», затем вернитесь сюда.</span>
            <button type="button" :disabled="isCheckingTelegram" class="text-slate-500 underline disabled:opacity-50" @click="checkTelegramLinked">
              Проверить
            </button>
          </div>
          <span v-if="telegramLinkError" class="text-xs text-red-600 dark:text-red-400">{{ telegramLinkError }}</span>
        </div>
      </div>

      <div v-if="oauthProviders.length" class="flex flex-col gap-2 text-sm">
        <span>Способы входа</span>
        <div class="flex items-center gap-2">
          <span class="w-24">Пароль</span>
          <span
            v-if="auth.user?.auth_providers.includes('password')"
            class="text-green-600 dark:text-green-400"
          >
            Задан
          </span>
          <span v-else class="text-slate-400">
            Не задан — вход только через привязанный аккаунт
          </span>
        </div>
        <div v-for="provider in oauthProviders" :key="provider.provider" class="flex items-center gap-2">
          <span class="w-24">{{ provider.label }}</span>
          <template v-if="isLinked(provider.provider)">
            <span class="text-green-600 dark:text-green-400">Привязан</span>
            <button type="button" class="text-xs text-slate-500 underline" @click="unlinkProvider(provider.provider)">
              Отвязать
            </button>
          </template>
          <button
            v-else
            type="button"
            :disabled="pendingProvider !== null"
            class="rounded-md border border-slate-300 px-3 py-1 text-xs disabled:opacity-50 dark:border-slate-700"
            @click="linkProvider(provider.provider)"
          >
            Привязать
          </button>
        </div>
        <span v-if="identityError" class="text-xs text-red-600 dark:text-red-400">{{ identityError }}</span>
        <span class="text-xs text-slate-400">
          Привязанным аккаунтом можно входить на сайт вместо почты и пароля.
        </span>
      </div>

      <label class="flex flex-col gap-1 text-sm">
        Уведомлять о занятии за
        <span class="flex items-center gap-2">
          <input
            v-model.number="reminderLeadMinutes"
            type="number"
            min="1"
            max="10080"
            class="w-24 rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
          />
          мин до его начала
        </span>
        <span class="text-xs text-slate-400">Придёт в Telegram/на почту и в «Системные уведомления». По умолчанию — 60 минут.</span>
      </label>

      <div class="flex flex-col gap-2 text-sm">
        <span>Напоминания о занятиях и уведомления</span>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="option in NOTIFICATION_CHANNELS"
            :key="option.value"
            type="button"
            :disabled="option.needsTelegram && !auth.user?.telegram_chat_id"
            :title="option.needsTelegram && !auth.user?.telegram_chat_id ? 'Сначала подключите Telegram выше' : undefined"
            class="rounded-lg border px-3 py-1.5 transition-colors disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-slate-300 dark:disabled:hover:border-slate-700"
            :class="
              notificationChannel === option.value
                ? 'border-brand-500 bg-brand-50 font-medium text-brand-800 dark:bg-brand-900/40 dark:text-brand-200'
                : 'border-slate-300 text-slate-600 hover:border-brand-400 dark:border-slate-700 dark:text-slate-300'
            "
            @click="notificationChannel = option.value"
          >
            {{ option.label }}
          </button>
        </div>
        <p class="text-xs text-slate-500">
          {{
            !auth.user?.telegram_chat_id && (notificationChannel === "telegram" || notificationChannel === "both")
              ? "Мессенджер сейчас не подключён — уведомления в него приходить не будут. Подключите Telegram выше или выберите «Только почта»."
              : !auth.user?.telegram_chat_id
                ? "Варианты с мессенджером станут доступны после подключения Telegram — кнопка выше."
                : notificationChannel === "off"
                ? "Напоминания и уведомления о занятиях приходить не будут. Письма о регистрации и сбросе пароля отправляются всегда."
                : "Письма о регистрации и сбросе пароля отправляются всегда, независимо от этой настройки."
          }}
        </p>
      </div>

      <div class="flex items-center gap-3">
        <button type="button" class="w-fit rounded-md bg-brand-500 px-4 py-2 text-sm text-white" @click="save">
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
        <button type="button" :disabled="isSavingPolicy" class="w-fit rounded-md bg-brand-500 px-4 py-2 text-sm text-white disabled:opacity-50" @click="savePolicy">
          Сохранить
        </button>
        <span v-if="policySavedMessage" class="text-sm text-green-600 dark:text-green-400">{{ policySavedMessage }}</span>
      </div>
    </section>
  </div>
</template>
