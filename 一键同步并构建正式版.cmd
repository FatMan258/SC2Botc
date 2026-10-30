@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\quick_sync.ps1" -Mode production
exit /b %ERRORLEVEL%
