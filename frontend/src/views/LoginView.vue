<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

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
  } catch {
    error.value = "Неверная почта или пароль";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <div class="mx-auto flex max-w-sm flex-col gap-4 px-4 py-16">
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
        class="rounded-md bg-slate-900 px-3 py-2 text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"
      >
        Войти
      </button>
    </form>
    <RouterLink to="/register" class="text-sm text-slate-500 hover:underline">
      Нет аккаунта? Зарегистрироваться
    </RouterLink>
  </div>
</template>
