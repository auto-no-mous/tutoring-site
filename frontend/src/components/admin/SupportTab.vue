<script setup lang="ts">
import { onMounted, ref } from "vue";

import { addSupportStaff, listSupportStaff, removeSupportStaff, type SupportStaffMember } from "@/api/admin";
import ChatPanel from "@/components/ChatPanel.vue";
import { apiErrorMessage } from "@/utils/apiError";

// Обращения пользователей в поддержку и кто на них отвечает. Админы отвечают всегда;
// здесь можно назначить ещё людей - например, свой аккаунт репетитора, чтобы
// отвечать из обычного кабинета и не заходить ради этого в админку.
const staff = ref<SupportStaffMember[]>([]);
const email = ref("");
const error = ref("");
const isSaving = ref(false);

const ROLE_LABELS: Record<string, string> = { tutor: "репетитор", student: "ученик", admin: "администратор" };

async function load(): Promise<void> {
  staff.value = await listSupportStaff();
}

async function add(): Promise<void> {
  if (!email.value.trim()) return;
  error.value = "";
  isSaving.value = true;
  try {
    await addSupportStaff(email.value.trim());
    email.value = "";
    await load();
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось назначить");
  } finally {
    isSaving.value = false;
  }
}

async function remove(member: SupportStaffMember): Promise<void> {
  if (!window.confirm(`Снять ${member.display_name} с поддержки?`)) return;
  await removeSupportStaff(member.id);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="flex flex-col gap-6">
    <section class="max-w-2xl">
      <h2 class="text-lg font-medium">Кто отвечает в поддержке</h2>
      <p class="mt-1 text-sm text-slate-500">
        Администраторы видят обращения всегда. Назначенные здесь видят их в чате своего кабинета и получают
        уведомления о новых обращениях — в Telegram, ВКонтакте или на почту, как у них настроено.
      </p>
      <ul class="mt-3 flex flex-col gap-1.5" data-support-staff>
        <li v-if="staff.length === 0" class="text-sm text-slate-400">Пока никого, кроме администраторов.</li>
        <li
          v-for="member in staff"
          :key="member.id"
          class="flex items-center justify-between gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800"
        >
          <span>
            {{ member.display_name }}
            <span class="text-slate-400">· {{ ROLE_LABELS[member.role] ?? member.role }} · {{ member.email ?? "без почты" }}</span>
          </span>
          <button type="button" class="text-xs text-red-600 underline dark:text-red-400" @click="remove(member)">
            Снять
          </button>
        </li>
      </ul>
      <form class="mt-3 flex flex-wrap gap-2" @submit.prevent="add">
        <input
          v-model="email"
          type="email"
          placeholder="Почта аккаунта на сайте"
          aria-label="Почта аккаунта для назначения в поддержку"
          class="min-w-64 flex-1 rounded-md border border-slate-300 bg-transparent px-3 py-1.5 text-sm dark:border-slate-700"
        />
        <button
          type="submit"
          :disabled="isSaving || !email.trim()"
          class="rounded-md bg-brand-500 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Назначить в поддержку
        </button>
      </form>
      <p v-if="error" class="mt-1 text-sm text-red-600 dark:text-red-400">{{ error }}</p>
    </section>

    <section>
      <h2 class="text-lg font-medium">Обращения</h2>
      <ChatPanel class="mt-3" support-only />
    </section>
  </div>
</template>
