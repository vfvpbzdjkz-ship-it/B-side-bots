@echo off
REM lichess-bot wrapper for the kneejerk engine (Windows).
cd /d "%~dp0\..\.."
set ENGINE=kneejerk
python -m retro.uci %*
