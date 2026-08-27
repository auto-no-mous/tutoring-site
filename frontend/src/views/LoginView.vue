<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";
import { apiErrorMessage } from "@/utils/apiError";

const email = ref("");
const password = ref("");
const error = ref<string | null>(null);
const isSubmitting = ref(false);

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

async function onSubmit(): Promise<void> {
  error.value = null;
  isSubmitting.value = true;
  try {
    await auth.login(email.value, password.value);
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/cabinet";
    await router.push(redirect);
  } catch (err) {
    error.value = apiErrorMessage(err, "Неверная почта или пароль");
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
      <h1 class="text-2xl font-semibold">Вход</h1>
      <form class="flex flex-col gap-3" @submit.prevent="onSubmit">
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
          placeholder="Пароль"
          class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        />
        <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
        <button
          type="submit"
          :disabled="isSubmitting"
          class="btn-primary w-full"
        >
          Войти
        </button>
      </form>
      <RouterLink to="/forgot-password" class="text-sm text-slate-500 hover:underline">Забыли пароль?</RouterLink>
      <RouterLink to="/register" class="text-sm text-slate-500 hover:underline">
        Нет аккаунта? Зарегистрироваться
      </RouterLink>
    </div>
  </div>
</template>
