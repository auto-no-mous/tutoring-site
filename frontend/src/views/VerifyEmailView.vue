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
    <div class="surface-card animate-pop-in mt-6 flex flex-col gap-4 p-6 text-center">
      <p v-if="status === 'loading'" class="text-sm text-slate-400">Подтверждаем почту…</p>

      <template v-else-if="status === 'success'">
        <h1 class="text-xl font-semibold text-green-600 dark:text-green-400">Почта подтверждена</h1>
        <RouterLink
          :to="auth.isAuthenticated ? '/cabinet' : '/login'"
          class="btn-primary"
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
  </div>
</template>
