@echo off
chcp 65001 >nul
REM Builds ResetPasswords.exe (the owner's password recovery tool) with PyInstaller.
REM Run from the project folder with your virtual environment activated.
REM Keep the resulting exe with the owner only (USB stick), not on the gym laptop.

python -m pip install --upgrade pyinstaller pyzk
if errorlevel 1 goto fail

python -m PyInstaller --noconfirm --clean --noconsole --onefile --name ResetPasswords --icon assets\icon.ico --add-data "assets;assets" reset_passwords_gui.py
if errorlevel 1 goto fail

echo.
echo Done: dist\ResetPasswords.exe
echo Put it next to gym.db (or pick the file inside the tool) and run it.
pause
exit /b 0

:fail
echo.
echo Build FAILED - read the messages above.
pause
exit /b 1
