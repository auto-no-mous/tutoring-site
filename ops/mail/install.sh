#!/usr/bin/env bash
# Ставит собственный SMTP для my-tutor.ru: Postfix (отправка + приём служебных
# адресов) + OpenDKIM (подпись) + postsrsd (SRS для пересылки).
#
# Скрипт идемпотентный: повторный запуск не ломает уже настроенное, а доводит
# конфигурацию до нужного состояния. Запускать на сервере из клона репозитория:
#
#   sudo FORWARD_TO=you@example.com /opt/my-tutor/ops/mail/install.sh
#
# После установки он печатает DNS-записи, которые нужно добавить в панели хостера.
# Полный порядок действий и проверки - в ops/mail/README.md.
set -euo pipefail

MAIL_HOST="${MAIL_HOST:-mail.my-tutor.ru}"
MAIL_DOMAIN="${MAIL_DOMAIN:-my-tutor.ru}"
FORWARD_TO="${FORWARD_TO:?Укажите почту для пересылки служебных писем: FORWARD_TO=you@example.com}"
DKIM_SELECTOR="${DKIM_SELECTOR:-mail}"
# Сети, из которых Postfix принимает письма на отправку наружу. Сюда попадает
# только докер-мост этого же сервера: контейнер backend ходит на host-gateway:25.
TRUSTED_NETWORKS="${TRUSTED_NETWORKS:-127.0.0.0/8 [::1]/128 172.16.0.0/12}"
CERTBOT_WEBROOT="${CERTBOT_WEBROOT:-/opt/my-tutor/certbot-webroot}"
# Секрет, которым скрипт приёма входящих авторизуется в бэкенде. Если не задан -
# берётся уже установленный, иначе генерируется новый.
INGEST_TOKEN_FILE=/etc/my-tutor-mail-ingest.token
CONF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Запускать от root: sudo FORWARD_TO=... $0" >&2
  exit 1
fi

log() { printf '\n\033[36m==> %s\033[0m\n' "$*"; }

# --- 0. Проверка исходящего 25 ------------------------------------------------
# Хостеры по умолчанию режут SMTP наружу. Установка при закрытом порте не вредна,
# но письма будут копиться в очереди - об этом лучше знать сразу.
log "Проверяю исходящий порт 25"
if python3 - <<'PY'; then
import socket, sys
try:
    socket.create_connection(("alt1.gmail-smtp-in.l.google.com", 25), timeout=10).close()
except OSError as exc:
    print(f"    порт 25 наружу НЕ работает: {exc}")
    sys.exit(1)
print("    порт 25 наружу открыт")
PY
  PORT25_OPEN=1
else
  PORT25_OPEN=0
  echo "    Письма будут накапливаться в очереди (postqueue -p), пока хостер не откроет порт."
  echo "    Текст заявки в поддержку - в ops/mail/README.md."
fi

# --- 1. Пакеты ----------------------------------------------------------------
log "Ставлю пакеты"
export DEBIAN_FRONTEND=noninteractive
debconf-set-selections <<EOF
postfix postfix/main_mailer_type select Internet Site
postfix postfix/mailname string ${MAIL_DOMAIN}
EOF
apt-get update -qq
apt-get install -y -qq postfix opendkim opendkim-tools postsrsd certbot >/dev/null
echo "${MAIL_DOMAIN}" > /etc/mailname

# --- 2. TLS-сертификат для mail.<домен> --------------------------------------
# Выпускается тем же certbot и через тот же webroot, что и сертификат сайта:
# nginx на :80 - дефолтный сервер, поэтому ACME-запрос на mail.<домен> он тоже
# обслужит. Нужен для STARTTLS на входящих письмах.
if [[ -d "/etc/letsencrypt/live/${MAIL_HOST}" ]]; then
  log "Сертификат для ${MAIL_HOST} уже есть"
else
  log "Выпускаю сертификат для ${MAIL_HOST}"
  certbot certonly --webroot -w "${CERTBOT_WEBROOT}" -d "${MAIL_HOST}" \
    --non-interactive --agree-tos --register-unsafely-without-email \
    --deploy-hook "systemctl reload postfix" || {
      echo "    Не удалось выпустить сертификат - проверьте, что A-запись ${MAIL_HOST} уже указывает на этот сервер."
      echo "    Установка продолжится, TLS на входящих будет выключен до повторного запуска."
    }
fi

# --- 3. Postfix ---------------------------------------------------------------
log "Настраиваю Postfix"
postconf -e "myhostname = ${MAIL_HOST}"
postconf -e "mydomain = ${MAIL_DOMAIN}"
postconf -e "myorigin = \$mydomain"
postconf -e "mydestination = \$myhostname, localhost.localdomain, localhost"
postconf -e "inet_interfaces = all"
# Только IPv4: у IPv6-адреса сервера нет PTR, а Gmail отвергает письма с IPv6
# без обратной записи. Входящие тоже идут по IPv4 - MX указывает на A-запись.
postconf -e "inet_protocols = ipv4"
postconf -e "mynetworks = ${TRUSTED_NETWORKS}"
postconf -e "relayhost ="
postconf -e "smtpd_banner = \$myhostname ESMTP"
postconf -e "biff = no"
postconf -e "append_dot_mydomain = no"
postconf -e "message_size_limit = 10485760"
postconf -e "maximal_queue_lifetime = 3d"
postconf -e "bounce_queue_lifetime = 1d"

