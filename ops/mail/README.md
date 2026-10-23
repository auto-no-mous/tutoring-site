# Своя почта my-tutor.ru (Postfix + OpenDKIM)

Транзакционные письма сайта (подтверждение почты, сброс пароля) уходят через
собственный SMTP на том же сервере, без сторонних сервисов. Рассылок нет и не
планируется.

Схема:

```
backend (docker) --25--> host.docker.internal --> Postfix (хост) --25--> почта получателя
                                                     |
                                              OpenDKIM (подпись)
входящие: MX -> Postfix -> info@ -> личный ящик (пересылка) + копия в журнал админки
                        -> postmaster@/abuse@/no-reply@ -> только журнал почты админки
                           (ingest-mail.py; пересылку служебных см. «Октябрь 2026»)
```

Почему так, а не контейнером: Postfix нужен PTR, стабильный IP и системный
certbot — всё это уже есть на хосте, а в контейнере пришлось бы дублировать
сеть и сертификаты. Нагрузка — десятки писем в сутки, отдельный сервис избыточен.

## 0. Блокер: хостер режет исходящий порт 25

На aeza (как и у большинства хостеров) исходящие 25/465/587 закрыты по
умолчанию — пакеты дропаются, соединение уходит в таймаут. Проверить:

```
python3 -c "import socket;socket.create_connection(('alt1.gmail-smtp-in.l.google.com',25),timeout=10);print('open')"
```

Пока порт закрыт, письма будут копиться в очереди (`postqueue -p`) и через
`maximal_queue_lifetime` (3 дня) возвращаться отбойниками. Открывается заявкой в
поддержку хостера. Текст обращения:

> Здравствуйте!
>
> Прошу открыть исходящие подключения на порт 25 (SMTP) для моего VPS responsible-viol 193.233.247.209.
>
> На сервере работает сайт my-tutor.ru — сервис онлайн-занятий с репетиторами.
> Почта нужна исключительно для транзакционных писем самого сервиса:
> подтверждение адреса при регистрации и восстановление пароля. Массовых
> рассылок, маркетинга и покупных баз нет и не будет; письма отправляются
> только по действию самого пользователя, объём — несколько десятков писем в
> сутки.
>
> Почтовый сервер настроен по всем требованиям: Postfix + OpenDKIM, домен
> my-tutor.ru с записями SPF, DKIM и DMARC, обратная зона (PTR) для
> 193.233.247.209 будет указывать на mail.my-tutor.ru, HELO совпадает с PTR,
> работают адреса postmaster@ и abuse@. Открытого релея нет — отправка
> разрешена только с самого сервера.
>
> Также прошу настроить PTR-запись для 193.233.247.209 -> mail.my-tutor.ru.
>
> Спасибо!

Если хостер откажет — вариант Б: отдельный дешёвый VPS у провайдера, который 25
не блокирует; всё в этом каталоге настраивается там точно так же, меняются
только `MAIL_HOST`/IP в DNS, а backend ходит на него уже с логином и STARTTLS.

## 1. Установка

Порядок важен: сначала A-запись (иначе не выпустится сертификат), потом скрипт,
потом остальные DNS-записи (DKIM-ключ появляется только после установки).

1. В панели DNS добавить `A mail.my-tutor.ru -> 193.233.247.209`.
2. На сервере:

   ```
   cd /opt/my-tutor && git pull
   sudo FORWARD_TO=dr.lurko@gmail.com ops/mail/install.sh
   ```

   Скрипт ставит Postfix/OpenDKIM/postsrsd, выпускает сертификат для
   `mail.my-tutor.ru`, генерирует DKIM-ключ, открывает входящий 25/tcp в ufw и
   печатает готовые DNS-записи. Запускать повторно безопасно.
3. Добавить в DNS остальное — значения печатает сам скрипт:

   | Тип | Имя | Значение |
   | --- | --- | --- |
   | MX | `my-tutor.ru` (prio 10) | `mail.my-tutor.ru` |
   | TXT | `my-tutor.ru` | `v=spf1 ip4:193.233.247.209 -all` |
   | TXT | `mail._domainkey.my-tutor.ru` | `v=DKIM1; h=sha256; k=rsa; p=…` |
   | TXT | `_dmarc.my-tutor.ru` | `v=DMARC1; p=none; rua=mailto:postmaster@my-tutor.ru; adkim=s; aspf=s` |
   | TXT | `mail.my-tutor.ru` | `v=spf1 ip4:193.233.247.209 -all` |
   | PTR | `193.233.247.209` | `mail.my-tutor.ru` (в панели хостера) |

   `-all` в SPF (жёсткий отказ) можно ставить сразу: письма уходят только с этого
   IP. SPF для `mail.my-tutor.ru` нужен уведомлениям о недоставке: у них пустой
   отправитель, и SPF проверяется по имени из HELO. DMARC начинаем с `p=none` — это режим наблюдения; через пару недель, когда
   отчёты покажут, что всё подписывается, поменять на `p=quarantine`, потом на
   `p=reject`.
