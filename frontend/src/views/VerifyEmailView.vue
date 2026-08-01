<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { verifyEmail } from "@/api/users";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const auth = useAuthStore();

const status = ref<"loading" | "success" | "error">("loading");
const errorMessage = ref("");

onMounted(async () => {
  const token = typeof route.query.token === "string" ? route.query.token : "";
  if (!token) {
    status.value = "error";
    errorMessage.value = "В ссылке нет кода подтверждения.";
    return;
  }
  try {
    const user = await verifyEmail(token);
    if (auth.user && auth.user.id === user.id) {
      auth.user = user;
    }
    status.value = "success";
  } catch {
    status.value = "error";
    errorMessage.value = "Ссылка недействительна или уже была использована.";
  }
});
</script>

<template>
  <div class="mx-auto flex max-w-sm flex-col gap-4 px-4 py-16 text-center">
    <p v-if="status === 'loading'" class="text-sm text-slate-400">Подтверждаем почту…</p>

    <template v-else-if="status === 'success'">
      <h1 class="text-xl font-semibold text-green-600 dark:text-green-400">Почта подтверждена</h1>
      <RouterLink
        :to="auth.isAuthenticated ? '/cabinet' : '/login'"
        class="rounded-md bg-slate-900 px-4 py-2 text-sm text-white dark:bg-white dark:text-slate-900"
      >
        {{ auth.isAuthenticated ? "В личный кабинет" : "Войти" }}
      </RouterLink>
    </template>

    <template v-else>
      <h1 class="text-xl font-semibold text-red-600 dark:text-red-400">Не удалось подтвердить почту</h1>
      <p class="text-sm text-slate-500">{{ errorMessage }}</p>
      <RouterLink to="/" class="text-sm text-slate-500 underline">На главную</RouterLink>
    </template>
  </div>
</template>
