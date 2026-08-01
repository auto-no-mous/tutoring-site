from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Shared across the auth router (see api/v1/auth.py) - in-memory storage is fine for
# a single-instance deployment; move to a Redis-backed storage_uri if the backend is
# ever scaled to multiple processes/instances.
limiter = Limiter(key_func=get_remote_address, enabled=settings.rate_limit_enabled)
