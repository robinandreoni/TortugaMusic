#!/usr/bin/env bash
# ============================================================
#   🏴‍☠️ TORTUGA MUSIC & TV - INSTALLATORE AMBIENTE TERMUX
#   Installa Python, Git, FFmpeg, Cloudflared e tutte le librerie
# ============================================================

set -e

echo "============================================================"
echo "  🏴‍☠️ INSTALLAZIONE AMBIENTE TORTUGA SU ANDROID (TERMUX)"
echo "============================================================"
echo ""

# Rimuovi eventuale binario errato precedente
rm -f ./cloudflared 2>/dev/null || true

echo "[1/4] Aggiornamento pacchetti di sistema..."
pkg update -y

echo "[2/4] Installazione dipendenze native (Python, Git, FFmpeg, Cloudflared, Clang, Curl)..."
pkg install -y python git ffmpeg cloudflared clang libffi openssl curl

echo "[3/4] Aggiornamento pip..."
pip install --upgrade pip setuptools wheel

echo "[4/4] Installazione librerie Python di Tortuga..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
pip install -r requirements.txt

# Rendi eseguibile lo script di avvio
chmod +x AVVIA_TORTUGA_ONLINE.sh

echo ""
echo "============================================================"
echo "  ✅ INSTALLAZIONE COMPLETATA CON SUCCESSO!"
echo "  Per avviare Tortuga dal telefono digita semplicemente:"
echo "  ./AVVIA_TORTUGA_ONLINE.sh"
echo "============================================================"
