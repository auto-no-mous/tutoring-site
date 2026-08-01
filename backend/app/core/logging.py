import json
import logging
from datetime import datetime, timezone

from app.core.config import settings

_RESERVED_LOG_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Renders each log line as one JSON object, so a log aggregator (e.g. the
    docker-compose logging driver shipping to a centralized store) can index by
    level/logger/etc. instead of grepping free text."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Anything passed via logging's `extra={...}` kwarg - e.g. request_id.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_RECORD_ATTRS:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """Human-readable logs in local dev (settings.debug), one-JSON-object-per-line in
    anything else, so `docker compose logs` output is directly machine-parseable
    without needing a separate log-shipping agent to reformat it.

    Without this, app.* loggers (email_service, telegram_service, ...) are silently
    dropped by the root logger's default WARNING level - in particular the dev-mode
    "email/Telegram disabled, logging instead" messages (README's "read the link from
    the log" workflow) would never actually appear anywhere.
    """
    handler = logging.StreamHandler()
    if settings.debug:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    else:
        handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1)
