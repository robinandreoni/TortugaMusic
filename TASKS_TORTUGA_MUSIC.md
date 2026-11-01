# 🎵 Tortuga Music - Piano delle Attività (Tasks)

Questo documento traccia in dettaglio tutte le attività necessarie per lo sviluppo di **Tortuga Music**, un'applicazione di streaming musicale (stile Spotify/YouTube Music) basata sulla solida architettura già sperimentata con Tortuga TV.

## 🏗️ 1. Architettura e Struttura di Base
- [ ] Creazione del progetto Android nativo (Java/Kotlin).
- [ ] Integrazione di **Chaquopy** per eseguire il backend in Python direttamente sul dispositivo.
- [ ] Configurazione della `WebView` come interfaccia grafica principale (Frontend in HTML, CSS, JS).
- [ ] Setup dei permessi Android necessari (Internet, Wakelock per la riproduzione in background, ecc.).

## 🔄 2. Sistema di Preloader e Comunicazione Sicura (Ispirato a Tortuga TV)
- [ ] Implementazione del meccanismo di **Preloader** all'avvio.
- [ ] Collegamento a un **GitHub Gist** (o proxy simile) per il recupero dinamico dei domini attivi.
- [ ] Logica di fallback nel caso in cui i domini principali siano irraggiungibili o bloccati (Anti-blocco / Proxying).
- [ ] Pagina di caricamento iniziale (Splash Screen) con animazioni e feedback sullo stato della connessione, identica o simile allo stile di Tortuga TV.

## 🐍 3. Motore di Estrazione Audio (Backend Python)
- [ ] Sviluppo del modulo Python (`server.py`) per interagire con le piattaforme musicali (es. YouTube Music).
- [ ] Utilizzo di librerie per l'estrazione diretta degli stream audio puri (es. `yt-dlp` o chiamate API proxy personalizzate) senza pubblicità.
- [ ] Creazione di un'interfaccia server locale (es. Flask su localhost) per comunicare con la `WebView` e inviare i link `.m4a`/`.webm` o i metadati dei brani.
- [ ] Gestione delle playlist e delle code di riproduzione lato Python.

## 🎨 4. Interfaccia Grafica (Frontend Web)
- [ ] L'applicazione sarà orientata in **Verticale (Portrait)** per smartphone, a differenza di Tortuga TV.
- [ ] Preloader grafico riadattato e ottimizzato per lo schermo verticale.
- [ ] Se l'utente decide di mettere il player a schermo intero (Full Screen), l'app ruoterà e si posizionerà in orizzontale.
- [ ] Sviluppo di un'interfaccia utente in stile **Spotify / YouTube Music**.
- [ ] Player audio persistente in basso (Play, Pausa, Brano Precedente, Brano Successivo, Scrubber).
- [ ] **Home Page dinamica:** Vista con le classifiche, playlist consigliate o ultime uscite, molto curata nei suggerimenti musicali.
- [ ] **Barra di Ricerca mirata:** Sistema di ricerca in tempo reale rigoroso, configurato per trovare esclusivamente brani musicali e artisti, scartando pubblicità o risultati non pertinenti.

## 🎧 5. Riproduzione e Media Session
- [ ] Integrazione della **MediaSessionCompat** in Android per far sì che la musica continui a suonare anche con l'app in background o a schermo spento.
- [ ] Collegamento dei tasti multimediali del telefono/televisore al player della WebView.
- [ ] Notifica di riproduzione persistente sulla barra di stato di Android con copertina del brano, titolo e controlli rapidi.

## 🛡️ 6. Sicurezza e Rilascio
- [ ] Offuscamento del codice Java (ProGuard/R8) e del codice Javascript.
- [ ] Protezione avanzata del codice Python (offuscamento stringhe, script pre-build) per evitare reverse engineering dell'algoritmo di estrazione.
- [ ] Test approfondito su emulatore e dispositivi fisici reali.
- [ ] Generazione del bundle `.aab` (con conformità 16 KB page-size di Gradle 8.7+) e pubblicazione finale.
