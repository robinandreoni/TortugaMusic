# 🏴‍☠️ Tortuga Music & TV — Web / PC Edition

Benvenuto nella directory del progetto **Tortuga Music & TV (Web / PC Edition)**!

Questo progetto è il porting standalone dell'applicazione Android **Tortuga Music** & **Tortuga TV** per l'utilizzo su **PC Desktop, browser web e Progressive Web App (PWA)**, senza vincoli di Chaquopy o dell'ambiente mobile.

---

## 📋 File Principale di Lavoro

Tutte le attività operative, le fasi di sviluppo, i test e la matrice di conformità sono descritti e tracciati nel file dedicato:

👉 **[TASKS_TORTUGA_PC_WEB.md](file:///c:/Users/robin/Desktop/TortugaMusic/PC/TASKS_TORTUGA_PC_WEB.md)**

---

## 🎯 Obiettivi Chiave del Progetto PC

1. **Nessuna logica persa**: 100% delle funzionalità audio (yt-dlp), film/serie (StreamingCommunity & Vixcloud con strategia a 7 fasi), anime (AnimeUnity), IPTV Live e download manager.
2. **Backend Standalone**: Server Python indipendente con cache SQLite persistente (`tortuga_cache.db`), gestione proxy stream e CORS per il web.
3. **Frontend Widescreen Desktop**: Interfaccia ottimizzata per schermi PC (1080p, 2K, 4K), player video Hls.js con controlli completi da tastiera (Spazio, Frecce, F, M, scorciatoie) e player audio con Media Session API.
4. **PWA & 1-Click Launch**: Web app installabile con un click su Chrome/Edge e script batch di avvio rapido con aggiornamento automatico delle dipendenze.
