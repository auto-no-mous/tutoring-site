FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.4.1

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY . .
RUN mkdir -p storage && chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
# Single worker: app/core/rate_limit.py's per-IP auth limiter is in-memory, scoped to
# one process - multiple Gunicorn workers would each keep their own counter, silently
# multiplying the effective limit on brute-force-sensitive endpoints (login,
# registration, password reset) by the worker count. Async I/O under one Uvicorn
# worker already handles concurrent requests fine for this app's scale; move to a
# Redis-backed limiter storage (slowapi supports it) before adding more workers.
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "-w", "1"]
