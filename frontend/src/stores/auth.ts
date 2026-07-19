import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { apiClient, clearTokens, getAccessToken, setTokens } from "@/api/client";
import type { User, UserRole } from "@/types/user";

interface TokenPair {
  access_token: string;
  refresh_token: string;
}

interface RegisterPayload {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  patronymic?: string | null;
  role: Exclude<UserRole, "admin">;
  pd_consent: boolean;
}

export const useAuthStore = defineStore("auth", () => {
  const user = ref<User | null>(null);
  const isInitialized = ref(false);

  const isAuthenticated = computed(() => user.value !== null);

  async function fetchCurrentUser(): Promise<void> {
    if (!getAccessToken()) {
      user.value = null;
      return;
    }
    try {
      const { data } = await apiClient.get<User>("/auth/me");
      user.value = data;
    } catch {
      user.value = null;
      clearTokens();
    }
  }

  async function init(): Promise<void> {
    if (isInitialized.value) return;
    await fetchCurrentUser();
    isInitialized.value = true;
  }

  async function login(email: string, password: string): Promise<void> {
    const { data } = await apiClient.post<TokenPair>("/auth/login", { email, password });
    setTokens(data.access_token, data.refresh_token);
    await fetchCurrentUser();
  }

  async function register(payload: RegisterPayload): Promise<void> {
    const { data } = await apiClient.post<{ user: User; tokens: TokenPair }>(
      "/auth/register",
      payload,
    );
    setTokens(data.tokens.access_token, data.tokens.refresh_token);
    user.value = data.user;
  }

  async function logout(): Promise<void> {
    clearTokens();
    user.value = null;
  }

  return { user, isAuthenticated, isInitialized, init, login, register, logout, fetchCurrentUser };
});
