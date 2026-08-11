<script setup lang="ts">
import { onBeforeUnmount, watch } from "vue";
import { useRouter } from "vue-router";

import ToastContainer from "@/components/ToastContainer.vue";
import UserMenu from "@/components/UserMenu.vue";
import { useAuthStore } from "@/stores/auth";
import { useNotificationsStore } from "@/stores/notifications";
import { useThemeStore } from "@/stores/theme";

const auth = useAuthStore();
const themeStore = useThemeStore();
const notifications = useNotificationsStore();
const router = useRouter();

async function onLogout(): Promise<void> {
  await auth.logout();
  await router.push({ name: "catalog" });
}

// Only tutors/students see UserMenu's badge (admin gets its own nav, see below) -
// poll only while logged in as one of those roles.
watch(
  () => (auth.isAuthenticated && auth.user?.role !== "admin" ? auth.user?.id : null),
  (id) => {
    if (id) notifications.startPolling();
    else notifications.stopPolling();
  },
  { immediate: true },
);

onBeforeUnmount(() => notifications.stopPolling());
</script>

<template>
  <div class="flex min-h-full flex-col">
    <header class="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-800">
      <RouterLink to="/" class="text-lg font-semibold">my-tutor.ru</RouterLink>
      <nav class="flex items-center gap-4 text-sm">
        <template v-if="auth.isAuthenticated">
          <template v-if="auth.user?.role === 'admin'">
            <RouterLink to="/admin">Админка</RouterLink>
            <button type="button" @click="onLogout">Выйти</button>
          </template>
          <UserMenu v-else />
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
    <ToastContainer />
  </div>
</template>
