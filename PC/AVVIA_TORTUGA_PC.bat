@echo off
chcp 65001 > nul
title Tortuga Music & TV - Server PC & Web
color 0B
cd /d "%~dp0"

echo ============================================================
echo   🏴‍☠️ TORTUGA MUSIC & TV - AVVIO AMBIENTE PC & WEB
echo ============================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRORE] Python non e installato o non e presente nel PATH di sistema.
    echo Scarica e installa Python da https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [*] Controllo e aggiornamento automatico dipendenze...
python -m pip install -r requirements.txt --quiet --no-warn-script-location

echo [*] Aggiornamento del motore yt-dlp all'ultima versione...
python -m pip install -U yt-dlp --quiet --no-warn-script-location

echo.
echo [*] Avvio del server web locale Tortuga...
echo [*] Il browser verra aperto automaticamente a breve.
echo.

python run.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Il server si e arrestato con codice di errore %errorlevel%.
    pause
)
