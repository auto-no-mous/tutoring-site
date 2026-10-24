<#
.SYNOPSIS
    Скачивает свежий бэкап my-tutor.ru с сервера на этот компьютер.

.DESCRIPTION
    1. Запускает на сервере ops/backup.sh: дамп базы, загруженные файлы, серверные
       настройки (backend/.env и т.п.) - тот же архив, что делает ночной таймер.
       Запуск через systemd-run: если SSH-соединение оборвётся (маршрут до сервера
       бывает нестабильным, см. ops/README.md), бэкап всё равно доделается.
    2. Скачивает архив по scp, при обрыве повторяет.
    3. Проверяет его: контрольная сумма совпадает с серверной, архив распаковывается,
       внутри есть база, файлы и настройки.
    4. Хранит последние -Keep копий, старые удаляет.

    В архиве персональные данные учеников и пароли/токены сайта (backend/.env) -
    храните папку там, куда нет доступа у посторонних, и не кладите её в облачную
    синхронизацию без шифрования. Подробнее - ops/local-backup/README.md.

    Нужен доступ по SSH к серверу под алиасом из ~/.ssh/config (по умолчанию
    my-tutor, ключ ops/secrets/deploy_key).

.PARAMETER Destination
    Куда складывать архивы. По умолчанию - %USERPROFILE%\Backups\my-tutor.

.PARAMETER Keep
    Сколько последних архивов хранить. По умолчанию 30.

.PARAMETER UseLatest
    Не делать свежий бэкап, а скачать последний готовый (ночной, 03:15 UTC).

.PARAMETER SshHost
    Алиас сервера из ~/.ssh/config. По умолчанию my-tutor.

.EXAMPLE
    .\backup-to-local.ps1
    .\backup-to-local.ps1 -Destination D:\Backups\my-tutor -Keep 10
#>
param(
    [string]$Destination = (Join-Path $env:USERPROFILE "Backups\my-tutor"),
    [int]$Keep = 30,
    [switch]$UseLatest,
    [string]$SshHost = "my-tutor"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RemoteBackupDir = "/opt/backups"
$Attempts = 3
# Системный tar (bsdtar): у tar из Git путь вида C:\... читается как адрес
# удалённого хоста, и проверка архива падает.
$Tar = Join-Path $env:SystemRoot "System32\tar.exe"

function Step([string]$text) { Write-Host "`n== $text" -ForegroundColor Cyan }

# Команда на сервере с повторами: соединение до сервера иногда рвётся посреди
# рукопожатия, и одна неудача не должна валить весь бэкап.
function Invoke-Remote([string]$command) {
    for ($i = 1; $i -le $Attempts; $i++) {
        $output = & ssh -o BatchMode=yes -o ConnectTimeout=15 $SshHost $command
        if ($LASTEXITCODE -eq 0) { return $output }
        if ($i -lt $Attempts) {
            Write-Host "   соединение не удалось (код $LASTEXITCODE), повтор $($i + 1) из $Attempts..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }
    throw "Команда на сервере не выполнилась после $Attempts попыток: $command"
}

foreach ($tool in @("ssh", "scp")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Не найден $tool. Установите клиент OpenSSH: Параметры -> Приложения -> Дополнительные компоненты -> Клиент OpenSSH."
    }
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null

if (-not $UseLatest) {
    Step "Делаю свежий бэкап на сервере"
    $unit = "my-tutor-local-backup-$(Get-Date -Format 'yyyyMMddHHmmss')"
    Invoke-Remote "sudo systemd-run --quiet --unit=$unit /opt/my-tutor/ops/backup.sh" | Out-Null
    $deadline = (Get-Date).AddMinutes(15)
    do {
        Start-Sleep -Seconds 5
        $state = (Invoke-Remote "systemctl show $unit -p ActiveState --value") -join ""
        Write-Host "   ...$state"
    } while ($state -in @("active", "activating") -and (Get-Date) -lt $deadline)
    $result = (Invoke-Remote "systemctl show $unit -p Result --value 2>/dev/null; true") -join ""
    # Отработавший unit systemd может уже убрать - тогда о результате судим по
    # свежести архива ниже.
    if ($result -and $result -ne "success") {
        throw "Бэкап на сервере завершился с ошибкой ($result). Подробности: ssh $SshHost sudo journalctl -u $unit"
    }
}

Step "Ищу архив на сервере"
$remote = ((Invoke-Remote "ls -t $RemoteBackupDir/my-tutor-*.tar.gz | head -1") -join "").Trim()
if (-not $remote) { throw "На сервере нет архивов в $RemoteBackupDir" }
$info = ((Invoke-Remote "stat -c '%Y %s' $remote; sha256sum $remote | cut -d' ' -f1") -join " ").Trim() -split "\s+"
$remoteTime = [DateTimeOffset]::FromUnixTimeSeconds([long]$info[0]).LocalDateTime
$remoteSize = [long]$info[1]
$remoteHash = $info[2].ToUpper()
Write-Host "   $remote, $([math]::Round($remoteSize / 1MB, 1)) МБ, создан $($remoteTime.ToString('dd.MM.yyyy HH:mm'))"
if (-not $UseLatest -and ((Get-Date) - $remoteTime).TotalMinutes -gt 20) {
    throw "Свежий архив не появился: самый новый на сервере создан $($remoteTime.ToString('dd.MM.yyyy HH:mm'))."
}

Step "Скачиваю"
$name = "my-tutor-$($remoteTime.ToString('yyyy-MM-dd_HHmm')).tar.gz"
$target = Join-Path $Destination $name
$partial = "$target.part"
$downloaded = $false
for ($i = 1; $i -le $Attempts -and -not $downloaded; $i++) {
    & scp -q -o BatchMode=yes -o ConnectTimeout=15 "${SshHost}:$remote" $partial
    $downloaded = ($LASTEXITCODE -eq 0) -and (Test-Path $partial) -and ((Get-Item $partial).Length -eq $remoteSize)
    if (-not $downloaded -and $i -lt $Attempts) {
        Write-Host "   скачать не удалось, повтор $($i + 1) из $Attempts..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }
}
if (-not $downloaded) { throw "Архив не скачался после $Attempts попыток." }

Step "Проверяю архив"
$localHash = (Get-FileHash -Algorithm SHA256 $partial).Hash
if ($localHash -ne $remoteHash) {
    Remove-Item $partial
    throw "Контрольная сумма не совпала с серверной - файл повреждён при скачивании. Запустите ещё раз."
}
$listing = & $Tar -tzf $partial
if ($LASTEXITCODE -ne 0) { throw "Архив не читается ($Tar вернул $LASTEXITCODE)." }
foreach ($required in @("./db.dump", "./storage/", "./config/backend.env")) {
    if (-not ($listing -contains $required)) { throw "В архиве нет $required - бэкап неполный." }
}
Move-Item -Force $partial $target
Write-Host "   контрольная сумма совпадает, внутри база, файлы ($(@($listing | Where-Object { $_ -like './storage/*' -and $_ -notlike '*/' }).Count) шт.) и настройки"

$old = @(Get-ChildItem $Destination -Filter "my-tutor-*.tar.gz" | Sort-Object LastWriteTime -Descending | Select-Object -Skip $Keep)
if ($old.Count -gt 0) {
    Step "Удаляю старые копии (храню последние $Keep)"
    $old | ForEach-Object { Write-Host "   $($_.Name)"; Remove-Item $_.FullName }
}

Write-Host "`nГотово: $target" -ForegroundColor Green