4. Включить отправку в `backend/.env` на сервере:

   ```
   SMTP_HOST=host.docker.internal
   SMTP_PORT=25
   SMTP_USER=
   SMTP_PASSWORD=
   SMTP_STARTTLS=false
   SMTP_FROM=no-reply@my-tutor.ru
   MAIL_FROM_NAME=my-tutor.ru
   MAIL_REPLY_TO=info@my-tutor.ru
   EMAIL_ENABLED=true
   FRONTEND_BASE_URL=https://my-tutor.ru
   ```

   Плюс токен приёма входящих, который напечатал установщик:

   ```
   MAIL_INGEST_TOKEN=<значение из /etc/my-tutor-mail-ingest.token>
   ```

   и перезапустить: `docker compose --profile bot up -d backend`.

   Пароль не нужен: Postfix релеит письма из своих сетей (`mynetworks`), а
   контейнер приходит с адреса докер-моста. Снаружи релей закрыт.

## 2. Проверка

```
# 1. Postfix жив и слушает
systemctl status postfix opendkim postsrsd
ss -lntp | grep :25

# 2. Письмо самому себе (подставьте свой ящик)
echo "test" | mail -s "test from my-tutor.ru" you@example.com   # если установлен bsd-mailx
# или без mailx:
sendmail -f no-reply@my-tutor.ru you@example.com <<'EOF'
Subject: test from my-tutor.ru

test
EOF

# 3. Очередь и лог
postqueue -p
journalctl -u postfix -n 50 --no-pager

# 4. Подпись DKIM ключом из DNS
opendkim-testkey -d my-tutor.ru -s mail -vvv

# 5. Из контейнера видно хостовый Postfix
docker compose exec backend python -c "import socket;socket.create_connection(('host.docker.internal',25),timeout=5);print('ok')"
```

Главная проверка доставляемости — отправить письмо на
[check-auth@verifier.port25.com](mailto:check-auth@verifier.port25.com): в ответ
придёт отчёт со строками `SPF check: pass`, `DKIM check: pass`,
`DMARC check: pass`. Альтернатива — mail-tester.com (даёт оценку 10/10) и
отправка на свой ящик в Gmail/mail.ru/Яндексе с проверкой «Показать оригинал».

