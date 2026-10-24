@echo off
rem Двойной щелчок - скачать свежий бэкап my-tutor.ru на этот компьютер.
rem Сам скрипт - backup-to-local.ps1 рядом; параметры см. в нём или в README.md.
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup-to-local.ps1" %*
echo.
pause
