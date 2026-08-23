<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";

import { confirmPasswordReset } from "@/api/users";

const route = useRoute();
const token = computed(() => (typeof route.query.token === "string" ? route.query.token : ""));

const newPassword = ref("");
const confirmPassword = ref("");
const isSubmitting = ref(false);
const status = ref<"form" | "success" | "error">(token.value ? "form" : "error");
const error = ref("");

async function onSubmit(): Promise<void> {
  error.value = "";
  if (newPassword.value !== confirmPassword.value) {
    error.value = "Пароли не совпадают";
    return;
  }
  isSubmitting.value = true;
  try {
    await confirmPasswordReset(token.value, newPassword.value);
    status.value = "success";
  } catch {
    error.value = "Ссылка недействительна или устарела.";
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
      <h1 class="text-2xl font-semibold">Новый пароль</h1>

      <template v-if="status === 'success'">
        <p class="text-sm text-green-600 dark:text-green-400">Пароль обновлён.</p>
        <RouterLink
          to="/login"
          class="w-fit rounded-md bg-brand-500 px-4 py-2 text-sm text-white"
        >
          Войти
        </RouterLink>
      </template>

      <template v-else-if="!token">
        <p class="text-sm text-red-600 dark:text-red-400">В ссылке нет кода сброса пароля.</p>
        <RouterLink to="/forgot-password" class="text-sm text-slate-500 hover:underline">Запросить новую ссылку</RouterLink>
      </template>

      <form v-else class="flex flex-col gap-3" @submit.prevent="onSubmit">
        <input
          v-model="newPassword"
          type="password"
          required
          minlength="8"
          placeholder="Новый пароль (минимум 8 символов)"
          class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        />
        <input
          v-model="confirmPassword"
          type="password"
          required
          minlength="8"
          placeholder="Повторите новый пароль"
          class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        />
        <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
        <button
          type="submit"
          :disabled="isSubmitting"
          class="btn-primary w-full"
        >
          Сохранить пароль
        </button>
      </form>
    </div>
  </div>
</template>
