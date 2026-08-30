<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import {
  claimWithPassword,
  getClaimPreview,
  listOAuthProviders,
  startOAuth,
  type ClaimPreview,
  type OAuthProviderName,
} from "@/api/auth";
import { useAuthStore } from "@/stores/auth";
import { apiErrorMessage } from "@/utils/apiError";

// Страница, на которую репетитор присылает ссылку ученику, заведённому вручную.
// Здесь человек задаёт себе способ входа и получает тот же самый профиль - со всеми
// уже проведёнными занятиями, группами и домашкой.
const PROVIDER_COLORS: Record<OAuthProviderName, string> = {
  vk: "#0077FF",
  yandex: "#FC3F1D",
};

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const token = route.params.token as string;

const preview = ref<ClaimPreview | null>(null);
const providers = ref<{ provider: OAuthProviderName; label: string }[]>([]);
const loadError = ref("");
const error = ref("");
const isLoading = ref(true);
const isSubmitting = ref(false);

const email = ref("");
const password = ref("");
const pdConsent = ref(false);

onMounted(async () => {
  try {
    const [previewData, providerList] = await Promise.all([
      getClaimPreview(token),
      listOAuthProviders().catch(() => []),
    ]);
    preview.value = previewData;
    providers.value = providerList.filter((p) => p.enabled);
  } catch (err) {
    loadError.value = apiErrorMessage(err, "Ссылка недействительна.");
  } finally {
    isLoading.value = false;
  }
});

async function submitPassword(): Promise<void> {
  error.value = "";
  if (!pdConsent.value) {
    error.value = "Необходимо согласие на обработку персональных данных";
    return;
  }
  isSubmitting.value = true;
  try {
    const { user, tokens } = await claimWithPassword({
      token,
      email: email.value,
      password: password.value,
      pd_consent: pdConsent.value,
    });
    await auth.applySession(tokens, user);
    await router.replace("/cabinet");
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось привязать вход");
  } finally {
    isSubmitting.value = false;
  }
}

async function useProvider(provider: OAuthProviderName): Promise<void> {
  error.value = "";
  try {
    // Тот же поток, что и обычный вход, только вместо создания аккаунта провайдер
    // привязывается к профилю из ссылки - сервер узнаёт об этом по claim_token.
    window.location.href = await startOAuth(provider, "/cabinet", token);
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось начать вход");
  }
}
</script>

<template>
  <div class="mx-auto w-full max-w-sm px-4 py-12">
    <RouterLink to="/" class="block">
      <img src="/logo-mark.svg" alt="my-tutor.ru" class="mx-auto h-16 w-auto dark:hidden" />
      <img src="/logo-mark-dark.svg" alt="" class="mx-auto hidden h-16 w-auto dark:block" />
    </RouterLink>

    <div class="surface-card animate-pop-in mt-6 flex flex-col gap-4 p-6">
      <p v-if="isLoading" class="text-sm text-slate-400">Загрузка…</p>

      <template v-else-if="loadError">
        <h1 class="text-xl font-semibold">Ссылка не работает</h1>
        <p class="text-sm text-red-600 dark:text-red-400">{{ loadError }}</p>
        <RouterLink to="/" class="btn-primary w-full text-center">На главную</RouterLink>
      </template>

      <template v-else-if="preview">
        <h1 class="text-2xl font-semibold">Ваш профиль у репетитора</h1>
        <div class="rounded-md bg-slate-50 p-3 text-sm dark:bg-slate-800/60">
          <div class="font-medium">{{ preview.display_name }}</div>
          <div v-if="preview.grade" class="text-slate-500 dark:text-slate-400">{{ preview.grade }}-й класс</div>
          <div class="text-slate-500 dark:text-slate-400">Репетитор: {{ preview.tutor_display_name }}</div>
        </div>
        <p class="text-sm text-slate-500">
          Задайте способ входа — и профиль станет вашим вместе со всеми занятиями, группами и домашними заданиями.
        </p>

        <form class="flex flex-col gap-3" @submit.prevent="submitPassword">
          <input
            v-model="email"
            type="email"
            required
            placeholder="Почта"
            class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
          />
          <input
            v-model="password"
            type="password"
            required
            minlength="8"
            placeholder="Пароль (минимум 8 символов)"
            class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
          />
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
          <button type="submit" :disabled="isSubmitting" class="btn-primary w-full">Забрать профиль</button>
        </form>

        <div v-if="providers.length" class="flex flex-col gap-3">
          <div class="flex items-center gap-3 text-xs text-slate-400">
            <span class="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
            или
            <span class="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
          </div>
          <div class="flex gap-2">
            <button
              v-for="provider in providers"
              :key="provider.provider"
              type="button"
              :style="{ backgroundColor: PROVIDER_COLORS[provider.provider] }"
              class="flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
              @click="useProvider(provider.provider)"
            >
              {{ provider.label }}
            </button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
