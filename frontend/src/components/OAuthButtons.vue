<script setup lang="ts">
import { onMounted, ref } from "vue";

import { listOAuthProviders, startOAuth, type OAuthProviderName } from "@/api/auth";
import { apiErrorMessage } from "@/utils/apiError";

const props = defineProps<{
  // Куда вернуть пользователя после входа. Только путь внутри сайта - сервер
  // отвергает всё остальное (см. schemas/oauth.py).
  redirectTo?: string | null;
}>();

// Фирменные цвета провайдеров: кнопку соцсети узнают по ней, а не по подписи.
const PROVIDER_STYLES: Record<OAuthProviderName, { bg: string; title: string }> = {
  vk: { bg: "#0077FF", title: "VK ID" },
  yandex: { bg: "#FC3F1D", title: "Яндекс ID" },
};

const providers = ref<{ provider: OAuthProviderName; label: string }[]>([]);
const error = ref<string | null>(null);
const pending = ref<OAuthProviderName | null>(null);

onMounted(async () => {
  try {
    // Провайдер без настроенных кред на сервере кнопку не получает: вести человека
    // в заведомо мёртвый поток хуже, чем не показать вариант.
    providers.value = (await listOAuthProviders()).filter((p) => p.enabled);
  } catch {
    providers.value = [];
  }
});

async function signIn(provider: OAuthProviderName): Promise<void> {
  error.value = null;
  pending.value = provider;
  try {
    window.location.href = await startOAuth(provider, props.redirectTo ?? null);
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось начать вход. Попробуйте позже.");
    pending.value = null;
  }
}
</script>

<template>
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
        :disabled="pending !== null"
        :style="{ backgroundColor: PROVIDER_STYLES[provider.provider].bg }"
        class="flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
        @click="signIn(provider.provider)"
      >
        <span class="font-bold">{{ provider.provider === "vk" ? "VK" : "Я" }}</span>
        <span>{{ PROVIDER_STYLES[provider.provider].title }}</span>
      </button>
    </div>
    <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
  </div>
</template>
