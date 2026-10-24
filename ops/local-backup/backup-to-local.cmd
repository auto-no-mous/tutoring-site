@echo off
rem Double-click: download a fresh my-tutor.ru backup to this computer.
rem The work is done by backup-to-local.ps1 next to this file - see README.md.
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup-to-local.ps1" %*
echo.
pause
