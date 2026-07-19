"""Sends "upcoming lesson" reminder notifications (section 2.7).

Meant to be invoked periodically by an external scheduler (cron / Windows Task
Scheduler / a scheduled container in docker-compose) - this codebase has no built-in
scheduler. Safe to run frequently (e.g. hourly): each booking is only reminded once.

Usage:
    poetry run python -m app.scripts.send_reminders
"""

import asyncio

from app.db.session import AsyncSessionLocal
from app.services.notification_service import send_upcoming_reminders


async def main() -> None:
    async with AsyncSessionLocal() as db:
        count = await send_upcoming_reminders(db)
        print(f"Sent {count} upcoming-lesson reminder(s)")


if __name__ == "__main__":
    asyncio.run(main())
