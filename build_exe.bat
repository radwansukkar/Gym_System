@echo off
chcp 65001 >nul
REM ===========================================================================
REM  Builds StarGym with PyInstaller (Windows).
REM  Run it from the project folder, with your virtual environment activated.
REM
REM    build_exe.bat            folder build : dist\StarGym\StarGym.exe   (recommended)
REM    build_exe.bat onefile    single file  : dist\StarGym.exe
REM
REM  IMPORTANT: every build deletes the dist folder. Never keep real data
REM  (gym.db) inside dist - copy the program to a permanent folder such as
REM  C:\StarGym and run it from there.
REM ===========================================================================

python -m pip install --upgrade pyinstaller pyzk
if errorlevel 1 goto fail

set MODE=--onedir
if /I "%~1"=="onefile" set MODE=--onefile

python -m PyInstaller --noconfirm --clean --noconsole %MODE% --name StarGym --icon assets\icon.ico --add-data "assets;assets" main.py
if errorlevel 1 goto fail

echo.
echo Build finished.
if /I "%~1"=="onefile" (
  echo Copy dist\StarGym.exe to a permanent folder, for example C:\StarGym
) else (
  echo Copy the whole folder to a permanent location, for example:
  echo   xcopy /E /I /Y dist\StarGym C:\StarGym
  echo This keeps gym.db, backups, app.log and config.json when you update later.
)
pause
exit /b 0

:fail
echo.
echo Build FAILED - read the messages above.
pause
exit /b 1
