"""Вход и регистрация через внешних провайдеров (VK ID, Яндекс ID).

Поток целиком:
1. POST /auth/oauth/{provider}/start - выдаём state + PKCE, отдаём ссылку авторизации.
   Если запрос пришёл от залогиненного пользователя, это привязка провайдера к его
   аккаунту, а не вход (state.link_user_id).
2. Провайдер возвращает человека на /oauth/{provider}/callback во фронтенде, тот
   пересылает code/state/device_id в POST /auth/oauth/{provider}/callback.
3. Дальше три исхода - см. handle_callback: вход, привязка или "нужна регистрация".
4. POST /auth/oauth/complete - создание аккаунта по одноразовому signup-токену,
   когда пользователь выбрал роль и дал согласие на обработку ПД.
"""

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    JWTError,
    TokenType,
    create_oauth_signup_token,
    decode_token,
)
from app.models.enums import SystemNotificationEvent, UserRole
from app.models.identity import OAuthState, UserIdentity
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.oauth import (
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    OAuthCompleteRequest,
    OAuthSignupPrefill,
)
from app.schemas.user import UserOut
from app.services import (
    auth_service,
    claim_service,
    file_service,
    oauth_providers,
    system_notification_service,
)
from app.services.oauth_providers import OAuthProfile
from app.utils.names import compose_display_name
from app.utils.time import ensure_aware, utcnow

logger = logging.getLogger("app.oauth")

# Столько живёт незавершённая авторизация: с запасом на ввод логина и пароля в
# VK/Яндексе, но не настолько, чтобы накапливать мусор.
STATE_TTL = timedelta(minutes=10)


async def list_providers() -> list[dict]:
    return [
        {"provider": client.name, "label": client.label, "enabled": client.is_configured}
        for client in oauth_providers.all_clients()
    ]


async def start_authorization(
    db: AsyncSession,
    provider: str,
    redirect_to: str | None,
    link_user: User | None,
    claim_token: str | None = None,
) -> str:
    client = oauth_providers.get_client(provider)
    client.ensure_configured()

    # Ссылка-приглашение: авторизует не сессия, а токен, поэтому пользователя для
    # привязки достаём по нему - и только если аккаунт всё ещё никем не забран.
    is_claim = False
    if claim_token:
        link_user = await claim_service.get_claimable_user(db, claim_token)
        is_claim = True

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = oauth_providers.generate_pkce_pair()

    # Заодно подчищаем протухшие: отдельного планировщика ради одной таблицы заводить
    # незачем, а строк тут мало.
    await db.execute(delete(OAuthState).where(OAuthState.expires_at < utcnow()))
    db.add(
        OAuthState(
            state=state,
            provider=provider,
            code_verifier=code_verifier,
            redirect_to=redirect_to,
            link_user_id=link_user.id if link_user is not None else None,
            is_claim=is_claim,
            expires_at=utcnow() + STATE_TTL,
        )
    )
    await db.commit()

    return client.authorize_url(state, code_challenge)


@dataclass(frozen=True)
class _PendingAuth:
    code_verifier: str
    redirect_to: str | None
    link_user_id: uuid.UUID | None
    is_claim: bool


async def _consume_state(db: AsyncSession, provider: str, state: str) -> _PendingAuth:
    """Забирает state и сразу удаляет его: повторно предъявленный код обменять нельзя."""
    result = await db.execute(select(OAuthState).where(OAuthState.state == state))
    stored = result.scalar_one_or_none()
    if stored is None or stored.provider != provider:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ссылка входа недействительна. Попробуйте войти ещё раз.",
        )

    # Снимаем значения до удаления строки, чтобы не зависеть от того, что осталось
    # доступным на отсоединённом объекте.
    pending = _PendingAuth(
        code_verifier=stored.code_verifier,
        redirect_to=stored.redirect_to,
        link_user_id=stored.link_user_id,
        is_claim=stored.is_claim,
    )
    expired = ensure_aware(stored.expires_at) < utcnow()
    await db.delete(stored)
    await db.commit()

    if expired:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Вход занял слишком много времени. Попробуйте ещё раз."
        )
    return pending


