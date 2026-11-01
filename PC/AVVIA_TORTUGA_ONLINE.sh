#!/usr/bin/env bash
# ============================================================
#   🏴‍☠️ TORTUGA MUSIC & TV - AVVIO DA TELEFONO (TERMUX / ANDROID)
#   Avvia il server Flask locale e il Cloudflare Tunnel
#   aggiornando automaticamente l'indirizzo fisso:
#   https://tortuga.cybergrid.workers.dev
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "  🏴‍☠️ TORTUGA MUSIC & TV - MOBILE SERVER & CLOUDFLARE TUNNEL"
echo "============================================================"
# 0. Aggiornamento automatico da GitHub (se presente git)
if command -v git >/dev/null 2>&1 && [ -d ".git" ]; then
    echo "[*] Controllo aggiornamenti automatici da GitHub..."
    git pull origin main --quiet || true
fi
echo ""

# 1. Mantieni sveglio il processore Android (se dentro Termux)
if command -v termux-wake-lock >/dev/null 2>&1; then
    echo "[*] Blocco risparmio energetico Android (wake-lock attivo)..."
    termux-wake-lock
fi

# 2. Verifica Python
if ! command -v python >/dev/null 2>&1; then
    echo "[ERRORE] Python non trovato! Esegui prima: pkg install -y python"
    exit 1
fi

# 3. Rimuovi eventuale binario glibc errato scaricato in precedenza
if [ -f "./cloudflared" ]; then
    rm -f ./cloudflared
fi

# 4. Verifica o Installa Cloudflared nativo per Termux
if ! command -v cloudflared >/dev/null 2>&1; then
    echo "[*] Installazione nativa Cloudflared per Termux/Android..."
    pkg update -y && pkg install -y cloudflared
    if ! command -v cloudflared >/dev/null 2>&1; then
        echo "[ERRORE] Impossibile installare cloudflared automaticamente."
        echo "Digita manualmente in Termux: pkg install -y cloudflared"
        exit 1
    fi
fi

# 4b. Assicura certificati CA in Termux per evitare errori SSL x509
if [ -n "$PREFIX" ]; then
    if [ ! -f "$PREFIX/etc/tls/cert.pem" ]; then
        echo "[*] Installazione certificati CA in Termux..."
        pkg install -y ca-certificates
    fi
    export SSL_CERT_FILE="$PREFIX/etc/tls/cert.pem"
    export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
fi

# 5. Pulizia processi precedenti
echo "[*] Pulizia eventuali processi precedenti..."
killall -9 cloudflared >/dev/null 2>&1 || true
pkill -f "run.py" >/dev/null 2>&1 || true

# 6. Trap per chiusura pulita con CTRL+C
cleanup() {
    echo ""
    echo "[*] Arresto server e tunnel in corso..."
    kill "$FLASK_PID" >/dev/null 2>&1 || true
    killall -9 cloudflared >/dev/null 2>&1 || true
    if command -v termux-wake-unlock >/dev/null 2>&1; then
        termux-wake-unlock
    fi
    echo "[OK] Server fermato. Alla prossima!"
    exit 0
}
trap cleanup SIGINT SIGTERM

# 7. Avvio Server Flask in background
echo "[*] Avvio Server Flask locale (porta 5000)..."
python run.py --no-browser > flask.log 2>&1 &
FLASK_PID=$!

# Attendi che Flask sia pronto
echo "[*] Controllo disponibilità server locale..."
READY=0
for i in {1..8}; do
    if curl -s http://127.0.0.1:5000/api/health >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 1
done

if [ "$READY" -eq 1 ]; then
    echo "[OK] Server Flask attivo e rispondente!"
else
    echo "[INFO] Flask in avvio, log recente:"
    tail -n 8 flask.log 2>/dev/null || true
fi

# 8. Avvio Auto-Tunnel (gestisce il tunnel e aggiorna il dominio fisso)
echo "[*] Avvio Cloudflare Tunnel e sincronizzazione dominio..."
python auto_tunnel.py

# Se auto_tunnel termina, esegui pulizia
cleanup
