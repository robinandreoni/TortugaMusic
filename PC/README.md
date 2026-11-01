# 🏴‍☠️ Tortuga Music & TV — Web / PC Edition

La versione **Web / PC Edition** di Tortuga Music & TV offre un'esperienza multimediale completa utilizzabile direttamente da browser desktop o come Progressive Web App (PWA), senza dipendenze da Chaquopy o dall'ambiente Android.

---

## 🎯 Caratteristiche

1. **Streaming Audio & Video Unificato**: Supporto completo per riproduzione musicale (YouTube/SoundCloud via `yt-dlp`), canali IPTV Live in streaming HLS nativo e film/serie TV.
2. **Backend Standalone Python**: Server Flask leggero con smart-proxy HLS integrato per aggirare le restrizioni CORS e gestire il caching dei flussi.
3. **Interfaccia Desktop Widescreen**: Layout reattivo ottimizzato per display 1080p, 2K e 4K, con controlli completi da tastiera e supporto a Media Session API.
4. **Accessibilità Remota & Cloudflare Tunnel**: Esposizione sicura su Internet con certificati SSL automatici senza necessità di aprire porte sul router.
5. **Supporto Mobile Termux**: Possibilità di eseguire il server Python direttamente su Android con Termux per streaming portatile.

---

## 🚀 Guida all'Avvio Rapido

### 1. Installazione Dipendenze (Python 3.10+)
Assicurati di avere [Python](https://www.python.org/) e [ffmpeg](https://ffmpeg.org/) installati sul sistema.
```bash
cd PC
pip install -r requirements.txt
```

### 2. Configurazione Credenziali (Opzionale)
Copia il file di esempio per abilitare il mirror resolver Telegram o la sincronizzazione Gist:
```bash
copy .env.example .env
```
Compila le variabili necessarie seguendo le istruzioni nel file `.env`.

### 3. Avvio Locale (Windows)
Fai doppio click su:
```text
AVVIA_TORTUGA_PC.bat
```
Oppure da terminale:
```bash
python run.py
```
Apri il browser all'indirizzo `http://localhost:5000`.

### 4. Condivisione Online (Cloudflare Tunnel)
Per trasmettere in streaming ovunque ti trovi su smartphone o dispositivi remoti:
```text
AVVIA_TORTUGA_ONLINE.bat
```
Consulta la guida dettagliata in [DEPLOY_ONLINE.md](DEPLOY_ONLINE.md) o [GUIDA_AVVIO_DA_TELEFONO.md](GUIDA_AVVIO_DA_TELEFONO.md) per l'avvio su Android Termux.

---

## 📁 Struttura della Cartella `PC/`

```text
PC/
├── backend/                    # Core server Flask, scraper, database, audio/video proxy
├── frontend/                   # UI HTML5, player video Hls.js, audio player e stili
├── data/                       # Cataloghi canali IPTV e seed di sincronizzazione
├── scripts/                    # Utility di ispezione e validazione playlist
├── .env.example                # Template per credenziali d'ambiente
├── run.py                      # Punto di ingresso del server locale
├── auto_tunnel.py              # Sincronizzazione automatica Cloudflare Tunnel
├── cloudflare_worker.js        # Script Worker per routing a dominio permanente
├── telegram_sc_bot.py          # Monitor bot Telegram Telethon
├── AVVIA_TORTUGA_PC.bat        # Launcher 1-click locale
├── AVVIA_TORTUGA_ONLINE.bat    # Launcher 1-click con tunnel pubblico
├── AVVIA_TORTUGA_ONLINE.sh     # Launcher per Android Termux
└── requirements.txt            # Dipendenze Python
```

---

## 📄 Licenza

Distribuito con licenza MIT — vedi il file [LICENSE](../LICENSE) principale.
Realizzato da [Robin Andreoni](https://github.com/robinandreoni) & [Tortuga Italia](https://www.tortugaitalia.com).
