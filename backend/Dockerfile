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
#
# --forwarded-allow-ips: без него Gunicorn доверяет X-Forwarded-For только с
# 127.0.0.1, а nginx стоит в соседнем контейнере и приходит с адреса docker-сети.
# Заголовок отбрасывался, request.client.host у КАЖДОГО запроса оказывался адресом
# nginx - и per-IP лимитер (app/core/rate_limit.py) складывал всех посетителей сайта
# в одно ведро: 10 регистраций в час и 10 входов в минуту на весь сайт сразу.
# Значение "*" безопасно ровно потому, что порт 8000 наружу не опубликован
# (docker-compose: expose, не ports) - достучаться до бэкенда может только nginx,
# который перезаписывает X-Forwarded-For своим $remote_addr (frontend/nginx.conf).
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "-w", "1", "--forwarded-allow-ips", "*"]
