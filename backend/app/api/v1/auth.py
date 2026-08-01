from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser, DbSession
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
    VKAuthRequest,
)
from app.schemas.user import UserOut, UserSettingsUpdate
from app.services import auth_service, telegram_service, vk_service

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


@router.post("/vk", response_model=RegisterResponse)
@limiter.limit("10/minute")
async def vk_login(request: Request, payload: VKAuthRequest, db: DbSession) -> RegisterResponse:
    result = await vk_service.exchange_code(payload.code, payload.redirect_uri)
    user = await auth_service.login_or_register_vk_user(db, result.vk_id, payload)
    tokens = await auth_service.issue_token_pair(db, user)
    return RegisterResponse(user=UserOut.model_validate(user), tokens=tokens)
