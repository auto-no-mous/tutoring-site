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
  <div class="mx-auto w-full max-w-sm px-4 py-12">
    <RouterLink to="/" class="block">
      <img
        src="/logo-mark.svg"
        alt="my-tutor.ru"
        class="mx-auto h-16 w-auto transition-transform duration-300 hover:scale-105 dark:hidden"
      />
      <img
        src="/logo-mark-dark.svg"
        alt=""
        class="mx-auto hidden h-16 w-auto transition-transform duration-300 hover:scale-105 dark:block"
      />
    </RouterLink>
    <div class="surface-card animate-pop-in mt-6 flex flex-col gap-4 p-6">
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
          class="btn-primary w-full"
        >
          Отправить ссылку
        </button>
      </form>

      <RouterLink v-if="!isSent" to="/login" class="text-sm text-slate-500 hover:underline">
        Вспомнили пароль? Войти
      </RouterLink>
    </div>
  </div>
</template>
