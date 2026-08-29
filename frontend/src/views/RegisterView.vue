<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import OAuthButtons from "@/components/OAuthButtons.vue";
import { useAuthStore } from "@/stores/auth";
import { apiErrorMessage } from "@/utils/apiError";
import type { UserRole } from "@/types/user";

const email = ref("");
const password = ref("");
const firstName = ref("");
const lastName = ref("");
const patronymic = ref("");
// ?role=tutor lets the home page's "Я репетитор" CTA land on a preselected form.
const role = ref<Exclude<UserRole, "admin">>(useRoute().query.role === "tutor" ? "tutor" : "student");
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
  } catch (err) {
    // Причина почти всегда известна серверу (почта занята, лимит попыток,
    // недоступность) - показываем её, а не общее "проверьте данные".
    error.value = apiErrorMessage(err, "Не удалось зарегистрироваться. Проверьте данные.");
  } finally {
    isSubmitting.value = false;
  }
}
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
    <div class="surface-card animate-pop-in mt-6 flex flex-col gap-4 p-6">
      <h1 class="text-2xl font-semibold">Регистрация</h1>
      <form class="flex flex-col gap-3" @submit.prevent="onSubmit">
        <input
          v-model="lastName"
          required
          placeholder="Фамилия"
          class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        />
        <input
          v-model="firstName"
          required
          placeholder="Имя"
          class="rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        />
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
        <div class="flex rounded-md border border-slate-300 p-1 dark:border-slate-700">
          <button
            type="button"
            class="flex-1 rounded px-3 py-1.5 text-sm transition-colors"
            :class="role === 'student' ? 'bg-brand-500 text-white' : 'text-slate-500'"
            @click="role = 'student'"
          >
            Ученик
          </button>
          <button
            type="button"
            class="flex-1 rounded px-3 py-1.5 text-sm transition-colors"
            :class="role === 'tutor' ? 'bg-brand-500 text-white' : 'text-slate-500'"
            @click="role = 'tutor'"
          >
            Репетитор
          </button>
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
          class="btn-primary w-full"
        >
          Зарегистрироваться
        </button>
      </form>
      <OAuthButtons redirect-to="/cabinet" />
      <RouterLink to="/login" class="text-sm text-slate-500 hover:underline">
        Уже есть аккаунт? Войти
      </RouterLink>
    </div>
  </div>
</template>
