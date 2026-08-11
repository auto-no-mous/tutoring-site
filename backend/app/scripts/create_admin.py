"""Creates or updates the single admin account (project_description.md section 4).

Usage:
    poetry run python -m app.scripts.create_admin --email admin@my-tutor.ru --password ...

Falls back to ADMIN_EMAIL / ADMIN_PASSWORD from the environment/.env when the flags
are omitted.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.utils.time import utcnow


async def create_or_update_admin(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.role == UserRole.ADMIN.value))
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.email = email
            existing.password_hash = hash_password(password)
            existing.email_verified = True
            existing.is_active = True
            await db.commit()
            print(f"Updated existing admin account: {email}")
            return

        admin = User(
            role=UserRole.ADMIN.value,
            email=email,
            password_hash=hash_password(password),
            first_name="Администратор",
            last_name="",
            display_name="Администратор",
            email_verified=True,
            is_active=True,
            pd_consent_given=True,
            pd_consent_at=utcnow(),
        )
        db.add(admin)
        await db.commit()
        print(f"Created admin account: {email}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=settings.admin_email)
    parser.add_argument("--password", default=settings.admin_password)
    args = parser.parse_args()

    if not args.email or not args.password:
        raise SystemExit(
            "Provide --email/--password, or set ADMIN_EMAIL/ADMIN_PASSWORD in the environment/.env"
        )

    asyncio.run(create_or_update_admin(args.email, args.password))


if __name__ == "__main__":
    main()
