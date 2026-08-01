import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { apiClient, clearTokens, getAccessToken, setTokens } from "@/api/client";
import { getMyProfile } from "@/api/tutors";
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
  // Denormalized from the tutor's own TutorProfile (see ProfileTab.vue), purely for
  // the header avatar (components/UserMenu.vue) - students have no photo field.
  const tutorPhotoUrl = ref<string | null>(null);

  const isAuthenticated = computed(() => user.value !== null);

  function setTutorPhotoUrl(url: string | null): void {
    tutorPhotoUrl.value = url;
  }

  async function fetchCurrentUser(): Promise<void> {
    if (!getAccessToken()) {
      user.value = null;
      tutorPhotoUrl.value = null;
      return;
    }
    try {
      const { data } = await apiClient.get<User>("/auth/me");
      user.value = data;
    } catch {
      user.value = null;
      tutorPhotoUrl.value = null;
      clearTokens();
      return;
    }
    if (user.value.role === "tutor") {
      // Best-effort only - a hiccup here shouldn't take down the whole session.
      try {
        tutorPhotoUrl.value = (await getMyProfile()).photo_url;
      } catch {
        tutorPhotoUrl.value = null;
      }
    } else {
      tutorPhotoUrl.value = null;
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
    tutorPhotoUrl.value = null;
  }

  return {
    user,
    isAuthenticated,
    isInitialized,
    tutorPhotoUrl,
    setTutorPhotoUrl,
    init,
    login,
    register,
    logout,
    fetchCurrentUser,
  };
});
