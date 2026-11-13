<script setup lang="ts">
import axios from "axios";
import { computed, onBeforeUnmount, onMounted, ref, toRaw } from "vue";

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
  disconnectTelegram as disconnectTelegramApi,
  disconnectVk,
  getTelegramLinkToken,
  getVkLink,
  resendVerificationEmail,
  updateMySettings,
  uploadMyPhoto,
} from "@/api/users";
import NotificationSettingsEditor from "@/components/NotificationSettingsEditor.vue";
import PhotoCropModal from "@/components/PhotoCropModal.vue";
import { useAuthStore } from "@/stores/auth";
import { detectTimezone, timezoneOptions } from "@/utils/timezones";
import { apiErrorMessage } from "@/utils/apiError";
import type { RecurringSeriesDetail } from "@/types/booking";
import type { NotificationSettings } from "@/types/user";
import type { TutorProfile } from "@/types/tutor";

const WEEKDAY_NAMES = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

const auth = useAuthStore();
const firstName = ref(auth.user?.first_name ?? "");
const lastName = ref(auth.user?.last_name ?? "");
const patronymic = ref(auth.user?.patronymic ?? "");
const grade = ref<number | null>(auth.user?.grade ?? null);
const email = ref(auth.user?.email ?? "");
// Если пояс ещё не выбирали, предлагаем тот, что сообщает браузер.
const timezone = ref(auth.user?.timezone || detectTimezone());
const timezones = computed(() => timezoneOptions(auth.user?.timezone));
// Копия, а не ссылка на auth.user: до «Сохранить» правки живут только в форме.
// toRaw обязателен: пользователь в сторе реактивный, а structuredClone на прокси Vue
// бросает DataCloneError - и вся вкладка не отображалась.
const notificationSettings = ref<NotificationSettings | null>(
  auth.user ? structuredClone(toRaw(auth.user.notification_settings)) : null,
);
const savedMessage = ref("");
const emailError = ref("");
const resendMessage = ref("");
const isResending = ref(false);

const telegramDeepLink = ref<string | null>(null);
const telegramLinkError = ref("");
const isLinkingTelegram = ref(false);

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
      notification_settings: notificationSettings.value ?? undefined,
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
    waitForLink();
  } finally {
    isLinkingTelegram.value = false;
  }
}

// --- ВКонтакте: привязка как у Telegram, через диалог с сообществом -------------

const vkLink = ref<{ code: string; link: string } | null>(null);
const vkLinkError = ref("");
const isLinkingVk = ref(false);

async function connectVk(): Promise<void> {
  isLinkingVk.value = true;
  vkLinkError.value = "";
  try {
    const { code, link } = await getVkLink();
    if (!link) {
      vkLinkError.value = "ВКонтакте пока не настроен на сервере — обратитесь к администратору.";
      return;
    }
    vkLink.value = { code, link };
    window.open(link, "_blank");
    waitForLink();
  } finally {
    isLinkingVk.value = false;
  }
}

// --- Ждём, пока бот привяжет аккаунт --------------------------------------------
//
// Привязка заканчивается в мессенджере, а не здесь: человек жмёт «Начать» у бота, и
// сайт об этом сам не узнаёт. Раньше нужно было нажать «Проверить» или обновить
// страницу, и кнопка «Подключить» висела, хотя всё уже работало. Теперь, пока ссылка
// открыта, страница сама спрашивает сервер раз в несколько секунд и сразу при
// возвращении на вкладку.

const LINK_POLL_MS = 3000;
// Дольше пяти минут не ждём: код привязки живёт 15, но столько на вкладке не сидят.
const LINK_POLL_LIMIT = 100;
let linkPollTimer: number | undefined;
let linkPollTicks = 0;

function isWaitingForLink(): boolean {
  return Boolean(telegramDeepLink.value || vkLink.value);
}

async function checkLinks(): Promise<void> {
  if (!isWaitingForLink()) return;
  await auth.fetchCurrentUser();
  const user = auth.user;
  if (!user) return;
  // При привязке сервер сам включает канал (telegram_service.link_chat_by_token,
  // vk_service.link_peer_by_code) - забираем это в форму, иначе она показывала бы
  // канал выключенным и затёрла бы его при следующем сохранении.
  if (telegramDeepLink.value && user.telegram_chat_id) {
    telegramDeepLink.value = null;
    if (notificationSettings.value) notificationSettings.value.telegram.enabled = user.notification_settings.telegram.enabled;
  }
  if (vkLink.value && user.vk_connected) {
    vkLink.value = null;
    if (notificationSettings.value) notificationSettings.value.vk.enabled = user.notification_settings.vk.enabled;
  }
  if (!isWaitingForLink()) stopWaitingForLink();
}

