@echo off
REM lichess-bot wrapper for the shannstein engine (Windows).
cd /d "%~dp0\..\.."
set ENGINE=shannstein
python -m retro.uci %*
