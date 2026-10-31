@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\github_upload.ps1"
exit /b %ERRORLEVEL%
