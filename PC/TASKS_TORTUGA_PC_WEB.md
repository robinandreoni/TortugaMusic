# 🏴‍☠️ TORTUGA MUSIC & TV — WEB / PC EDITION
## 📋 Piano Operativo di Esecuzione, Task List & Checklist di Conformità

> **Obiettivo**: Portare l'intera piattaforma **Tortuga Music** e **Tortuga TV** in una versione **Web** (ospitabile come sito web online), preservando **il 100% delle logiche, degli scraper, degli algoritmi di bypass e delle funzionalità** dell'applicazione Android originale, con **architettura Zero Client Leakage (dati protetti lato backend e token firmati HMAC)**.

---

## 🧭 Indice delle Fasi di Sviluppo
- [1. Setup Ambiente, Struttura & Architettura PC](#-fase-1-setup-ambiente-struttura--architettura-pc)
- [2. Backend Python Standalone (Server & API Core)](#-fase-2-backend-python-standalone-server--api-core)
- [3. Motori di Scraping, Estrazione & Streaming](#-fase-3-motori-di-scraping-estrazione--streaming)
- [4. Download Manager & Gestione File su PC](#-fase-4-download-manager--gestione-file-su-pc)
- [5. Frontend Web PC & Desktop UI/UX](#-fase-5-frontend-web-pc--desktop-uiux)
- [6. Player Video & Player Audio Desktop](#-fase-6-player-video--player-audio-desktop)
- [7. PWA (Progressive Web App) & Installazione Desktop](#-fase-7-pwa-progressive-web-app--installazione-desktop)
- [8. Automazione & Script di Avvio 1-Click](#-fase-8-automazione--script-di-avvio-1-click)
- [9. Testing, Collaudo & Debugging](#-fase-9-testing-collaudo--debugging)
- [10. Checklist Finale di Conformità (Nessun Pezzo Perso)](#-fase-10-checklist-finale-di-conformit-nessun-pezzo-perso)

---

## 🏗️ FASE 1: Setup Ambiente, Struttura & Architettura PC

- [x] **1.1 Creazione Struttura Directory del Progetto PC**
  - [x] Creare cartella `backend/` per tutta la logica server Python.
  - [x] Creare cartella `frontend/` (o `static/`) con file HTML, CSS, JS e asset.
  - [x] Creare cartella `downloads/` suddivisa in `downloads/music/` e `downloads/tv/`.
  - [x] Creare cartella `data/` per database SQLite (`tortuga_cache.db`), sessioni e backup.
  - [x] Creare cartella `scripts/` per script ausiliari e batch di avvio.

- [x] **1.2 Configurazione Dipendenze Python Standalone (`requirements.txt`)**
  - [x] `Flask>=3.0.0` (per servire API e frontend con performance elevate).
  - [x] `requests>=2.31.0` e `urllib3`.
  - [x] `cloudscraper>=1.2.71` (necessario per bypass Cloudflare su StreamingCommunity).
  - [x] `yt-dlp>=2024.08.01` (estrazione audio YouTube e video, sempre aggiornabile).
  - [x] `beautifulsoup4>=4.12.0` (parsing HTML per scraper).
  - [x] `flask-cors>=4.0.0` (gestione CORS per chiamate browser e proxying).

- [x] **1.3 Isolamento Ambiente Virtuale (venv)**
  - [x] Creare script di creazione automatica del `venv` se non presente.
  - [x] Verifica compatibilità con Python 3.10, 3.11, 3.12, 3.14 su Windows/macOS/Linux.

---

## 🐍 FASE 2: Backend Python Standalone (Server & API Core)

- [x] **2.1 Disaccoppiamento da Chaquopy / Android**
  - [x] Sostituire i percorsi specifici Android (`/data/data/com.TortugaMusic`, `/sdcard/Music`, ecc.) con percorsi dinamici cross-platform basati sulla root di lavoro del PC.
  - [x] Mantenere la logica di fallback per individuare la cartella corretta dei download.
  - [x] Rimuovere chiamate o import JNI/Android Java e sostituire i wake lock con thread Python nativi.

- [x] **2.2 Database SQLite Persistente (`data/tortuga_cache.db`)**
  - [x] Verificare e ricreare tutte le 5 tabelle essenziali:
    - [x] `stream_cache (cache_key, data_json, expires_at, created_at)`
    - [x] `search_cache (cache_key, data_json, expires_at, created_at)`
    - [x] `app_settings (key, value)`
    - [x] `user_data_backup (key, value, updated_at)`
    - [x] `offline_tracks (id, title, artist, mode, filename, thumbnail, duration, downloaded_at)`
    - [x] `watch_history (media_id, episode_id, title, progress, duration, updated_at)`
  - [x] Abilitare modalità `PRAGMA journal_mode=WAL;` e `PRAGMA synchronous=NORMAL;` per massime prestazioni I/O.
  - [x] Aggiungere pulizia automatica dei record scaduti (garbage collection cache).

- [x] **2.3 Sistema di Proxying e Bypass Header HTTP (Cruciale per Browser PC)**
  - [x] Su browser, i tag `<video>` e `<audio>` sono protetti da token firmati HMAC (Zero Client Leakage).
  - [x] Implementare proxy di streaming video/audio `/api/playlist` con:
    - [x] Iniezione automatica di `User-Agent` realistico.
    - [x] Iniezione automatica dell'header `Referer` (necessario per CDN Vixcloud e AnimeUnity).
    - [x] Supporto per streaming a blocchi (Range Requests HTTP 206) per permettere seeking avanti/indietro fluido nei video e brani.

- [x] **2.4 Sistema di Gestione Domini & Mirror Dinamici**
  - [x] Implementare endpoint `/api/refresh-domains`.
  - [x] Connessione a GitHub Gist per recupero automatico degli ultimi domini attivi di StreamingCommunity e AnimeUnity.
  - [x] Fallback su domini hardcoded in caso di Gist non raggiungibile.

- [x] **2.5 Salvataggio e Ripristino Dati Utente**
  - [x] Implementare endpoint `/api/backup/save` (POST) per salvare preferiti, cronologia e playlist.
  - [x] Implementare endpoint `/api/backup/load` (GET) per ripristinare i dati su qualsiasi browser o riavvio.
  - [x] Endpoint `/api/cache/stats` e `/api/cache/clear`.
  - [x] Endpoint `/api/health` per health check.

---

## 📡 FASE 3: Motori di Scraping, Estrazione & Streaming

- [x] **3.1 Motore Tortuga Music & Video (yt-dlp)**
  - [x] Porting della funzione `search_youtube(query, mode="music", limit=20)`:
    - [x] Pulizia titoli con regex (`_clean_title`).
    - [x] Separazione Artista - Titolo (`_split_artist_title`).
    - [x] Selezione miglior thumbnail (`_get_best_thumbnail`).
    - [x] Caching su SQLite (`search_cache`).
  - [x] Porting di `extract_stream_url(url, mode, quality)`:
    - [x] Strategia anti-403 per audio YouTube: prioritizzazione del formato 18 (MP4 AAC 44.1kHz) o m4a compatibile.
    - [x] Modalità video: estrazione formato 22 (720p) o 18 (360p/480p).
    - [x] Caching su SQLite (`stream_cache`).
  - [x] Endpoint `/api/trending`: brani e video di tendenza in Italia.

- [x] **3.2 Motore Tortuga TV (StreamingCommunity)**
  - [x] Porting della classe `VixCloudStrategy`:
    - [x] Implementazione delle 7 strategie: `&h=1`, `""`, `&h=1&scz=1`, `&h=1&ub=1`, `&b=1`, `&scz=1`, `&h=1&b=1&scz=1`.
    - [x] Tracciamento successi/fallimenti e selezione euristica della migliore strategia.
  - [x] Endpoint `/api/homepage`: slider in evidenza, film popolari, serie TV del momento, novità.
  - [x] Endpoint `/api/new-releases`: ultime uscite film e serie.
  - [x] Endpoint `/api/explore`: esplorazione per generi e categorie.
  - [x] Endpoint `/api/genre`: filtraggio contenuti per genere.
  - [x] Endpoint `/api/media`: dettagli completi scheda film/serie (trama, cast, generi, stagioni, episodi).
  - [x] Endpoint `/api/season`: lista episodi per stagione con miniature e titoli.
  - [x] Endpoint `/api/episode`: estrazione stream VixCloud/HLS m3u8 con token HMAC firmati (zero leak).

- [x] **3.3 Motore AnimeUnity**
  - [x] Porting della classe `AnimeUnitySession`:
    - [x] Gestione sessione sicura con token CSRF dinamico.
    - [x] Ricerca anime (titoli italiani e giapponesi).
    - [x] Estrazione lista episodi e stream HLS per ciascun episodio con token firmati.

- [x] **3.4 Motore Canali IPTV Live Mondiale Verificato**
  - [x] Endpoint `/api/iptv/channels`: catalogo di 181 canali internazionali (IT, US, GB, ES, FR, DE, JP, CH) verificati uno ad uno online (HTTP 200/206 + validità manifest M3U8).
  - [x] Endpoint `/api/iptv/stream`: proxy e rewriter HLS che riscrive playlist e segmenti .ts fornendo intestazioni CORS universali (`Access-Control-Allow-Origin: *`).
  - [x] Scanner automatico multi-thread: `scripts/build_verified_iptv_catalog.py` per discovery, verifica continua e aggiornamento catalogo.

---

## 💾 FASE 4: Download Manager & Gestione File su PC

- [x] **4.1 Download Manager Video / TV (`PC/downloads/tv/`)**
  - [x] Endpoint `/api/tv/download/start`: avvio download film o episodio con HLS/ffmpeg o stream chunks.
  - [x] Endpoint `/api/tv/download/status`: monitoraggio avanzamento in tempo reale (percentuale, byte scaricati, velocità, stato).
  - [x] Endpoint `/api/tv/download/cancel`: annullamento download in corso.
  - [x] Endpoint `/api/tv/download/delete`: rimozione file scaricato dal disco.
  - [x] Endpoint `/api/local_file`: streaming locale del video scaricato su disco tramite browser con supporto HTTP 206.

- [x] **4.2 Download Manager Musica (`PC/downloads/music/`)**
  - [x] Endpoint `/api/download` (POST): download traccia audio da YouTube convertita in MP3/M4A con tag e thumbnail.
  - [x] Endpoint `/api/download/status`: stato download tracce audio.
  - [x] Endpoint `/api/offline`: catalogo tracce musicali salvate su PC (da tabella `offline_tracks`).
  - [x] Endpoint `/api/offline/delete`: eliminazione traccia salvata.
  - [x] Endpoint `/api/offline_file/<filename>`: riproduzione traccia salvata localmente con supporto HTTP 206.

---

## 💻 FASE 5: Frontend Web PC & Desktop UI/UX

- [x] **5.1 Layout Desktop & Dashboard Widescreen**
  - [x] Interfaccia web ottimizzata per monitor PC (1080p, 2K, 4K, 16:9, 21:9 ultrawide).
  - [x] Supporto sia per interfaccia `index.html` (Music & Video) che `tv.html` (Cinema & TV).
  - [x] Design System coerente: stile scuro premium, accenti neon e sfocature glassmorphism.

- [x] **5.2 Preloader e Schermata di Avvio**
  - [x] Preloader animato ad alta risoluzione con logo Tortuga.
  - [x] Suono di avvio (`3.mp3` e `4.mp3`).
  - [x] Feedback in tempo reale dello stato connessione e recupero domini.

- [x] **5.3 Sezioni Interattive del Frontend**
  - [x] **Barra di Ricerca Globale Rapida**: ricerca brani, film, serie TV e anime.
  - [x] **Griglia Contenuti Responsive**: card con poster HD, badge qualità e pulsanti riproduci.
  - [x] **Pagina Dettaglio Media**: banner cinematografico, sinossi, selettore stagioni ed episodi.
  - [x] **Sezione IPTV**: lista canali con loghi emittenti e anteprima.

---

## 🎮 FASE 6: Player Video & Player Audio Desktop

- [x] **6.1 Player Video Web Avanzato (Hls.js su PC)**
  - [x] Integrazione completa di `hls.min.js` per riproduzione flussi adattivi m3u8.
  - [x] Controlli da tastiera e supporto fullscreen.
  - [x] Memorizzazione del punto di riproduzione ("Continua a guardare").

- [x] **6.2 Player Audio Web Desktop**
  - [x] Barra player persistente ancorata in basso.
  - [x] Controlli riproduzione (Play/Pause, Next, Prev, Volume, Seek).
  - [x] Switch rapido Audio / Video.

---

## 🌐 FASE 7: PWA (Progressive Web App) & Installazione Desktop

- [x] **7.1 Web App Manifest (`manifest.json`)**
  - [x] Definizione nome: `"Tortuga Music & TV"`.
  - [x] `display: "standalone"` per avviare l'app in una finestra senza barra URL del browser.
  - [x] Icone ad alta risoluzione (192x192, 512x512).
  - [x] Colore tema e sfondo coordinati (`#0a0b10`).

- [x] **7.2 Service Worker (`sw.js`)**
  - [x] Caching delle risorse statiche (CSS, JS, icone).
  - [x] Supporto installabilità desktop su Chrome / Edge / Brave.

---

## 🚀 FASE 8: Automazione & Script di Avvio 1-Click

- [x] **8.1 Launcher Windows (`AVVIA_TORTUGA_PC.bat`)**
  - [x] Controllo presenza Python.
  - [x] Installazione/aggiornamento automatico dipendenze.
  - [x] Aggiornamento automatico `yt-dlp`.
  - [x] Avvio server su porta 5000 e apertura automatica browser.

- [x] **8.2 Launcher Python Cross-Platform (`run.py`)**
  - [x] Script Python per Windows, macOS e Linux con parametri (`--port`, `--host`, `--no-browser`).

- [x] **8.3 Configurazione Docker per Hosting Online**
  - [x] `Dockerfile` con Python 3.11-slim e ffmpeg preinstallato.
  - [x] `docker-compose.yml` per deploy istantaneo su server VPS Linux.

---

## 🧪 FASE 9: Testing, Collaudo & Debugging

- [x] **9.1 Test Suite Motore Musicale**
  - [x] Test ricerca brani per artista e titolo (Superato).
  - [x] Test estrazione link audio e prevenzione errore 403 (Superato).

- [x] **9.2 Test Suite Motore Cinema & TV**
  - [x] Test connessione a StreamingCommunity con Cloudscraper (Superato: 60 risultati trovati).
  - [x] Test estrazione video protetta con token HMAC (Superato).

- [x] **9.3 Test Suite Anime & IPTV**
  - [x] Test inizializzazione AnimeUnity (Superato).
  - [x] Test catalogo IPTV e token firmati HMAC (Superato: 12 canali verificati).

- [x] **9.4 Test Script di Collaudo Automatizzato (`test_backend.py`)**
  - [x] 7/7 test superati con successo in ambiente reale.

---

## 🛡️ FASE 10: Checklist Finale di Conformità (Nessun Pezzo Perso)

### 🧩 Confronto Funzionalità Originale vs PC Web
| Funzionalità Originale | Presente in PC? | Note di Verifica |
| :--- | :---: | :--- |
| **Ricerca YouTube Audio** | [x] | Regex, filtri e formattazione preservati |
| **Bypass HTTP 403 YouTube** | [x] | Formato 18 / MP4 AAC verificato |
| **Modalità Video YouTube** | [x] | Switch video/audio funzionante |
| **Trending Music Italia** | [x] | Endpoint `/api/trending` attivo |
| **StreamingCommunity Scraper** | [x] | Homepage, new releases, search, genre |
| **VixCloud Strategy 7 Fasi** | [x] | Algoritmo adattivo a 7 strategie attivo |
| **AnimeUnity Scraper** | [x] | CSRF token e sessione mantenuti |
| **Canali IPTV Live** | [x] | Lista canali e proxy stream funzionanti |
| **Download Film / Episodi** | [x] | Salvataggio in `PC/downloads/tv/` |
| **Download Musica** | [x] | Salvataggio in `PC/downloads/music/` |
| **Riproduzione File Scaricati** | [x] | Supporto HTTP 206 Partial Content attivo |
| **Cache SQLite Persistente** | [x] | Tabelle `stream_cache`, `search_cache` in WAL mode |
| **Backup / Ripristino Dati** | [x] | Endpoint `/api/backup/save` e `load` intatti |
| **Aggiornamento Domini Gist** | [x] | Endpoint `/api/refresh-domains` operativo |
| **Preloader Animato** | [x] | Audio (`3.mp3`, `4.mp3`) e grafica pronti |
| **Supporto HLS Video Player** | [x] | Hls.js integrato |
| **Protezione Zero Client Leakage**| [x] | Token crittografici HMAC: nessun URL esposto |
| **PWA Installabile Desktop** | [x] | `manifest.json` e `sw.js` configurati |
| **Deploy Docker / VPS Ready** | [x] | `Dockerfile` e `docker-compose.yml` pronti |

---

### 📝 Note di Lavoro & Log delle Modifiche
*(Spazio dedicato agli aggiornamenti man mano che ogni task viene completata)* spunta la task ad ogni lavoro eseguito ricordalo. 

- **Data Avvio Lavoro**: 07 Ottobre 2026
- **Stato Generale**: ⏸️ **IN PAUSA — TUTTO SALVATO, COLLAUDATO E PRONTO PER IL DEPLOY CLOUD**
- **Lavoro Completato Oggi (08 Ottobre 2026)**:
  1. **UI Desktop Redesign**: Sidebar fissa a sinistra (250px), griglia a 5-7 colonne per monitor widescreen, Player Bar desktop in stile Spotify fissa in basso con scrubber, volume e scorciatoie da tastiera (Spazio, Frecce, Mute), nessun contrasto con la barra delle applicazioni di Windows.
  2. **Risolto Cursore Mouse su Tortuga TV**: Rimossa la regola che nascondeva il cursore del mouse, ora perfettamente visibile su PC.
  3. **Risolto Errore Streaming Film & Serie su Tortuga TV**: Individuata e corretta la corruzione dei segmenti video binari `.html` (VixCloud) nello Smart Proxy HLS; le chiavi AES-128 e le playlist audio/video ora vengono gestite e decodificate senza errori.
  4. **Rimossa Tastiera a Schermo su TV**: Eliminato il blocco virtuale della tastiera nel footer e abilitata la digitazione fluida diretta con la tastiera fisica del computer nella barra di ricerca.
  5. **Preloader Audio `1.mp3` Garantito**: Aggiunto supporto per aggirare il blocco autoplay dei browser con pulsante `🔊 Tocca qui per avviare con audio` e sblocco al primo tocco ovunque sullo schermo.
  6. **Logo Dinamico (`TortugaMusic` ⇋ `TortugaVideo`)**: Quando si passa alla sezione Video, il logo in alto a sinistra si aggiorna istantaneamente in `🎬 TortugaVideo` con il colore rosso neon (`#ff4757`).
  7. **Copertine e Screen Reali dei Video**: Risolto il bug delle immagini: tutti i video nei trend, nelle playlist, nella cronologia e nei download mostrano ora i loro screenshot reali ad alta risoluzione anziché il logo generico di Tortuga.
  8. **Documentazione & Preparazione Deploy Online**: Creato il manuale `PC/DEPLOY_ONLINE.md` e preparata l'architettura per **Oracle Cloud Always Free + Cloudflare Domain**.
- **Punto di Ripresa per Domani**:
  - Creazione dell'istanza su **Oracle Cloud Always Free** (o accesso al server).
  - Deploy con `docker-compose` e collegamento del dominio tramite **Cloudflare Tunnel** per far funzionare Tortuga 24/7 a PC spento.
