from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import JWTError, TokenType, decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_id

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация")

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Невалидный или истёкший токен")

    if payload.get("type") != TokenType.ACCESS.value:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Невалидный токен")

    user = await get_user_by_id(db, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_user_optional(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User | None:
    """Пользователь, если запрос пришёл с валидным токеном, иначе None.

    Нужен там, где одна ручка обслуживает и гостя, и залогиненного: начало OAuth -
    это вход для первого и привязка провайдера для второго (см. oauth_service).
    Просроченный или битый токен здесь не ошибка, а просто "гость" - иначе человек
    с протухшей сессией не смог бы даже войти заново.
    """
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        return None
    if payload.get("type") != TokenType.ACCESS.value:
        return None
    user = await get_user_by_id(db, payload["sub"])
    return user if user is not None and user.is_active else None


CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]


def require_roles(*roles: str):
    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостаточно прав")
        return user

    return dependency
