import { apiClient } from "@/api/client";
import type { User } from "@/types/user";

export type OAuthProviderName = "vk" | "yandex";

export interface OAuthProvider {
  provider: OAuthProviderName;
  label: string;
  // false, когда на сервере не заданы креды приложения - такую кнопку не показываем.
  enabled: boolean;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

export interface OAuthSignupPrefill {
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  // Аватар у провайдера: показываем на шаге регистрации, а репетитору сервер сам
  // перенесёт его в анкету.
  avatar_url: string | null;
}

export interface OAuthCallbackResult {
  // authenticated - вошли; signup_required - нужен второй шаг (роль + согласие);
  // linked - привязали провайдера к текущему аккаунту.
  status: "authenticated" | "signup_required" | "linked";
  user: User | null;
  tokens: TokenPair | null;
  signup_token: string | null;
  prefill: OAuthSignupPrefill | null;
  redirect_to: string | null;
}

export interface OAuthCompletePayload {
  signup_token: string;
  role: "tutor" | "student";
  // Класс — только для ученика; у репетитора сервер поле игнорирует.
  grade?: number | null;
  // Имя и фамилия отправляются, только если провайдер их не отдал: обычно сервер
  // берёт их из подписанного signup-токена.
  first_name?: string | null;
  last_name?: string | null;
  pd_consent: boolean;
}

export async function listOAuthProviders() {
  const { data } = await apiClient.get<OAuthProvider[]>("/auth/oauth/providers");
  return data;
}

/** Возвращает ссылку авторизации у провайдера. Если пользователь залогинен, сервер
 * трактует поток как привязку провайдера к его аккаунту, а не как вход. */
export async function startOAuth(
  provider: OAuthProviderName,
  redirectTo?: string | null,
  claimToken?: string | null,
) {
  const { data } = await apiClient.post<{ auth_url: string }>(`/auth/oauth/${provider}/start`, {
    redirect_to: redirectTo ?? null,
    // Токен из ссылки-приглашения: провайдер привязывается к заведённому
    // репетитором профилю, а не создаёт новый аккаунт.
    claim_token: claimToken ?? null,
  });
  return data.auth_url;
}

export async function finishOAuth(
  provider: OAuthProviderName,
  payload: { code: string; state: string; device_id?: string | null },
) {
  const { data } = await apiClient.post<OAuthCallbackResult>(
    `/auth/oauth/${provider}/callback`,
    payload,
  );
  return data;
}

export async function completeOAuthSignup(payload: OAuthCompletePayload) {
  const { data } = await apiClient.post<{ user: User; tokens: TokenPair }>(
    "/auth/oauth/complete",
    payload,
  );
  return data;
}

export async function unlinkOAuthProvider(provider: OAuthProviderName) {
  const { data } = await apiClient.delete<User>(`/auth/me/identities/${provider}`);
  return data;
}

export interface ClaimPreview {
  display_name: string;
  grade: number | null;
  tutor_display_name: string;
}

export async function getClaimPreview(token: string) {
  const { data } = await apiClient.get<ClaimPreview>(`/auth/claim/${token}`);
  return data;
}

export async function claimWithPassword(payload: {
  token: string;
  email: string;
  password: string;
  pd_consent: boolean;
}) {
  const { data } = await apiClient.post<{ user: User; tokens: TokenPair }>(
    "/auth/claim/password",
    payload,
  );
  return data;
}
