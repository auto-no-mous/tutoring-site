<script setup lang="ts">
import { ref } from "vue";

import { requestPasswordReset } from "@/api/users";

const email = ref("");
const isSubmitting = ref(false);
const isSent = ref(false);
const error = ref<string | null>(null);

async function onSubmit(): Promise<void> {
  error.value = null;
  isSubmitting.value = true;
  try {
    await requestPasswordReset(email.value);
    isSent.value = true;
  } catch {
    error.value = "Не удалось отправить письмо. Попробуйте ещё раз.";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <div class="mx-auto flex max-w-sm flex-col gap-4 px-4 py-16">
    <h1 class="text-2xl font-semibold">Восстановление пароля</h1>

    <template v-if="isSent">
      <p class="text-sm text-slate-500">
        Если почта <span class="font-medium">{{ email }}</span> зарегистрирована, на неё отправлена ссылка для
        сброса пароля.
      </p>
      <RouterLink to="/login" class="text-sm text-slate-500 hover:underline">Вернуться ко входу</RouterLink>
    </template>

    <form v-else class="flex flex-col gap-3" @submit.prevent="onSubmit">
      <p class="text-sm text-slate-500">Укажите почту, на которую зарегистрирован аккаунт — пришлём ссылку для сброса пароля.</p>
      <input
        v-model="email"
        type="email"
        required
        placeholder="Почта"
        class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
      />
      <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
      <button
        type="submit"
        :disabled="isSubmitting"
        class="rounded-md bg-slate-900 px-3 py-2 text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"
      >
        Отправить ссылку
      </button>
    </form>

    <RouterLink v-if="!isSent" to="/login" class="text-sm text-slate-500 hover:underline">
      Вспомнили пароль? Войти
    </RouterLink>
  </div>
</template>