# Приём: только домен сайта и только адреса из /etc/postfix/virtual.
postconf -e "virtual_alias_domains = ${MAIL_DOMAIN}"
postconf -e "virtual_alias_maps = hash:/etc/postfix/virtual"

# Релей строго для своих сетей; наружу - никакой пересылки чужих писем.
postconf -e "smtpd_helo_required = yes"
postconf -e "disable_vrfy_command = yes"
postconf -e "smtpd_relay_restrictions = permit_mynetworks, reject_unauth_destination"
postconf -e "smtpd_recipient_restrictions = permit_mynetworks, reject_unauth_destination, reject_non_fqdn_recipient, reject_unknown_recipient_domain"
postconf -e "smtpd_client_restrictions = permit_mynetworks, reject_unauth_pipelining"
# Проверки по DNSBL (zen.spamhaus.org) намеренно НЕ включены: сервер резолвит через
# публичные 1.1.1.1/8.8.8.8, а Spamhaus такие запросы не обслуживает. Входящих у нас
# всего три служебных адреса, и всё уходит в Gmail с его собственными фильтрами.

# TLS. На исходящих - оппортунистический (шифруем, если принимающий сервер умеет);
# требовать нельзя, иначе часть писем просто не уйдёт.
postconf -e "smtp_tls_security_level = may"
postconf -e "smtp_tls_loglevel = 1"
postconf -e "smtp_tls_CApath = /etc/ssl/certs"
if [[ -d "/etc/letsencrypt/live/${MAIL_HOST}" ]]; then
  postconf -e "smtpd_tls_security_level = may"
  postconf -e "smtpd_tls_cert_file = /etc/letsencrypt/live/${MAIL_HOST}/fullchain.pem"
  postconf -e "smtpd_tls_key_file = /etc/letsencrypt/live/${MAIL_HOST}/privkey.pem"
  postconf -e "smtpd_tls_loglevel = 1"
fi

# Подпись DKIM через milter.
postconf -e "milter_default_action = accept"
postconf -e "milter_protocol = 6"
postconf -e "smtpd_milters = inet:127.0.0.1:8891"
postconf -e "non_smtpd_milters = inet:127.0.0.1:8891"

# SRS: при пересылке info@ -> личный ящик конверт переписывается на наш домен,
# иначе SPF отправителя не сойдётся и Gmail положит письмо в спам.
# postsrsd 2.x общается с Postfix через unix-сокет в очереди (socketmap), 1.x - через
# два TCP-порта. Определяем по наличию /etc/postsrsd.conf, он появился только во 2.x.
if [[ -f /etc/postsrsd.conf ]]; then
  postconf -e "sender_canonical_maps = socketmap:unix:srs:forward"
  postconf -e "recipient_canonical_maps = socketmap:unix:srs:reverse"
else
  postconf -e "sender_canonical_maps = tcp:127.0.0.1:10001"
  postconf -e "recipient_canonical_maps = tcp:127.0.0.1:10002"
fi
postconf -e "sender_canonical_classes = envelope_sender"
# Только конверт: переписывать ещё и заголовок To означало бы показывать получателю
# служебный SRS-адрес вместо настоящего.
postconf -e "recipient_canonical_classes = envelope_recipient"

log "Настраиваю адреса приёма (пересылка на ${FORWARD_TO})"
sed "s|@FORWARD_TO@|${FORWARD_TO}|g; s|@MAIL_DOMAIN@|${MAIL_DOMAIN}|g" \
  "${CONF_DIR}/postfix-virtual" > /etc/postfix/virtual
postmap /etc/postfix/virtual

# Системная почта (cron, certbot, ошибки дисков) - туда же.
if grep -q '^root:' /etc/aliases 2>/dev/null; then
  sed -i "s|^root:.*|root: ${FORWARD_TO}|" /etc/aliases
else
  echo "root: ${FORWARD_TO}" >> /etc/aliases
fi
newaliases

# --- 3b. Приём входящих в журнал админки --------------------------------------
# Postfix отдаёт копию каждого входящего письма скрипту, тот кладёт конверт и
# превью в журнал сайта. Оригинал при этом всё равно уходит на личный ящик.
log "Настраиваю приём входящих в журнал сайта"
install -m 755 "${CONF_DIR}/ingest-mail.py" /usr/local/bin/my-tutor-ingest-mail.py
if [[ ! -s "${INGEST_TOKEN_FILE}" ]]; then
  MAIL_INGEST_TOKEN="${MAIL_INGEST_TOKEN:-$(head -c 24 /dev/urandom | base64 | tr -d '=+/')}"
  printf '%s' "${MAIL_INGEST_TOKEN}" > "${INGEST_TOKEN_FILE}"
