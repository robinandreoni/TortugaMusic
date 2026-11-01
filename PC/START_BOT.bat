@echo off
chcp 65001 > nul
cd /d "%~dp0"
title Tortuga TV - SC Telegram Bot
echo ==============================================
echo   AVVIO BOT STREAMING COMMUNITY & GIST SYNC
echo ==============================================
python -u telegram_sc_bot.py
pause

