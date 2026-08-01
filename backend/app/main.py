from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter

settings.storage_dir.mkdir(parents=True, exist_ok=True)
configure_logging()

app = FastAPI(title=settings.app_name, debug=settings.debug)

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
