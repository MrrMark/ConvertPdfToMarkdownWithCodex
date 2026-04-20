@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run_batch_folder_windows.ps1" %*
exit /b %ERRORLEVEL%