fi
# Алиасы Postfix выполняются от nobody:nogroup - токен читаем только этой группе.
chown root:nogroup "${INGEST_TOKEN_FILE}"
chmod 640 "${INGEST_TOKEN_FILE}"
if ! grep -q '^mailingest:' /etc/aliases 2>/dev/null; then
  echo 'mailingest: "|/usr/local/bin/my-tutor-ingest-mail.py"' >> /etc/aliases
  newaliases
fi

# --- 4. OpenDKIM --------------------------------------------------------------
log "Настраиваю OpenDKIM"
install -d -o opendkim -g opendkim -m 750 "/etc/opendkim/keys/${MAIL_DOMAIN}"
if [[ ! -f "/etc/opendkim/keys/${MAIL_DOMAIN}/${DKIM_SELECTOR}.private" ]]; then
  opendkim-genkey -b 2048 -d "${MAIL_DOMAIN}" -s "${DKIM_SELECTOR}" -D "/etc/opendkim/keys/${MAIL_DOMAIN}"
  chown opendkim:opendkim "/etc/opendkim/keys/${MAIL_DOMAIN}/${DKIM_SELECTOR}."*
  chmod 600 "/etc/opendkim/keys/${MAIL_DOMAIN}/${DKIM_SELECTOR}.private"
fi
cp "${CONF_DIR}/opendkim.conf" /etc/opendkim.conf
sed "s|@MAIL_DOMAIN@|${MAIL_DOMAIN}|g; s|@DKIM_SELECTOR@|${DKIM_SELECTOR}|g" \
  "${CONF_DIR}/opendkim-key.table" > /etc/opendkim/key.table
sed "s|@MAIL_DOMAIN@|${MAIL_DOMAIN}|g; s|@DKIM_SELECTOR@|${DKIM_SELECTOR}|g" \
  "${CONF_DIR}/opendkim-signing.table" > /etc/opendkim/signing.table
sed "s|@MAIL_DOMAIN@|${MAIL_DOMAIN}|g" "${CONF_DIR}/opendkim-trusted.hosts" > /etc/opendkim/trusted.hosts
chown -R opendkim:opendkim /etc/opendkim
usermod -aG opendkim postfix

# --- 5. postsrsd --------------------------------------------------------------
log "Настраиваю postsrsd"
if [[ -f /etc/postsrsd.conf ]]; then           # postsrsd 2.x: список в фигурных скобках
  sed -i "s|^domains *=.*|domains = { \"${MAIL_DOMAIN}\" }|" /etc/postsrsd.conf
  grep -q "^domains" /etc/postsrsd.conf || echo "domains = { \"${MAIL_DOMAIN}\" }" >> /etc/postsrsd.conf
elif [[ -f /etc/default/postsrsd ]]; then      # postsrsd 1.x
  sed -i "s|^SRS_DOMAIN=.*|SRS_DOMAIN=${MAIL_DOMAIN}|" /etc/default/postsrsd
fi

# --- 6. Фаервол и запуск ------------------------------------------------------
log "Открываю входящий 25/tcp и перезапускаю сервисы"
ufw allow 25/tcp >/dev/null 2>&1 || true
systemctl enable --now opendkim postsrsd >/dev/null 2>&1 || true
systemctl restart opendkim postsrsd
systemctl enable --now postfix >/dev/null 2>&1 || true
systemctl restart postfix

# --- 7. Что добавить в DNS ----------------------------------------------------
DKIM_TXT=$(tr -d '\n' < "/etc/opendkim/keys/${MAIL_DOMAIN}/${DKIM_SELECTOR}.txt" \
  | sed -e 's/.*(\s*//' -e 's/\s*).*//' -e 's/"\s*"//g' -e 's/"//g' -e 's/^\s*//')
SERVER_IP=$(hostname -I | awk '{print $1}')

cat <<EOF

================= DNS-записи для ${MAIL_DOMAIN} =================
A     ${MAIL_HOST}                     ->  ${SERVER_IP}
MX    ${MAIL_DOMAIN}      (prio 10)    ->  ${MAIL_HOST}
TXT   ${MAIL_DOMAIN}                   ->  v=spf1 ip4:${SERVER_IP} -all
TXT   ${DKIM_SELECTOR}._domainkey.${MAIL_DOMAIN}  ->  ${DKIM_TXT}
TXT   _dmarc.${MAIL_DOMAIN}            ->  v=DMARC1; p=none; rua=mailto:postmaster@${MAIL_DOMAIN}; adkim=s; aspf=s
PTR   ${SERVER_IP}                     ->  ${MAIL_HOST}   (в панели хостера)
=================================================================

Порт 25 наружу: $([[ $PORT25_OPEN -eq 1 ]] && echo "открыт" || echo "ЗАКРЫТ - письма будут ждать в очереди")

Чтобы входящие письма попадали в журнал админки, добавьте в backend/.env:
MAIL_INGEST_TOKEN=$(cat "${INGEST_TOKEN_FILE}")
Проверки после добавления записей - в ops/mail/README.md.
EOF
