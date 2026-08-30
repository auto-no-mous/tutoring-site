# ops/

Вспомогательные файлы для администрирования продакшен-сервера.

`ops/secrets/` — SSH-ключ и учётные данные для доступа к серверу. Не в
git (см. `.gitignore`) — эти файлы существуют только на машинах, с
которых реально ходят на сервер. Если настраиваете доступ заново или
теряете эту папку — см. README.md проекта, раздел «Docker / продакшен»,
и создайте пользователя заново по той же схеме: отдельный sudo-пользователь
с доступом по ключу, `PasswordAuthentication`/`PermitRootLogin` выключены.

## Почта

`mail/` — установка и настройка собственного SMTP (Postfix + OpenDKIM) для
транзакционных писем сайта: скрипт `install.sh`, шаблоны конфигов и подробный
runbook в `mail/README.md` (включая текст заявки хостеру на разблокировку
исходящего порта 25 и список DNS-записей).

## Сеть для бота

В серверном `docker-compose.override.yml` (не в git) бот вынесен в отдельную сеть
`botnet` с IPv6 - так он ходит в Telegram API. Важно: `networks:` в compose заменяет
сеть по умолчанию целиком, поэтому у сервиса должны быть перечислены **обе** -
`botnet` и `default`. Без `default` бот не резолвит хост `postgres` и падает с
`Temporary failure in name resolution`. Пока база была файлом SQLite на общем томе,
это было незаметно.

## Бэкапы

`backup.sh` — ежедневный бэкап продакшен-сервера: дамп PostgreSQL
(`pg_dump -Fc` изнутри контейнера базы, консистентен при живых записях),
все загруженные файлы из тома `backend_storage`, плюс серверный конфиг,
которого нет в git (`backend/.env`, корневой `.env` с паролем базы,
`docker-compose.override.yml`, `ops-nginx/`) — без этого куска дамп БД
сам по себе бесполезен, сервер не поднимется в прежнем виде. Хранит последние 14 дней в `/opt/backups/` на самом
сервере, более старые удаляет автоматически (`find -mtime +14 -delete`)
- диск на хостинге не резиновый, поэтому бэкапы ротируются, а не копятся
вечно.

**Важно:** это защищает от «сломали данные/накатили плохую миграцию»,
но НЕ от потери самого сервера/диска — бэкапы лежат там же. Для защиты
от этого нужна ещё одна копия вне сервера (второй сервер по rsync,
объектное хранилище и т.п.) - пока не настроено, обсудить отдельно.

Установка на сервере (один раз):

```
sudo cp ops/systemd/my-tutor-backup.service ops/systemd/my-tutor-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now my-tutor-backup.timer
```

Проверить: `sudo systemctl list-timers my-tutor-backup.timer`, ручной
прогон — `sudo /opt/my-tutor/ops/backup.sh`.

Восстановление из бэкапа — распаковать архив, `config/` разложить по
местам (`backend/.env`, корневой `.env`, `docker-compose.override.yml`,
`ops-nginx/`), `storage/` целиком вернуть в volume `backend_storage`
(замена содержимого), поднять базу (`docker compose up -d postgres`) и
залить дамп:

```
docker exec -i my-tutor-postgres-1 pg_restore -U mytutor -d mytutor --clean --if-exists < db.dump
```

затем `docker compose --profile bot up -d`.
