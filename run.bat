@echo off
REM Launch the RETRO ROSTER UCI driver. Set ENGINE to pick the strategy,
REM e.g. `set ENGINE=copybook` then run.bat. Defaults to kneejerk.
cd /d "%~dp0"
python -m retro.uci %*
