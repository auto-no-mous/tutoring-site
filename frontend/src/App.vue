<script setup lang="ts">
import { useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";

const auth = useAuthStore();
const themeStore = useThemeStore();

async function onLogout(): Promise<void> {
  await auth.logout();
}
</script>

<template>
  <div class="flex min-h-full flex-col">
    <header class="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-800">
      <RouterLink to="/" class="text-lg font-semibold">it-tutor.pro</RouterLink>
      <nav class="flex items-center gap-4 text-sm">
        <RouterLink to="/">Каталог</RouterLink>
        <template v-if="auth.isAuthenticated">
          <RouterLink v-if="auth.user?.role === 'admin'" to="/admin">Админка</RouterLink>
          <RouterLink v-else to="/cabinet">Кабинет</RouterLink>
          <button type="button" @click="onLogout">Выйти</button>
        </template>
        <template v-else>
          <RouterLink to="/login">Войти</RouterLink>
          <RouterLink to="/register">Регистрация</RouterLink>
        </template>
        <button
          type="button"
          class="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-700"
          @click="themeStore.toggle"
        >
          {{ themeStore.theme === "dark" ? "☀️" : "🌙" }}
        </button>
      </nav>
    </header>
    <main class="flex-1">
      <RouterView />
    </main>
    <footer class="border-t border-slate-200 px-4 py-4 text-xs text-slate-500 dark:border-slate-800">
      <div class="flex flex-wrap gap-4">
        <RouterLink to="/legal/privacy">Политика конфиденциальности</RouterLink>
        <RouterLink to="/legal/agreement">Пользовательское соглашение</RouterLink>
      </div>
    </footer>
  </div>
</template>
