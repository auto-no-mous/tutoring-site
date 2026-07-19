<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";
import type { UserRole } from "@/types/user";

const email = ref("");
const password = ref("");
const firstName = ref("");
const lastName = ref("");
const patronymic = ref("");
const role = ref<Exclude<UserRole, "admin">>("student");
const pdConsent = ref(false);
const error = ref<string | null>(null);
const isSubmitting = ref(false);

const auth = useAuthStore();
const router = useRouter();

async function onSubmit(): Promise<void> {
  error.value = null;
  if (!pdConsent.value) {
    error.value = "Необходимо согласие на обработку персональных данных";
    return;
  }
  isSubmitting.value = true;
  try {
    await auth.register({
      email: email.value,
      password: password.value,
      first_name: firstName.value,
      last_name: lastName.value,
      patronymic: patronymic.value || null,
      role: role.value,
      pd_consent: pdConsent.value,
    });
    await router.push("/cabinet");
  } catch {
    error.value = "Не удалось зарегистрироваться. Проверьте данные.";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <div class="mx-auto flex max-w-sm flex-col gap-4 px-4 py-16">
    <h1 class="text-2xl font-semibold">Регистрация</h1>
    <form class="flex flex-col gap-3" @submit.prevent="onSubmit">
      <div class="flex gap-2">
        <input
          v-model="lastName"
          required
          placeholder="Фамилия"
          class="w-1/2 rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        />
        <input
          v-model="firstName"
          required
          placeholder="Имя"
          class="w-1/2 rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        />
      </div>
      <input
        v-model="patronymic"
        placeholder="Отчество (необязательно)"
        class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
      />
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
        minlength="8"
        placeholder="Пароль (минимум 8 символов)"
        class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
      />
      <div class="flex gap-4">
        <label class="flex items-center gap-2">
          <input v-model="role" type="radio" value="student" /> Ученик
        </label>
        <label class="flex items-center gap-2">
          <input v-model="role" type="radio" value="tutor" /> Репетитор
        </label>
      </div>
      <label class="flex items-start gap-2 text-sm">
        <input v-model="pdConsent" type="checkbox" class="mt-1" />
        <span>
          Согласен(на) с
          <RouterLink to="/legal/privacy" class="underline">политикой конфиденциальности</RouterLink>,
          <RouterLink to="/legal/agreement" class="underline">пользовательским соглашением</RouterLink>
          и обработкой персональных данных
        </span>
      </label>
      <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
      <button
        type="submit"
        :disabled="isSubmitting"
        class="rounded-md bg-slate-900 px-3 py-2 text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"
      >
        Зарегистрироваться
      </button>
    </form>
    <RouterLink to="/login" class="text-sm text-slate-500 hover:underline">
      Уже есть аккаунт? Войти
    </RouterLink>
  </div>
</template>
