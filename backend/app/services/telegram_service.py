import logging
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot
from telegram.error import TelegramError

from app.core.config import settings
from app.models.user import User
from app.utils.time import ensure_aware, utcnow

logger = logging.getLogger("app.telegram")

# How long a "Подключить Telegram" deep link stays valid before the user has to
# generate a new one from Settings.
LINK_TOKEN_TTL = timedelta(minutes=15)

_bot: Bot | None = None


def _get_bot() -> Bot | None:
    global _bot
    if not settings.telegram_enabled or not settings.telegram_bot_token:
        return None
    if _bot is None:
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


async def send_telegram_message(chat_id: str, text: str) -> None:
    """Sends a Telegram message, or logs it when the bot isn't configured (local dev)."""
    bot = _get_bot()
    if bot is None:
        logger.info("TELEGRAM (not sent, disabled) to=%s\n%s", chat_id, text)
        return

    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except TelegramError as exc:
        logger.warning("Telegram send failed to=%s: %s", chat_id, exc)
        raise


async def create_link_token(db: AsyncSession, user: User) -> str:
    """Issues a fresh deep-link token for the "Подключить Telegram" flow (section
    2.7), invalidating any token issued earlier - only one pending link attempt
    matters at a time. Consumed by the bot's /start handler, see
    app.scripts.run_telegram_bot."""
    token = secrets.token_urlsafe(24)
    user.telegram_link_token = token
    user.telegram_link_token_expires_at = utcnow() + LINK_TOKEN_TTL
    await db.commit()
    return token


def build_link_url(token: str) -> str | None:
    """None when the bot's username isn't configured yet (local dev before the
    tutor/admin has set up a real bot) - the frontend falls back to explaining the
    feature isn't available yet rather than showing a dead link."""
    if not settings.telegram_bot_username:
        return None
    return f"https://t.me/{settings.telegram_bot_username}?start={token}"


async def link_chat_by_token(db: AsyncSession, token: str, chat_id: str) -> User | None:
    """Consumes a link token from the bot's /start handler. Returns the newly-linked
    user, or None if the token is unknown/expired (the bot replies accordingly)."""
    result = await db.execute(select(User).where(User.telegram_link_token == token))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if user.telegram_link_token_expires_at is None or ensure_aware(user.telegram_link_token_expires_at) < utcnow():
        return None

    user.telegram_chat_id = chat_id
    user.telegram_link_token = None
    user.telegram_link_token_expires_at = None
    await db.commit()
    await db.refresh(user)
    return user
