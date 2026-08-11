from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Referenced from both the field default below and app.main's startup guard, which
# refuses to boot with this value when DEBUG=false - see app.main._validate_production_config.
INSECURE_DEFAULT_JWT_SECRET = "CHANGE_ME_INSECURE_DEV_SECRET"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "my-tutor.ru"
    environment: str = "development"
    debug: bool = True

    # Database. Default SQLite for local dev; set database_url to a postgresql+asyncpg://
    # DSN in production, per project_description.md section 9 (migration to PostgreSQL).
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'storage' / 'db.sqlite3'}"

    # JWT
    jwt_secret_key: str = INSECURE_DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Email
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "no-reply@my-tutor.ru"
    email_enabled: bool = False

    # Telegram
    telegram_bot_token: str | None = None
    telegram_enabled: bool = False
    # Bot's @username (without the @), used to build the t.me deep link shown in
    # Settings for the "Подключить Telegram" flow - see app.services.telegram_service.
    telegram_bot_username: str | None = None

    # VK OAuth
    vk_client_id: str | None = None
    vk_client_secret: str | None = None
    vk_redirect_uri: str | None = None

    # Files
    storage_dir: Path = BASE_DIR / "storage"
    max_upload_size_mb: int = 20

    # Frontend
    frontend_base_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Scheduling defaults (section 2.3)
    default_slot_granularity_minutes: int = 15
    allowed_slot_granularities: list[int] = [10, 15, 20, 30]
    default_min_lead_time_hours: int = 24

    # Timezone in which the tutor cabinet always displays schedule (section 2.3, 6)
    tutor_display_timezone: str = "Europe/Moscow"

    # Bootstrap credentials for the single admin account (section 4), used only by
    # scripts/create_admin.py - never read at request time.
    admin_email: str | None = None
    admin_password: str | None = None

    # Rate limiting (app.core.rate_limit) - on by default, disabled by the test suite
    # (see tests/conftest.py) since a shared in-memory limiter would otherwise trip
    # across unrelated tests hitting /auth/* from the same client IP.
    rate_limit_enabled: bool = True

    # Optional error tracking (app.core.logging) - inert unless a DSN is configured.
    sentry_dsn: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
