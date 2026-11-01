@echo off
chcp 65001 > nul
title Tortuga Music & TV - Server Online & Cloudflare Tunnel
color 0A
cd /d "%~dp0"

echo ============================================================
echo   🏴‍☠️ TORTUGA MUSIC & TV - AVVIO SERVER ONLINE + TUNNEL
echo ============================================================
echo.
echo [*] Verifica ambiente locale...

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRORE] Python non trovato nel PATH.
    pause
    exit /b 1
)

echo [*] Pulizia eventuali processi precedenti...
taskkill /F /IM cloudflared.exe >nul 2>nul

echo [*] Avvio del server Flask locale (porta 5000)...
start "Tortuga Flask Server" /min cmd /c "python run.py --no-browser"

if exist "telegram_sc_bot.py" (
    echo [*] Avvio del Bot Telegram Mirror StreamingCommunity...
    start "Tortuga Telegram SC Bot" /min cmd /c "python telegram_sc_bot.py"
)

timeout /t 2 /nobreak > nul

echo [*] Avvio Cloudflare Tunnel e sincronizzazione dominio...
python auto_tunnel.py

pause
