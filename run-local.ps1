<#
.SYNOPSIS
    Запускает backend и frontend it-tutor.pro локально для тестирования.

.DESCRIPTION
    Ставит зависимости (poetry/npm), применяет миграции, поднимает backend
    (uvicorn, http://127.0.0.1:8000) и frontend (Vite dev server,
    http://127.0.0.1:5173) каждый в своём окне PowerShell и открывает сайт
    в браузере. Чтобы остановить — закройте оба открывшихся окна или
    нажмите Ctrl+C в каждом из них.

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

Write-Host "Жду, пока серверы поднимутся..." -ForegroundColor Cyan
Start-Sleep -Seconds 6

Write-Host ""
Write-Host "Готово:" -ForegroundColor Green
Write-Host "  Сайт:        http://127.0.0.1:5173"
Write-Host "  API/Swagger: http://127.0.0.1:8000/docs"
Write-Host "Чтобы остановить — закройте открывшиеся окна PowerShell (или Ctrl+C в каждом)."

Start-Process "http://127.0.0.1:5173"