async def _get_identity(db: AsyncSession, provider: str, provider_user_id: str) -> UserIdentity | None:
    result = await db.execute(
        select(UserIdentity).where(
            UserIdentity.provider == provider,
            UserIdentity.provider_user_id == provider_user_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


def _email_conflict(label: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        f"На эту почту уже зарегистрирован аккаунт. Войдите по паролю и привяжите "
        f"{label} в настройках, в разделе «Способы входа».",
    )


async def handle_callback(
    db: AsyncSession, provider: str, payload: OAuthCallbackRequest
) -> OAuthCallbackResponse:
    client = oauth_providers.get_client(provider)
    client.ensure_configured()

    stored = await _consume_state(db, provider, payload.state)
    profile = await client.fetch_profile(payload.code, stored.code_verifier, payload.device_id)

    if stored.link_user_id is not None:
        linked_user = await _link_identity(db, stored.link_user_id, profile)
        if not stored.is_claim:
            return OAuthCallbackResponse(status="linked", redirect_to=stored.redirect_to)

        # Забрал аккаунт себе: он перестаёт быть управляемым, и человека надо сразу
        # впустить - в отличие от привязки из настроек, он ещё не залогинен.
        await claim_service.finalize(db, linked_user)
        tokens = await auth_service.issue_token_pair(db, linked_user)
        return OAuthCallbackResponse(
            status="authenticated",
            user=UserOut.model_validate(linked_user),
            tokens=tokens,
            redirect_to=stored.redirect_to,
        )

    identity = await _get_identity(db, provider, profile.provider_user_id)
    if identity is not None:
        user = await db.get(User, identity.user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Аккаунт заблокирован")
        tokens = await auth_service.issue_token_pair(db, user)
        await system_notification_service.notify(
            db, user.id, SystemNotificationEvent.LOGIN_SUCCESS, name=user.first_name
        )
        return OAuthCallbackResponse(
            status="authenticated",
            user=UserOut.model_validate(user),
            tokens=tokens,
            redirect_to=stored.redirect_to,
        )

    # Аккаунта с такой идентичностью нет. Если почта провайдера совпала с уже
    # существующим аккаунтом, молча слить их нельзя: это дало бы вход в чужой
    # аккаунт всякому, кто заведёт у провайдера почту с тем же адресом. Просим
    # войти паролем и привязать провайдера осознанно, из настроек.
    if profile.email is not None and await _get_user_by_email(db, profile.email) is not None:
        raise _email_conflict(client.label)

    signup_token = create_oauth_signup_token(
        provider,
        profile.provider_user_id,
        profile.email,
        first_name=profile.first_name,
        last_name=profile.last_name,
        avatar_url=profile.avatar_url,
    )
    return OAuthCallbackResponse(
        status="signup_required",
        signup_token=signup_token,
        prefill=OAuthSignupPrefill(
            email=profile.email,
            first_name=profile.first_name,
            last_name=profile.last_name,
            avatar_url=profile.avatar_url,
        ),
        redirect_to=stored.redirect_to,
    )


async def _link_identity(db: AsyncSession, user_id: uuid.UUID, profile: OAuthProfile) -> User:
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден")

    existing = await _get_identity(db, profile.provider, profile.provider_user_id)
    if existing is not None:
        if existing.user_id == user.id:
            return user
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Этот аккаунт провайдера уже привязан к другому пользователю сайта",
        )

    db.add(
        UserIdentity(
            user_id=user.id,
            provider=profile.provider,
            provider_user_id=profile.provider_user_id,
            email=profile.email,
        )
    )
    await db.commit()
    await db.refresh(user)
    return user


async def unlink_identity(db: AsyncSession, user: User, provider: str) -> User:
    identity = next((i for i in user.identities if i.provider == provider), None)
    if identity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Этот способ входа не привязан")
    if len(user.auth_providers) < 2:
        # Иначе человек остался бы без единого способа войти: пароля нет, а
        # единственную привязку он только что снял.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Это единственный способ входа в аккаунт. Сначала задайте пароль или "
            "привяжите другого провайдера.",
        )
    await db.delete(identity)
    await db.commit()
    await db.refresh(user)
    return user


async def complete_signup(db: AsyncSession, payload: OAuthCompleteRequest) -> User:
    try:
        decoded = decode_token(payload.signup_token)
    except JWTError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Регистрация заняла слишком много времени, начните заново"
        )
    if decoded.get("type") != TokenType.OAUTH_SIGNUP.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Невалидный токен регистрации")

    provider = decoded.get("provider")
    provider_user_id = decoded.get("sub")
    if not isinstance(provider, str) or not isinstance(provider_user_id, str):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Невалидный токен регистрации")
    client = oauth_providers.get_client(provider)
    email = decoded.get("email")

    if await _get_identity(db, provider, provider_user_id) is not None:
        # Например, второй колбэк по той же ссылке или два открытых окна: аккаунт уже
        # создан, повторно создавать его нельзя.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Аккаунт уже создан, попробуйте войти ещё раз"
        )
    if email is not None and await _get_user_by_email(db, email) is not None:
        raise _email_conflict(client.label)

    # ФИО берём из токена, то есть у провайдера. Поля запроса - запасной путь на
    # случай, когда провайдер имени не отдал: тогда форма спрашивает его сама.
    first_name = decoded.get("first_name") or payload.first_name
    last_name = decoded.get("last_name") or payload.last_name
    if not first_name or not last_name:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"{client.label} не передал имя и фамилию — укажите их вручную",
        )

    user = User(
        role=payload.role,
        email=email,
        first_name=first_name,
        last_name=last_name,
        # Отчество провайдеры не отдают; репетитор при желании дописывает его в
        # настройках.
        display_name=compose_display_name(first_name, last_name, None),
        # Класс осмыслен только для ученика - у репетитора значение игнорируем, а не
        # доверяем присланному.
        grade=payload.grade if payload.role == UserRole.STUDENT else None,
        # Почту сюда кладёт сам провайдер, у которого она уже подтверждена, так что
        # письмо с подтверждением не нужно.
        email_verified=email is not None,
        pd_consent_given=True,
        pd_consent_at=utcnow(),
    )
    # Аватар провайдера переносим к себе один раз и ставим его аккаунту. Репетитору
    # он заодно попадает в анкету: на старте лучше показать в каталоге хоть какое-то
    # фото, чем пустой квадрат, а заменить его можно в профиле.
    user.photo_url = await _import_avatar(decoded.get("avatar_url"))

    db.add(user)
    await db.flush()

    db.add(
        UserIdentity(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
        )
    )
    if payload.role == UserRole.TUTOR:
        db.add(TutorProfile(user_id=user.id, photo_url=user.photo_url))

    await db.commit()
    await db.refresh(user)

    # Приветствие - побочный эффект уже состоявшейся регистрации и не должно её
    # ронять (та же логика, что в auth_service.register_user).
    await system_notification_service.notify(
        db,
        user.id,
        SystemNotificationEvent.WELCOME,
        name=user.first_name,
        catalog_url=settings.frontend_base_url,
    )
    return user


async def _import_avatar(avatar_url: str | None) -> str | None:
    """Переносит аватар провайдера к нам в storage и возвращает путь для
    User.photo_url (репетитору он же уходит в TutorProfile.photo_url).

    Никогда не бросает: аватар - приятная мелочь, из-за которой регистрация не
    должна падать. Ссылку сюда пускает только адаптер провайдера, проверивший хост
    (см. oauth_providers.OAuthClient._trusted_avatar_url).
    """
    if not avatar_url:
        return None
    try:
        downloaded = await oauth_providers.download_avatar(avatar_url)
        if downloaded is None:
            return None
        content, content_type = downloaded
        return file_service.save_bytes(
            content, content_type, "user-photos", file_service.ALLOWED_IMAGE_TYPES
        )
    except Exception:
        logger.warning("OAUTH: не удалось сохранить аватар из %s", avatar_url, exc_info=True)
        return None
