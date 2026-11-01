#!/bin/sh
set -e

# Avvia il bot Telegram in background per mantenere sempre aggiornati i domini
if [ -f "telegram_sc_bot.py" ] && [ -f "sc_bot_session.session" ]; then
    echo "[*] Avvio telegram_sc_bot in background..."
    python -u telegram_sc_bot.py &
fi

# Avvia il server web Tortuga PC / Web in primo piano
echo "[*] Avvio Tortuga Music & TV Server..."
exec python run.py --no-browser
