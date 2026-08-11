"""Runs the my-tutor.ru Telegram bot via long polling (section 2.7).

Long polling means the bot reaches out to Telegram itself rather than Telegram
pushing updates to a public webhook URL, so this works identically on a laptop
during local development and on a real server - no public domain or HTTPS needed,
only a valid bot token. It does need to keep running continuously, though: locally
that's a second terminal window; in production it's a supervised process (systemd
unit, or the `bot` service in docker-compose.yml).

The bot's only job is the "Подключить Telegram" linking flow (see
app.services.telegram_service): a user clicks a deep link from Settings
(t.me/<bot>?start=<token>), which sends this bot a `/start <token>` command; we
resolve the token to their account and store the resulting chat_id so
notifications (section 2.7) can be delivered there.

Usage:
    poetry run python -m app.scripts.run_telegram_bot
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services import telegram_service


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    chat_id = str(update.effective_chat.id)

    if not context.args:
        await update.message.reply_text(
            "Привет! Чтобы получать уведомления от my-tutor.ru в Telegram, откройте "
            "«Настройки» на сайте и нажмите «Подключить Telegram» - оттуда придёт "
            "персональная ссылка на этого бота."
        )
        return

    token = context.args[0]
    async with AsyncSessionLocal() as db:
        user = await telegram_service.link_chat_by_token(db, token, chat_id)

    if user is None:
        await update.message.reply_text(
            "Ссылка недействительна или устарела. Сгенерируйте новую в «Настройках» на сайте."
        )
        return

    await update.message.reply_text(
        f"Готово, {user.first_name}! Теперь уведомления с my-tutor.ru будут приходить сюда."
    )


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        "Этот бот понимает только ссылку-приглашение из «Настроек» на my-tutor.ru."
    )


def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN не задан в backend/.env - получите токен у @BotFather (см. README.md).")

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL, fallback))

    print("Telegram bot: запущен (long polling). Остановить - Ctrl+C.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