Полезно (бесплатно, разово): зарегистрировать домен в постмастерах —
[postmaster.mail.ru](https://postmaster.mail.ru),
[postmaster.yandex.ru](https://postmaster.yandex.ru),
[Google Postmaster Tools](https://postmaster.google.com). Они показывают долю
спам-жалоб и репутацию IP.

## 3. Эксплуатация

- **Очередь**: `postqueue -p` — пусто в норме. `postqueue -f` — повторная попытка
  отправки всего, что застряло. `postsuper -d ALL` — очистить очередь.
- **Логи**: `journalctl -u postfix -f`. Строка `status=sent` — доставлено,
  `status=deferred` — временная ошибка (сервер получателя недоступен, ретраи
  продолжатся), `status=bounced` — отказ.
- **Сертификат** обновляется тем же `certbot.timer`, что и сертификат сайта;
  deploy-hook перезагружает Postfix.
- **Ротация DKIM-ключа** (раз в год-два): сгенерировать ключ с новым селектором
  (`DKIM_SELECTOR=mail2 sudo ops/mail/install.sh`), добавить TXT для нового
  селектора, дождаться распространения, удалить старую запись.
- **Смена ящика пересылки**: `sudo FORWARD_TO=новый@ящик ops/mail/install.sh`.
- **Бэкап**: приватный DKIM-ключ лежит в
  `/etc/opendkim/keys/my-tutor.ru/mail.private` и в `ops/backup.sh` не попадает —
  при переезде либо скопировать его, либо сгенерировать новый и обновить TXT.

## 4. Журнал почты в админке

Вкладка «Почта» в админке показывает статистику и журнал писем:

- **исходящие** пишет сам бэкенд при каждой отправке (успех и ошибку с текстом
  ошибки) - `app/services/email_log_service.py`;
- **входящие** попадают туда через `ingest-mail.py`: в `/etc/postfix/virtual`
  каждый служебный адрес имеет вторым получателем `mailingest@localhost`, алиас
  пайпит копию письма в `/usr/local/bin/my-tutor-ingest-mail.py`, а тот делает
  POST на `/api/v1/mail/inbound` с токеном из `/etc/my-tutor-mail-ingest.token`.
  В журнале хранится конверт и весь текст письма (кнопка «Показать полностью»;
  в списке - начало). Только текст: если у письма нет текстовой версии, скрипт
  переводит HTML в текст и сохраняет адреса ссылок в скобках, - чужую разметку
  админка не отображает. Вложения не сохраняются, в конце текста перечислены их
  имена; так отчёты DMARC (zip с XML) видны как факт прихода, но XML там не открыть.
  Оригинал письма на `info@` уходит и на личный ящик; письма на служебные адреса -
  только сюда.

  Скрипт на сервере - копия: `git pull` его не обновляет. После правки
  `ingest-mail.py` скопировать заново:
  `sudo install -m 755 ops/mail/ingest-mail.py /usr/local/bin/my-tutor-ingest-mail.py`.

Скрипт всегда завершается с кодом 0: если сайт лежит или токен не совпал, письмо
всё равно доставляется человеку, а в журнал просто не попадает (ошибка видна в
`journalctl -u postfix`). Проверить приём вручную:

```
printf 'From: test@example.com
To: info@my-tutor.ru
Subject: проверка

тело
'   | /usr/local/bin/my-tutor-ingest-mail.py; echo "код возврата: $?"
```

## 5. Чего здесь намеренно нет

- **IMAP/ящиков на сервере.** Входящее только пересылается на личный ящик;
  Dovecot, квоты и бэкапы писем не нужны. Если понадобится настоящий ящик
  `info@` — это отдельная задача.
- **Catch-all.** Принимаются только адреса из `postfix-virtual`, остальное
  отвергается на RCPT TO — иначе домен быстро наберёт спам и backscatter.
- **Spamhaus во входящих проверках.** Сервер резолвит через публичные
  1.1.1.1/8.8.8.8, а Spamhaus такие запросы не обслуживает. Вместо него - SpamCop и
  PSBL плюс проверки HELO и домена отправителя (`smtpd_*_restrictions` в
  `install.sh`). Из входящих за 60 дней Spamhaus знал 2 отправителя из 141, так что
  свой резолвер ради него не нужен.
- **IPv6.** `inet_protocols = ipv4`: у IPv6-адреса сервера нет PTR, а Gmail
  отвергает письма с IPv6 без обратной записи.

## 6. Октябрь 2026: IP в Spamhaus CSS

Разбор отчётов DMARC от Google показал, что IP сервера `193.233.247.209` внесён в
Spamhaus CSS (ответ `127.0.0.3`; соседние адреса подсети Aeza - нет). iCloud с 10
сентября отвергал все письма сайта (`550 5.7.1 ... listing in Spamhaus SBL`), Яндекс
11 октября отклонил пять писем как подозрительные на спам. Gmail и Mail.ru
принимали.

Что было не так и что сделано (23.10.2026):

- **Пересылка служебных адресов на Gmail.** На `postmaster@` приходят отчёты DMARC
  (Google, Mail.ru). Gmail притормаживал их пересылку («unusual rate of
  unsolicited mail»), через сутки Postfix отправлял отправителю уведомление о
  недоставке, а оно попадало в следующий отчёт как `fail` - тысячи отложенных
  попыток. Теперь `postmaster@`, `abuse@`, `no-reply@` идут только в журнал; на
  личный ящик пересылается лишь `info@`.
- **Неподписанные уведомления о недоставке.** Postfix по умолчанию не пропускает
  свои отбойники через milter - добавлено `internal_mail_filter_classes = bounce`.
  Плюс SPF для `mail.my-tutor.ru` (имя из HELO).
- **Спам во входящих пересылался дальше** - теперь отсекается на входе (раздел 5).

Исключение из CSS - самостоятельно, на
https://check.spamhaus.org/query/ip/193.233.247.209 (форма с подтверждением по
почте, автоматически страница не открывается). Подавать после исправлений, иначе
адрес попадёт в список снова. Проверить, в списке ли адрес (с сервера, мимо
публичных резолверов):

```
dig +short +norecurse @$(dig +short NS zen.spamhaus.org | head -1) 209.247.233.193.zen.spamhaus.org
```

Пустой ответ - не в списке; `127.0.0.3` - CSS. Доставку в iCloud после исключения
видно в `journalctl -u postfix@-` по `relay=mx0?.mail.icloud.com ... status=sent`.
