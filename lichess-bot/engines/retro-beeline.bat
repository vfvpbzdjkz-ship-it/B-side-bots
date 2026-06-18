@echo off
REM lichess-bot wrapper for the beeline engine (Windows).
cd /d "%~dp0\..\.."
set ENGINE=beeline
python -m retro.uci %*
