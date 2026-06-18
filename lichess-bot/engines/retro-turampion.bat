@echo off
REM lichess-bot wrapper for the turampion engine (Windows).
cd /d "%~dp0\..\.."
set ENGINE=turampion
python -m retro.uci %*
