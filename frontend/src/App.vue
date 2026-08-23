<script setup lang="ts">
import { Moon, Sun } from "lucide-vue-next";
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
    <header
      class="sticky top-0 z-40 border-b border-slate-200/80 bg-white/80 backdrop-blur-md transition-colors dark:border-slate-800/80 dark:bg-slate-950/80"
    >
      <div class="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-2.5">
        <RouterLink to="/" class="group flex items-center" aria-label="my-tutor.ru — на главную">
          <img
            src="/logo-horizontal.svg"
            alt="my-tutor.ru"
            class="h-9 w-auto transition-transform duration-300 ease-out group-hover:scale-105 dark:hidden sm:h-10"
          />
          <!-- В тёмной теме корпус ноутбука и шрифт в логотипе перекрашены в светлый
               (public/logo-horizontal-dark.svg), иначе они сливаются с фоном. -->
          <img
            src="/logo-horizontal-dark.svg"
            alt=""
            class="hidden h-9 w-auto transition-transform duration-300 ease-out group-hover:scale-105 dark:block sm:h-10"
          />
        </RouterLink>
        <nav class="flex items-center gap-1 text-sm sm:gap-2">
          <template v-if="auth.isAuthenticated">
            <template v-if="auth.user?.role === 'admin'">
              <RouterLink to="/admin" class="nav-link">Админка</RouterLink>
              <button type="button" class="nav-link" @click="onLogout">Выйти</button>
            </template>
            <UserMenu v-else />
          </template>
          <template v-else>
            <RouterLink to="/login" class="nav-link">Войти</RouterLink>
            <RouterLink to="/register" class="btn-primary px-3 py-1.5 text-sm">Регистрация</RouterLink>
          </template>
          <button
            type="button"
            :title="themeStore.theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'"
            class="ml-1 flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-500 transition-all duration-300 hover:rotate-12 hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700 dark:border-slate-700 dark:hover:border-brand-600 dark:hover:bg-brand-900/30 dark:hover:text-brand-200"
            @click="themeStore.toggle"
          >
            <Sun v-if="themeStore.theme === 'dark'" class="h-4 w-4" />
            <Moon v-else class="h-4 w-4" />
          </button>
        </nav>
      </div>
    </header>
    <main class="flex-1">
      <RouterView v-slot="{ Component, route }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" :key="route.path" />
        </Transition>
      </RouterView>
    </main>
    <footer class="mt-10 border-t border-slate-200 bg-white/60 px-4 py-6 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-950/60">
      <div class="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-3">
        <img src="/logo-mark.svg" alt="" class="h-8 w-auto opacity-80 dark:hidden" />
        <img src="/logo-mark-dark.svg" alt="" class="hidden h-8 w-auto opacity-80 dark:block" />
        <RouterLink to="/blog" class="transition-colors hover:text-brand-600">Блог</RouterLink>
        <RouterLink to="/legal/privacy" class="transition-colors hover:text-brand-600">Политика конфиденциальности</RouterLink>
        <RouterLink to="/legal/agreement" class="transition-colors hover:text-brand-600">Пользовательское соглашение</RouterLink>
        <span class="ml-auto text-slate-400">© my-tutor.ru</span>
      </div>
    </footer>
    <ToastContainer />
  </div>
</template>

