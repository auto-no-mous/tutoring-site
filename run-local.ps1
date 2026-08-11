<#
.SYNOPSIS
    Запускает backend и frontend my-tutor.ru локально для тестирования.

.DESCRIPTION
    Ставит зависимости (poetry/npm), применяет миграции, поднимает backend
    (uvicorn, http://127.0.0.1:8000) и frontend (Vite dev server,
    http://127.0.0.1:5173) каждый в своём окне PowerShell и открывает сайт
    в браузере. Если в backend/.env заданы TELEGRAM_ENABLED=true и
    TELEGRAM_BOT_TOKEN, дополнительно запускает Telegram-бота (long polling)
    ещё в одном окне. Также запускает цикл напоминаний о занятиях
    (app/scripts/send_reminders.py) - в проде это отдельный cron/systemd-
    таймер, здесь просто вызывается раз в минуту в своём окне. Чтобы
    остановить — закройте открывшиеся окна или нажмите Ctrl+C в каждом.

.PARAMETER SkipInstall
    Пропустить poetry install / npm install (быстрее, если зависимости уже стоят).
#>

param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

function Assert-Command($name, $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Не найдена команда '$name'. $hint"
    }
}

Assert-Command "poetry" "Установите Poetry: https://python-poetry.org/docs/#installation"
Assert-Command "npm" "Установите Node.js: https://nodejs.org/"

# --- backend: .env, зависимости, миграции ---
$envFile = Join-Path $backendDir ".env"
$envExample = Join-Path $backendDir ".env.example"
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host "Создан backend/.env из .env.example (значения по умолчанию подходят для локального теста)." -ForegroundColor Yellow
}

Push-Location $backendDir
try {
    if (-not $SkipInstall) {
        Write-Host "Backend: poetry install..." -ForegroundColor Cyan
        poetry install
    }
    Write-Host "Backend: применяю миграции (alembic upgrade head)..." -ForegroundColor Cyan
    poetry run alembic upgrade head
} finally {
    Pop-Location
}

# --- frontend: зависимости ---
if (-not $SkipInstall) {
    Push-Location $frontendDir
    try {
        Write-Host "Frontend: npm install..." -ForegroundColor Cyan
        npm install
    } finally {
        Pop-Location
    }
}

# --- предупреждение, если порты уже заняты ---
foreach ($port in 8000, 5173) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        Write-Host "Порт $port уже слушается — похоже, сервер уже запущен." -ForegroundColor Yellow
    }
}

# --- запуск серверов в отдельных окнах ---
Write-Host "Запускаю backend (http://127.0.0.1:8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd `"$backendDir`"; poetry run uvicorn app.main:app --reload --port 8000"
)

Write-Host "Запускаю frontend (http://127.0.0.1:5173)..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd `"$frontendDir`"; npm run dev"
)

# --- Telegram-бот (только если настроен в .env) ---
function Get-EnvValue($path, $key) {
    $line = Get-Content $path | Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -Last 1
    if (-not $line) { return $null }
    return ($line -split "=", 2)[1].Trim()
}

$telegramEnabled = Get-EnvValue $envFile "TELEGRAM_ENABLED"
$telegramToken = Get-EnvValue $envFile "TELEGRAM_BOT_TOKEN"
$telegramUsername = Get-EnvValue $envFile "TELEGRAM_BOT_USERNAME"
$telegramConfigured = ($telegramEnabled) -and ($telegramEnabled.ToLower() -eq "true") -and ($telegramToken)

if ($telegramConfigured) {
    if (-not $telegramUsername) {
        Write-Host "TELEGRAM_BOT_USERNAME не задан в backend/.env - кнопка 'Подключить Telegram' в Настройках не будет работать, хотя бот запустится." -ForegroundColor Yellow
    }
    Write-Host "Запускаю Telegram-бота (long polling)..." -ForegroundColor Green
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "cd `"$backendDir`"; poetry run python -m app.scripts.run_telegram_bot"
    )
} else {
    Write-Host "Telegram-бот не запущен: TELEGRAM_ENABLED/TELEGRAM_BOT_TOKEN не заданы в backend/.env (пропустите, если Telegram-уведомления не нужны)." -ForegroundColor DarkGray
}

# --- Напоминания о занятиях ("Скоро занятие" - Telegram/почта/системные уведомления) ---
# send_reminders.py - одноразовый cron-friendly скрипт (см. его докстринг и README):
# в проде он вызывается по расписанию (systemd timer/cron), сам не крутится в цикле.
# Здесь просто эмулируем такой планировщик локально, вызывая его раз в минуту - этого
# достаточно с учётом окна допуска (tolerance_minutes=5) в send_upcoming_reminders.
Write-Host "Запускаю напоминания о занятиях (проверка раз в минуту)..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd `"$backendDir`"; while (`$true) { poetry run python -m app.scripts.send_reminders; Start-Sleep -Seconds 60 }"
)

Write-Host "Жду, пока серверы поднимутся..." -ForegroundColor Cyan
Start-Sleep -Seconds 6

Write-Host ""
Write-Host "Готово:" -ForegroundColor Green
Write-Host "  Сайт:        http://127.0.0.1:5173"
Write-Host "  API/Swagger: http://127.0.0.1:8000/docs"
if ($telegramConfigured) {
    Write-Host "  Telegram-бот: запущен (long polling)"
}
Write-Host "  Напоминания:  запущены (проверка раз в минуту)"
Write-Host "Чтобы остановить — закройте открывшиеся окна PowerShell (или Ctrl+C в каждом)."

Start-Process "http://127.0.0.1:5173"
