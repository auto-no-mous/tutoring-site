<script setup lang="ts">
import { ChevronDown } from "lucide-vue-next";
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "reka-ui";
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";
import { useNotificationsStore } from "@/stores/notifications";

const auth = useAuthStore();
const notifications = useNotificationsStore();
const router = useRouter();

const isOpen = ref(false);

const firstName = computed(() => auth.user?.first_name ?? "");
const initial = computed(() => firstName.value.charAt(0).toUpperCase());
// Both roles land on their lesson list - it's the tab either role is most likely to
// want first. "Профиль"/"Настройки" are still one click away via the dropdown below.
const primaryTabKey = "bookings";

const menuItems = computed(() => {
  const items = [{ key: "bookings", label: "Занятия" }, { key: "chat", label: "Сообщения" }];
  if (auth.user?.role === "tutor") items.unshift({ key: "profile", label: "Профиль" });
  items.push({ key: "settings", label: "Настройки" });
  return items;
});

async function onLogout(): Promise<void> {
  await auth.logout();
  await router.push({ name: "catalog" });
}
</script>

<template>
  <div class="relative flex items-center">
    <RouterLink
      :to="`/cabinet?tab=${primaryTabKey}`"
      class="flex items-center gap-2 rounded-md px-1.5 py-1 hover:bg-brand-50 dark:hover:bg-brand-900/30"
    >
      <span class="relative shrink-0">
        <img v-if="auth.tutorPhotoUrl" :src="auth.tutorPhotoUrl" alt="" class="h-8 w-8 rounded-full object-cover" />
        <div
          v-else
          class="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-800 dark:bg-brand-900/60 dark:text-brand-200"
        >
          {{ initial }}
        </div>
        <span
          v-if="notifications.total > 0"
          class="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-medium text-white"
        >
          {{ notifications.total > 9 ? "9+" : notifications.total }}
        </span>
      </span>
      <span>{{ firstName }}</span>
    </RouterLink>

    <!-- Reka UI берёт на себя закрытие по клику вне меню и по Escape, стрелки/Home/End
         и возврат фокуса на кнопку - раньше это был свой слушатель mousedown. -->
    <DropdownMenuRoot v-model:open="isOpen">
      <DropdownMenuTrigger
        class="flex h-7 w-7 items-center justify-center rounded-md text-slate-500 hover:bg-brand-50 hover:text-brand-700 dark:hover:bg-brand-900/30 dark:hover:text-brand-200"
        aria-label="Меню профиля"
      >
        <ChevronDown class="h-4 w-4 transition-transform duration-300" :class="{ 'rotate-180': isOpen }" />
      </DropdownMenuTrigger>
      <DropdownMenuPortal>
        <DropdownMenuContent
          align="end"
          :side-offset="8"
          class="z-50 w-44 origin-[var(--reka-dropdown-menu-content-transform-origin)] rounded-xl border border-slate-200 bg-white py-1 text-sm shadow-lg data-[state=closed]:animate-pop-out data-[state=open]:animate-pop-in dark:border-slate-700 dark:bg-slate-900"
        >
          <DropdownMenuItem
            v-for="item in menuItems"
            :key="item.key"
            as-child
            class="cursor-pointer outline-none data-[highlighted]:bg-brand-50 data-[highlighted]:text-brand-800 dark:data-[highlighted]:bg-brand-900/30 dark:data-[highlighted]:text-brand-200"
          >
            <RouterLink :to="`/cabinet?tab=${item.key}`" class="block px-3 py-2">{{ item.label }}</RouterLink>
          </DropdownMenuItem>
          <DropdownMenuSeparator class="my-1 h-px bg-slate-200 dark:bg-slate-800" />
          <DropdownMenuItem
            class="cursor-pointer px-3 py-2 outline-none data-[highlighted]:bg-brand-50 data-[highlighted]:text-brand-800 dark:data-[highlighted]:bg-brand-900/30 dark:data-[highlighted]:text-brand-200"
            @select="onLogout"
          >
            Выйти
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenuPortal>
    </DropdownMenuRoot>
  </div>
</template>
