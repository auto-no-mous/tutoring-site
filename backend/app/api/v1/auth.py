from fastapi import APIRouter, File, Request, UploadFile, status

from app.api.deps import CurrentUser, CurrentUserOptional, DbSession
from app.core.rate_limit import limiter
from app.schemas.auth import (
    EmailVerifyRequest,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TelegramLinkTokenOut,
    TokenPair,
)
from app.schemas.oauth import (
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    OAuthCompleteRequest,
    OAuthProviderOut,
    OAuthStartRequest,
    OAuthStartResponse,
)
from app.schemas.user import UserOut, UserSettingsUpdate
from app.services import auth_service, file_service, oauth_service, telegram_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def register(request: Request, payload: RegisterRequest, db: DbSession) -> RegisterResponse:
    user = await auth_service.register_user(db, payload)
    tokens = await auth_service.issue_token_pair(db, user)
    return RegisterResponse(user=UserOut.model_validate(user), tokens=tokens)


@router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest, db: DbSession) -> TokenPair:
    user = await auth_service.authenticate_user(db, payload)
    return await auth_service.issue_token_pair(db, user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    return await auth_service.refresh_token_pair(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, db: DbSession) -> None:
    await auth_service.revoke_refresh_token(db, payload.refresh_token)


@router.post("/verify-email", response_model=UserOut)
async def verify_email(payload: EmailVerifyRequest, db: DbSession) -> UserOut:
    user = await auth_service.verify_email(db, payload.token)
    return UserOut.model_validate(user)


@router.post("/verify-email/resend", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/hour")
async def resend_verification_email(request: Request, current_user: CurrentUser) -> None:
    await auth_service.resend_verification_email(current_user)


@router.post("/me/telegram-link-token", response_model=TelegramLinkTokenOut)
async def create_telegram_link_token(current_user: CurrentUser, db: DbSession) -> TelegramLinkTokenOut:
    token = await telegram_service.create_link_token(db, current_user)
    return TelegramLinkTokenOut(token=token, deep_link=telegram_service.build_link_url(token))


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/hour")
async def request_password_reset(request: Request, payload: PasswordResetRequest, db: DbSession) -> None:
    await auth_service.request_password_reset(db, payload.email)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(payload: PasswordResetConfirm, db: DbSession) -> None:
    await auth_service.confirm_password_reset(db, payload)


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)


@router.patch("/me", response_model=UserOut)
async def update_me(payload: UserSettingsUpdate, current_user: CurrentUser, db: DbSession) -> UserOut:
    user = await auth_service.update_user_settings(db, current_user, payload)
    return UserOut.model_validate(user)


@router.post("/me/photo", response_model=UserOut)
async def upload_my_photo(
    current_user: CurrentUser, db: DbSession, file: UploadFile = File(...)
) -> UserOut:
    """Аватар аккаунта. У репетитора фото анкеты меняется отдельно, в профиле
    (POST /tutors/me/photo) - это разные картинки, см. User.photo_url."""
    photo_url = await file_service.save_upload(file, "user-photos", file_service.ALLOWED_IMAGE_TYPES)
    user = await auth_service.set_photo(db, current_user, photo_url)
    return UserOut.model_validate(user)


@router.delete("/me/photo", response_model=UserOut)
async def delete_my_photo(current_user: CurrentUser, db: DbSession) -> UserOut:
    user = await auth_service.set_photo(db, current_user, None)
    return UserOut.model_validate(user)


@router.get("/oauth/providers", response_model=list[OAuthProviderOut])
async def list_oauth_providers() -> list[OAuthProviderOut]:
    """Какие внешние провайдеры входа настроены на сервере - фронтенд показывает
    только их кнопки."""
    return [OAuthProviderOut(**item) for item in await oauth_service.list_providers()]


@router.post("/oauth/{provider}/start", response_model=OAuthStartResponse)
@limiter.limit("20/minute")
async def oauth_start(
    request: Request,
    provider: str,
    payload: OAuthStartRequest,
    db: DbSession,
    current_user: CurrentUserOptional,
) -> OAuthStartResponse:
    """Начало авторизации у провайдера. С токеном в заголовке это привязка провайдера
    к текущему аккаунту, без токена - вход или регистрация."""
    auth_url = await oauth_service.start_authorization(
        db, provider, payload.redirect_to, current_user
    )
    return OAuthStartResponse(auth_url=auth_url)


@router.post("/oauth/{provider}/callback", response_model=OAuthCallbackResponse)
@limiter.limit("20/minute")
async def oauth_callback(
    request: Request, provider: str, payload: OAuthCallbackRequest, db: DbSession
) -> OAuthCallbackResponse:
    return await oauth_service.handle_callback(db, provider, payload)


@router.post("/oauth/complete", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def oauth_complete(
    request: Request, payload: OAuthCompleteRequest, db: DbSession
) -> RegisterResponse:
    """Второй шаг первого входа через провайдера: роль и согласие на обработку ПД."""
    user = await oauth_service.complete_signup(db, payload)
    tokens = await auth_service.issue_token_pair(db, user)
    return RegisterResponse(user=UserOut.model_validate(user), tokens=tokens)


@router.delete("/me/identities/{provider}", response_model=UserOut)
async def unlink_identity(provider: str, current_user: CurrentUser, db: DbSession) -> UserOut:
    user = await oauth_service.unlink_identity(db, current_user, provider)
    return UserOut.model_validate(user)
