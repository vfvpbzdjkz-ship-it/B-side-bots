@echo off
REM Build a standalone Windows executable (RetroRoster.exe) for the GUI.
REM
REM Run this once on a Windows machine that has Python installed. It uses
REM PyInstaller to bundle Python + the engines into a single .exe you can
REM double-click with nothing else installed. The finished file lands in dist\.
setlocal
cd /d "%~dp0"

echo Installing build dependencies...
python -m pip install --upgrade pyinstaller chess || goto :error

echo Building RetroRoster.exe ...
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name RetroRoster ^
    --collect-submodules retro ^
    RetroRoster.pyw || goto :error

echo.
echo Done. Your executable is at: dist\RetroRoster.exe
goto :eof

:error
echo.
echo Build failed. Make sure Python 3.11+ is installed and on PATH.
exit /b 1
