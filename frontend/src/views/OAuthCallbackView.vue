<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { completeOAuthSignup, finishOAuth, type OAuthProviderName } from "@/api/auth";
import { useAuthStore } from "@/stores/auth";
import { apiErrorMessage } from "@/utils/apiError";
import type { UserRole } from "@/types/user";

const PROVIDER_LABELS: Record<OAuthProviderName, string> = {
  vk: "VK ID",
  yandex: "Яндекс ID",
};

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const provider = route.params.provider as OAuthProviderName;
const providerLabel = PROVIDER_LABELS[provider] ?? "провайдера";

// exchanging - идёт обмен кода; signup - провайдер опознан, но аккаунта ещё нет и
// нужен второй шаг; error - показываем причину и путь назад.
const phase = ref<"exchanging" | "signup" | "error">("exchanging");
const error = ref<string | null>(null);

const signupToken = ref("");
// Имя, почта и аватар приходят от провайдера и правке не подлежат: их берёт сам
// сервер из подписанного signup-токена. Здесь они только показываются.
const providerName = ref<string | null>(null);
const providerEmail = ref<string | null>(null);
const providerAvatar = ref<string | null>(null);
// Заполняются вручную только в редком случае, когда провайдер имени не отдал.
const firstName = ref("");
const lastName = ref("");
const needsName = ref(false);

const role = ref<Exclude<UserRole, "admin">>("student");
const grade = ref<number | null>(null);
const pdConsent = ref(false);
const redirectTo = ref<string | null>(null);
const isSubmitting = ref(false);

const canSubmit = computed(
  () => !isSubmitting.value && (!needsName.value || (!!firstName.value && !!lastName.value)),
);

function queryValue(name: string): string | null {
  const value = route.query[name];
  return typeof value === "string" ? value : null;
}

onMounted(async () => {
  // Пользователь мог нажать "Отмена" на стороне провайдера - тогда кода нет, а есть
  // error/error_description.
  const providerError = queryValue("error");
  const code = queryValue("code");
  const state = queryValue("state");
  if (providerError || !code || !state) {
    phase.value = "error";
    error.value = providerError
      ? `${providerLabel} отклонил вход: ${queryValue("error_description") ?? providerError}`
      : "Ссылка возврата неполная. Попробуйте войти ещё раз.";
    return;
  }

  try {
    const result = await finishOAuth(provider, {
      code,
      state,
      // VK передаёт device_id в колбэке и требует его при обмене кода; у Яндекса
      // такого параметра нет.
      device_id: queryValue("device_id"),
    });
    redirectTo.value = result.redirect_to;

    if (result.status === "authenticated" && result.tokens) {
      await auth.applySession(result.tokens, result.user);
      await router.replace(result.redirect_to ?? "/cabinet");
      return;
    }
    if (result.status === "linked") {
      // Привязка из настроек: обновляем пользователя, чтобы список способов входа
      // отрисовался уже с новым провайдером.
      await auth.fetchCurrentUser();
      await router.replace(result.redirect_to ?? "/cabinet?tab=settings");
      return;
    }

    signupToken.value = result.signup_token ?? "";
    providerEmail.value = result.prefill?.email ?? null;
    providerAvatar.value = result.prefill?.avatar_url ?? null;
    const first = result.prefill?.first_name ?? "";
    const last = result.prefill?.last_name ?? "";
    needsName.value = !first || !last;
    providerName.value = needsName.value ? null : `${last} ${first}`;
    phase.value = "signup";
  } catch (err) {
    phase.value = "error";
    error.value = apiErrorMessage(err, `Не удалось войти через ${providerLabel}.`);
  }
});

async function submitSignup(): Promise<void> {
  error.value = null;
  if (!pdConsent.value) {
    error.value = "Необходимо согласие на обработку персональных данных";
    return;
  }
  isSubmitting.value = true;
  try {
    const { user, tokens } = await completeOAuthSignup({
      signup_token: signupToken.value,
      role: role.value,
      grade: role.value === "student" ? grade.value : null,
      first_name: needsName.value ? firstName.value : null,
      last_name: needsName.value ? lastName.value : null,
      pd_consent: pdConsent.value,
    });
    await auth.applySession(tokens, user);
    await router.replace(redirectTo.value ?? "/cabinet");
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось завершить регистрацию.");
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <div class="mx-auto w-full max-w-sm px-4 py-12">
    <div class="surface-card animate-pop-in flex flex-col gap-4 p-6">
      <template v-if="phase === 'exchanging'">
        <h1 class="text-xl font-semibold">Входим через {{ providerLabel }}…</h1>
        <p class="text-sm text-slate-500">Секунду, проверяем данные.</p>
      </template>

      <template v-else-if="phase === 'signup'">
        <h1 class="text-2xl font-semibold">Почти готово</h1>

        <div class="flex items-center gap-3 rounded-md bg-slate-50 p-3 dark:bg-slate-800/60">
          <img
            v-if="providerAvatar"
            :src="providerAvatar"
            alt=""
            class="h-12 w-12 rounded-full object-cover"
          />
          <div class="flex flex-col text-sm">
            <span v-if="providerName" class="font-medium">{{ providerName }}</span>
            <span v-if="providerEmail" class="text-slate-500">{{ providerEmail }}</span>
            <span class="text-xs text-slate-400">Данные из {{ providerLabel }}</span>
          </div>
        </div>

        <form class="flex flex-col gap-3" @submit.prevent="submitSignup">
          <!-- Обычно провайдер отдаёт имя сам; поля появляются, только если не отдал. -->
          <template v-if="needsName">
            <input
              v-model="lastName"
              required
              placeholder="Фамилия"
              class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
            />
            <input
              v-model="firstName"
              required
              placeholder="Имя"
              class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
            />
          </template>

          <div class="flex flex-col gap-1 text-sm">
            <span class="text-slate-500">Кем вы будете на сайте</span>
            <div class="flex rounded-md border border-slate-300 p-1 dark:border-slate-700">
              <button
                type="button"
                class="flex-1 rounded px-3 py-1.5 text-sm transition-colors"
                :class="role === 'student' ? 'bg-brand-500 text-white' : 'text-slate-500'"
                @click="role = 'student'"
              >
                Ученик
              </button>
              <button
                type="button"
                class="flex-1 rounded px-3 py-1.5 text-sm transition-colors"
                :class="role === 'tutor' ? 'bg-brand-500 text-white' : 'text-slate-500'"
                @click="role = 'tutor'"
              >
                Репетитор
              </button>
            </div>
          </div>

          <label v-if="role === 'student'" class="flex flex-col gap-1 text-sm">
            Класс
            <select
              v-model.number="grade"
              class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
            >
              <option :value="null">Не указывать</option>
              <option v-for="n in 11" :key="n" :value="n">{{ n }}-й класс</option>
            </select>
          </label>

          <label class="flex items-start gap-2 text-sm">
            <input v-model="pdConsent" type="checkbox" class="mt-1" />
            <span>
              Согласен(на) с
              <RouterLink to="/legal/privacy" class="underline">политикой конфиденциальности</RouterLink>,
              <RouterLink to="/legal/agreement" class="underline">пользовательским соглашением</RouterLink>
              и обработкой персональных данных
            </span>
          </label>
          <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
          <button type="submit" :disabled="!canSubmit" class="btn-primary w-full">
            Завершить регистрацию
          </button>
        </form>
      </template>

      <template v-else>
        <h1 class="text-xl font-semibold">Не получилось</h1>
        <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
        <RouterLink to="/login" class="btn-primary w-full text-center">Вернуться ко входу</RouterLink>
      </template>
    </div>
  </div>
</template>
