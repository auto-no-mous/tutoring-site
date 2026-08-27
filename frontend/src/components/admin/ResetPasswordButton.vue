<script setup lang="ts">
import { ref } from "vue";

import { resetUserPassword } from "@/api/admin";
import { useToastStore } from "@/stores/toast";
import { apiErrorMessage } from "@/utils/apiError";

// userId, а не id анкеты: ручка одна на любую роль, см. api/admin.ts.
const props = defineProps<{ userId: string; displayName: string }>();

const toast = useToastStore();
const isOpen = ref(false);
const newPassword = ref("");
const isSaving = ref(false);
const error = ref("");

function open(): void {
  isOpen.value = true;
  newPassword.value = "";
  error.value = "";
}

function close(): void {
  isOpen.value = false;
  newPassword.value = "";
}

async function submit(): Promise<void> {
  isSaving.value = true;
  error.value = "";
  try {
    await resetUserPassword(props.userId, newPassword.value);
    close();
    toast.show("Пароль изменён, все сессии пользователя завершены");
  } catch (err) {
    error.value = apiErrorMessage(err, "Не удалось изменить пароль");
  } finally {
    isSaving.value = false;
  }
}
</script>

<template>
  <button
    v-if="!isOpen"
    type="button"
    class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700"
    @click="open"
  >
    Сбросить пароль
  </button>

  <form v-else class="flex flex-col gap-1" @submit.prevent="submit">
    <div class="flex items-center gap-2">
      <input
        v-model="newPassword"
        type="text"
        required
        minlength="8"
        :aria-label="`Новый пароль для ${displayName}`"
        placeholder="Новый пароль (от 8 символов)"
        class="w-56 rounded-md border border-slate-300 bg-transparent px-2 py-1 text-xs dark:border-slate-700"
      />
      <button
        type="submit"
        :disabled="isSaving"
        class="rounded-md bg-brand-500 px-2 py-1 text-xs text-white disabled:opacity-50"
      >
        Задать
      </button>
      <button type="button" class="text-xs text-slate-500 underline" @click="close">Отмена</button>
    </div>
    <!-- Пароль намеренно показан открытым: админ должен его прочитать и передать
         человеку, а прятать за точками то, что всё равно диктуется вслух, смысла нет. -->
    <p class="text-xs text-slate-500">Передайте пароль пользователю — на почту он не отправляется.</p>
    <p v-if="error" class="text-xs text-red-600 dark:text-red-400">{{ error }}</p>
  </form>
</template>
