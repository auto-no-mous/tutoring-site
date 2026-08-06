<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();

const isOpen = ref(false);
const containerRef = ref<HTMLElement | null>(null);

const firstName = computed(() => auth.user?.first_name ?? "");
const initial = computed(() => firstName.value.charAt(0).toUpperCase());
// Tutors land on their "Профиль" tab; students have no such tab, so clicking the
// avatar/name takes them to their lesson list instead ("Настройки", where a student's
// own data actually lives, is still one click away via the dropdown below).
const primaryTabKey = computed(() => (auth.user?.role === "tutor" ? "profile" : "bookings"));

const menuItems = computed(() => {
  const items = [{ key: "bookings", label: "Занятия" }];
  if (auth.user?.role === "tutor") items.unshift({ key: "profile", label: "Профиль" });
  items.push({ key: "settings", label: "Настройки" });
  return items;
});

function toggleMenu(): void {
  isOpen.value = !isOpen.value;
}

function closeMenu(): void {
  isOpen.value = false;
}

function onDocumentClick(event: MouseEvent): void {
  if (containerRef.value && !containerRef.value.contains(event.target as Node)) {
    closeMenu();
  }
}

async function onLogout(): Promise<void> {
  closeMenu();
  await auth.logout();
  await router.push({ name: "catalog" });
}

onMounted(() => {
  document.addEventListener("mousedown", onDocumentClick);
});
onBeforeUnmount(() => {
  document.removeEventListener("mousedown", onDocumentClick);
});
</script>

<template>
  <div ref="containerRef" class="relative flex items-center">
    <RouterLink
      :to="`/cabinet?tab=${primaryTabKey}`"
      class="flex items-center gap-2 rounded-md px-1.5 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
      @click="closeMenu"
    >
      <img v-if="auth.tutorPhotoUrl" :src="auth.tutorPhotoUrl" alt="" class="h-8 w-8 rounded-full object-cover" />
      <div
        v-else
        class="flex h-8 w-8 items-center justify-center rounded-full bg-slate-200 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300"
      >
        {{ initial }}
      </div>
      <span>{{ firstName }}</span>
    </RouterLink>
    <button
      type="button"
      title="Меню"
      class="rounded-md p-1 hover:bg-slate-100 dark:hover:bg-slate-800"
      @click="toggleMenu"
    >
      <span class="inline-block text-xs transition-transform" :class="{ 'rotate-180': isOpen }">▾</span>
    </button>

    <div
      v-if="isOpen"
      class="absolute right-0 top-full z-10 mt-2 w-40 rounded-md border border-slate-200 bg-white py-1 text-sm shadow-lg dark:border-slate-700 dark:bg-slate-900"
    >
      <RouterLink
        v-for="item in menuItems"
        :key="item.key"
        :to="`/cabinet?tab=${item.key}`"
        class="block px-3 py-2 hover:bg-slate-100 dark:hover:bg-slate-800"
        @click="closeMenu"
      >
        {{ item.label }}
      </RouterLink>
      <button type="button" class="block w-full px-3 py-2 text-left hover:bg-slate-100 dark:hover:bg-slate-800" @click="onLogout">
        Выйти
      </button>
    </div>
  </div>
</template>
