@echo off
REM lichess-bot wrapper for the mirror engine (Windows).
cd /d "%~dp0\..\.."
set ENGINE=mirror
python -m retro.uci %*
