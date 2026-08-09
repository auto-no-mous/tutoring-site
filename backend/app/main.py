from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import INSECURE_DEFAULT_JWT_SECRET, settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.db.session import AsyncSessionLocal
from app.services.system_notification_service import ensure_default_templates


def _validate_production_config() -> None:
    """Refuses to boot with the insecure placeholder JWT secret outside local dev
    (DEBUG=false is the signal a deployer used, per README's "Docker / продакшен")
    - failing fast here beats silently issuing tokens anyone could forge by reading
    this file on GitHub."""
    if not settings.debug and settings.jwt_secret_key == INSECURE_DEFAULT_JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET_KEY is still the insecure default while DEBUG=false - set a "
            "real secret in backend/.env before running in production (e.g. "
            "`openssl rand -hex 32`)."
        )


_validate_production_config()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Seeds any missing notification_templates rows (new event types added in a
    # later release, or a brand-new database) so the admin "Уведомления" tab and
    # every notify() call site always have a template to read, without a data
    # migration per event added.
    async with AsyncSessionLocal() as db:
        await ensure_default_templates(db)
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.state.limiter = limiter
# slowapi's handler is typed against RateLimitExceeded specifically, which mypy sees
# as narrower than FastAPI's declared `Exception` handler signature - a known stub
# mismatch between the two packages, not an actual type error.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/files", StaticFiles(directory=settings.storage_dir), name="files")

app.include_router(api_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