function stopWaitingForLink(): void {
  window.clearInterval(linkPollTimer);
  linkPollTimer = undefined;
}

function waitForLink(): void {
  stopWaitingForLink();
  linkPollTicks = 0;
  linkPollTimer = window.setInterval(() => {
    linkPollTicks += 1;
    if (linkPollTicks > LINK_POLL_LIMIT) {
      stopWaitingForLink();
      return;
    }
    void checkLinks();
  }, LINK_POLL_MS);
}

function onWindowFocus(): void {
  void checkLinks();
}

onMounted(() => window.addEventListener("focus", onWindowFocus));
onBeforeUnmount(() => {
  window.removeEventListener("focus", onWindowFocus);
  stopWaitingForLink();
});

async function onDisconnectVk(): Promise<void> {
  auth.user = await disconnectVk();
}

async function disconnectTelegram(): Promise<void> {
  const updated = await disconnectTelegramApi();
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
        <select v-model="timezone" class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700">
          <option v-for="tz in timezones" :key="tz.value" :value="tz.value">{{ tz.label }}</option>
        </select>
        <span class="text-xs text-slate-500">
          Время занятий на сайте и в письмах — московское. Пояс нужен, чтобы подсказывать,
          который час это у вас.
        </span>
        <span class="text-xs text-slate-400">Определяется автоматически, можно скорректировать вручную.</span>
      </label>

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

      <div v-if="notificationSettings" class="flex flex-col gap-2 text-sm">
        <span>Уведомления</span>
        <NotificationSettingsEditor
          v-model="notificationSettings"
          :available="{
            telegram: Boolean(auth.user?.telegram_chat_id),
            email: Boolean(auth.user?.email),
            vk: Boolean(auth.user?.vk_connected),
          }"
          :unavailable-hint="{
            telegram: 'Telegram не подключён — кнопка «Подключить Telegram» выше.',
            email: 'Почта не указана — впишите её в поле «Почта» выше и сохраните.',
            vk: 'ВКонтакте не подключён.',
          }"
        >
          <template #connection-telegram>
            <span v-if="auth.user?.telegram_chat_id" class="flex items-center gap-2 text-xs">
              <span class="text-green-600 dark:text-green-400">Подключён</span>
              <button type="button" class="text-slate-500 underline" @click="disconnectTelegram">Отключить</button>
            </span>
            <button
              v-else
              type="button"
              :disabled="isLinkingTelegram"
              class="rounded-md bg-brand-500 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
              @click="connectTelegram"
            >
              Подключить Telegram
            </button>
            <p v-if="!auth.user?.telegram_chat_id && telegramDeepLink" class="basis-full text-xs text-slate-400" data-link-pending>
              Откройте бота и нажмите «Запустить» — эта страница сама заметит подключение.
            </p>
            <p v-if="telegramLinkError" class="basis-full text-xs text-red-600 dark:text-red-400">{{ telegramLinkError }}</p>
          </template>
          <template #connection-vk>
            <span v-if="auth.user?.vk_connected" class="flex items-center gap-2 text-xs" data-vk-link>
              <span class="text-green-600 dark:text-green-400">Подключён</span>
              <button type="button" class="text-slate-500 underline" @click="onDisconnectVk">Отключить</button>
            </span>
            <button
              v-else
              type="button"
              :disabled="isLinkingVk"
              class="rounded-md bg-brand-500 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
              data-vk-link
              @click="connectVk"
            >
              Подключить ВКонтакте
            </button>
            <p v-if="!auth.user?.vk_connected && vkLink" class="basis-full text-xs text-slate-400" data-link-pending>
              В диалоге с сообществом нажмите «Начать» — эта страница сама заметит подключение. Если бот не ответил,
              отправьте ему код <b class="font-mono text-slate-600 dark:text-slate-300">{{ vkLink.code }}</b>
              (<a :href="vkLink.link" target="_blank" class="underline">открыть диалог ещё раз</a>).
            </p>
            <p v-if="vkLinkError" class="basis-full text-xs text-red-600 dark:text-red-400">{{ vkLinkError }}</p>
          </template>
        </NotificationSettingsEditor>
        <p class="text-xs text-slate-500">
          <template v-if="auth.user?.role === 'tutor'">
            Сообщения в чате и заявки в группы приходят в каждый включённый канал.
          </template>
          Письма о регистрации и сбросе пароля отправляются всегда.
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
