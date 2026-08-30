#!/bin/sh
# Daily backup of the my-tutor.ru production data: a PostgreSQL dump (pg_dump's
# custom format, taken from inside the postgres container - consistent while the
# app keeps writing), all uploaded files from the backend volume, and the
# server-local config that isn't in git (backend/.env, the root .env with the
# database password, docker-compose.override.yml, ops-nginx/). Run as root
# (needed to read the docker-managed volumes) via the my-tutor-backup.timer
# systemd unit - see ops/README.md for the one-time setup.
#
# Восстановление: распаковать архив, поднять postgres, затем
#   docker exec -i my-tutor-postgres-1 pg_restore -U mytutor -d mytutor --clean --if-exists < db.dump
# storage/ вернуть в том backend_storage, config/ разложить по местам.
set -eu

PROJECT_DIR=/opt/my-tutor
BACKEND_CONTAINER=my-tutor-backend-1
DB_CONTAINER=my-tutor-postgres-1
BACKUP_DIR=/opt/backups
RETENTION_DAYS=14

STAMP=$(date +%F)
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

mkdir -p "$BACKUP_DIR"

# Пользователь и база берутся из окружения самого контейнера: так скрипт не
# расходится с docker-compose.yml, если их однажды поменяют.
DB_USER=$(docker exec "$DB_CONTAINER" printenv POSTGRES_USER)
DB_NAME=$(docker exec "$DB_CONTAINER" printenv POSTGRES_DB)

# -Fc: сжатый формат, из которого pg_restore умеет разворачивать выборочно и
# параллельно. Обычный SQL-дамп читается глазами, но на восстановлении гораздо
# менее гибок.
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$WORKDIR/db.dump"

# Файлы (фото анкет и аккаунтов, вложения чата, домашние задания) живут в томе
# backend_storage - без них дамп базы бесполезен: ссылки в /files повиснут.
docker cp "$BACKEND_CONTAINER:/app/storage" "$WORKDIR/storage"

mkdir -p "$WORKDIR/config"
cp "$PROJECT_DIR/backend/.env" "$WORKDIR/config/backend.env"
# В корневом .env лежит пароль базы, которым подставляется DATABASE_URL в compose:
# без него поднятый из бэкапа сервер не достучится до собственной базы.
[ -f "$PROJECT_DIR/.env" ] && cp "$PROJECT_DIR/.env" "$WORKDIR/config/compose.env"
[ -f "$PROJECT_DIR/docker-compose.override.yml" ] && cp "$PROJECT_DIR/docker-compose.override.yml" "$WORKDIR/config/"
[ -d "$PROJECT_DIR/ops-nginx" ] && cp -r "$PROJECT_DIR/ops-nginx" "$WORKDIR/config/"

tar czf "$BACKUP_DIR/my-tutor-$STAMP.tar.gz" -C "$WORKDIR" .

find "$BACKUP_DIR" -name 'my-tutor-*.tar.gz' -mtime "+$RETENTION_DAYS" -delete

echo "Backup done: $BACKUP_DIR/my-tutor-$STAMP.tar.gz ($(du -h "$BACKUP_DIR/my-tutor-$STAMP.tar.gz" | cut -f1))"
