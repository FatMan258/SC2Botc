@echo off
setlocal

if exist "%~dp0python.local.cmd" call "%~dp0python.local.cmd"

if defined BOTC_PYTHON (
    goto run_custom
)

py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 goto run_py

python -c "import sys" >nul 2>nul
if not errorlevel 1 goto run_python

echo Python 3 was not found.
echo Set BOTC_PYTHON or create BOTC_Tools\python.local.cmd.
exit /b 9009

:run_custom
"%BOTC_PYTHON%" "%~dp0botc.py" %*
exit /b %ERRORLEVEL%

:run_py
py -3 "%~dp0botc.py" %*
exit /b %ERRORLEVEL%

:run_python
python "%~dp0botc.py" %*
exit /b %ERRORLEVEL%
