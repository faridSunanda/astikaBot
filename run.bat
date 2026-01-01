@echo off
echo ====================================
echo TeknikBot - Running Bot
echo ====================================
echo.

REM Check if venv exists
if not exist "venv" (
    echo [ERROR] Virtual environment belum ada!
    echo [INFO] Jalankan setup.bat terlebih dahulu.
    pause
    exit /b 1
)

echo [INFO] Mengaktifkan virtual environment...
call venv\Scripts\activate.bat

echo [INFO] Menjalankan bot...
echo.
python bot.py
