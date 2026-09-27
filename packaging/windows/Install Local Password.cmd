@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Source "%~dp0LocalPassword"
if errorlevel 1 pause
