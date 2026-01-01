@echo off
echo ====================================
echo TeknikBot - Setup Virtual Environment
echo ====================================
echo.

REM Check if venv exists
if exist "venv" (
    echo [INFO] Virtual environment sudah ada.
    echo [INFO] Mengaktifkan environment...
) else (
    echo [INFO] Membuat virtual environment baru...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Gagal membuat virtual environment!
        echo [ERROR] Pastikan Python sudah terinstall dengan benar.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment berhasil dibuat!
)

echo.
echo [INFO] Mengaktifkan virtual environment...
call venv\Scripts\activate.bat

echo.
echo [INFO] Menginstall dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Gagal menginstall dependencies!
    pause
    exit /b 1
)

echo.
echo ====================================
echo [OK] Setup selesai!
echo ====================================
echo.
echo Untuk menjalankan bot:
echo   1. Aktifkan environment: venv\Scripts\activate
echo   2. Jalankan bot: python bot.py
echo.
echo Atau gunakan: run.bat
echo.
pause
