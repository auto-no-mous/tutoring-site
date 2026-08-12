#!/bin/sh
# Daily backup of the my-tutor.ru production data: a consistent SQLite snapshot
# (taken via sqlite3's own backup API, safe to run while the app keeps writing)
# plus all uploaded files, and the server-local config that isn't in git
# (backend/.env, docker-compose.override.yml, ops-nginx/). Run as root (needed
# to read the docker-managed volume) via the my-tutor-backup.timer systemd unit
# - see ops/README.md for the one-time setup.
set -eu

PROJECT_DIR=/opt/my-tutor
CONTAINER=my-tutor-backend-1
BACKUP_DIR=/opt/backups
RETENTION_DAYS=14

STAMP=$(date +%F)
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

mkdir -p "$BACKUP_DIR"

docker exec "$CONTAINER" python3 -c "
import sqlite3
src = sqlite3.connect('/app/storage/db.sqlite3')
dst = sqlite3.connect('/app/storage/.backup-snapshot.sqlite3')
src.backup(dst)
dst.close()
src.close()
"

docker cp "$CONTAINER:/app/storage" "$WORKDIR/storage"
docker exec "$CONTAINER" rm -f /app/storage/.backup-snapshot.sqlite3
mv "$WORKDIR/storage/.backup-snapshot.sqlite3" "$WORKDIR/storage/db.sqlite3"

mkdir -p "$WORKDIR/config"
cp "$PROJECT_DIR/backend/.env" "$WORKDIR/config/backend.env"
[ -f "$PROJECT_DIR/docker-compose.override.yml" ] && cp "$PROJECT_DIR/docker-compose.override.yml" "$WORKDIR/config/"
[ -d "$PROJECT_DIR/ops-nginx" ] && cp -r "$PROJECT_DIR/ops-nginx" "$WORKDIR/config/"

tar czf "$BACKUP_DIR/my-tutor-$STAMP.tar.gz" -C "$WORKDIR" .

find "$BACKUP_DIR" -name 'my-tutor-*.tar.gz' -mtime "+$RETENTION_DAYS" -delete

echo "Backup done: $BACKUP_DIR/my-tutor-$STAMP.tar.gz ($(du -h "$BACKUP_DIR/my-tutor-$STAMP.tar.gz" | cut -f1))"
