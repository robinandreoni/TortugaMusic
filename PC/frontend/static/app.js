/* ═══════════════════════════════════════════════════════════════
   Tortuga Music v2.2 — Application Logic (app.js)
   Handles: Unified Home Feed, Context-Aware Playlists & Downloads,
   Permanent Cache, Ultra-Fluid Playback, Foreground Service
   ═══════════════════════════════════════════════════════════════ */

const API = `${window.location.origin}/api`;
let audio = document.getElementById('audio-player');
if (!audio) {
    audio = document.createElement('video');
    audio.id = 'audio-player';
    audio.setAttribute('playsinline', '');
    audio.setAttribute('webkit-playsinline', '');
    audio.style.display = 'none';
}

// ─── State ─────────────────────────────────────────────────
let queue = [];
let queueIndex = -1;
let isPlaying = false;
let currentTrack = null;
let searchTimeout = null;
let currentMode = 'music';
let isExpanded = false;
let streamAbortController = null;
let streamQuality = localStorage.getItem('stream_quality') || 'high';
let activeDownloads = {};
let downloadPollInterval = null;
let currentTab = 'home';
let currentTrendingTracks = [];
let currentSearchResults = [];

function playFromTrending(index) {
    playFromList(currentTrendingTracks, index, 'trending');
}

function playFromSearch(index) {
    playFromList(currentSearchResults, index);
}

window.playFromTrending = playFromTrending;
window.playFromSearch = playFromSearch;

// ─── Play Modes per Section ───
let sectionPlayModes = {
    trending: 'seq',
    playlist: 'seq',
    download: 'seq'
};

try {
    const legacyModes = JSON.parse(localStorage.getItem('tortuga_section_modes') || '{}');
    const savedModes = JSON.parse(localStorage.getItem('tortuga_section_modes_v2') || '{}');
    sectionPlayModes = { ...sectionPlayModes, ...legacyModes, ...savedModes };
    if (legacyModes['playlist-music'] || legacyModes['playlist-video']) {
        sectionPlayModes.playlist = legacyModes['playlist-music'] || legacyModes['playlist-video'] || 'seq';
    }
    if (legacyModes.offline || legacyModes['download-music']) {
        sectionPlayModes.download = legacyModes.offline || legacyModes['download-music'] || 'seq';
    }
} catch(e) {}

function updateModeSwitchUI(section) {
    const $container = document.getElementById(`switch-${section}`);
    if (!$container) return;
    const mode = sectionPlayModes[section] || 'seq';
    const isRnd = mode === 'rnd';
    
    $container.classList.toggle('mode-rnd', isRnd);
    const $seqBtn = $container.querySelector('.seq-btn');
    const $rndBtn = $container.querySelector('.rnd-btn');
    if ($seqBtn) $seqBtn.classList.toggle('active', !isRnd);
    if ($rndBtn) $rndBtn.classList.toggle('active', isRnd);
}

function initPlayModeSwitches() {
    ['trending', 'playlist', 'download'].forEach(sec => updateModeSwitchUI(sec));
}

function togglePlayMode(section) {
    const current = sectionPlayModes[section] || 'seq';
    const next = current === 'seq' ? 'rnd' : 'seq';
    sectionPlayModes[section] = next;
    try {
        localStorage.setItem('tortuga_section_modes_v2', JSON.stringify(sectionPlayModes));
        saveBackup('tortuga_section_modes_v2', sectionPlayModes);
    } catch(e) {}
    
    updateModeSwitchUI(section);
    
    const sectionNames = {
        trending: 'In Tendenza per Te',
        playlist: currentMode === 'video' ? 'Playlist Video' : 'Playlist Musica',
        download: currentMode === 'video' ? 'Video Scaricati' : 'Canzoni Scaricate'
    };
    const modeText = next === 'rnd' ? 'Casuale 🔀' : 'In ordine 🔁';
    showCustomToast(`${sectionNames[section] || section}: ${modeText}`);
}

// ─── DOM refs ──────────────────────────────────────────────
const $preloader       = document.getElementById('preloader');
const $preloaderStatus = document.getElementById('preloader-status');
const $app             = document.getElementById('app');
const $searchInput     = document.getElementById('search-input');
const $btnClearSearch  = document.getElementById('btn-clear-search');
const $viewHome        = document.getElementById('view-home');
const $viewPlaylist    = document.getElementById('view-playlist');
const $viewDownload    = document.getElementById('view-download');
const $viewSearch      = document.getElementById('view-search');
const $trendingList    = document.getElementById('trending-list');
const $searchResults   = document.getElementById('search-results');
const $playerBar       = document.getElementById('player-bar');
const $playerExpanded  = document.getElementById('player-expanded');
const $progressFill    = document.getElementById('progress-fill');
const $seekSlider      = document.getElementById('seek-slider');
const $timeCurrent     = document.getElementById('time-current');
const $timeTotal       = document.getElementById('time-total');


// ═══════════════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', init);

function openTortugaTV() {
    sessionStorage.setItem('tortuga_skip_splash', '1');
    // 1. Stop background native MediaPlayer
    if (window.AndroidBridge && window.AndroidBridge.stopNativeAudio) {
        window.AndroidBridge.stopNativeAudio();
    }
    // 2. Pause and clear HTML5 player
    if (audio) {
        audio.pause();
        audio.currentTime = 0;
        audio.removeAttribute('src');
    }
    isPlaying = false;
    updatePlayButtons();
    syncMediaSession(false);

    // 3. Set orientation to landscape and navigate
    if (window.AndroidBridge && window.AndroidBridge.setOrientation) {
        window.AndroidBridge.setOrientation('landscape');
    }
    location.href = '/tv.html';
}

async function restoreUserDataBackup() {
    try {
        const r = await fetch(`${API}/backup/load`);
        const data = await r.json();
        const backup = data.backup || {};
        
        // 1. Dal server al browser (se il browser è vuoto)
        for (const [key, val] of Object.entries(backup)) {
            const currentVal = localStorage.getItem(key);
            if (!currentVal || currentVal === '[]' || currentVal === '{}' || currentVal === 'null') {
                const strVal = (typeof val === 'string') ? val : JSON.stringify(val);
                localStorage.setItem(key, strVal);
                console.log(`[Backup Restored] ${key}`);
            }
        }

        // 2. BIDIREZIONALE: Dal browser al server (se il server è nuovo/vuoto come su telefono)
        const localKeysToSync = [
            'tortuga_history_music',
            'tortuga_history_video',
            'tortuga_playlist_music',
            'tortuga_playlist_video',
            'tortuga_custom_playlists',
            'tortuga_history',
            'tortuga_watch_progress',
            'tortuga_section_modes_v2',
            'tortuga_volume_v2',
            'history_music',
            'history_video',
            'playlist_favorites_music',
            'playlist_favorites_video'
        ];
        
        for (const k of localKeysToSync) {
            const localVal = localStorage.getItem(k);
            if (localVal && localVal !== '[]' && localVal !== '{}' && localVal !== 'null') {
                if (!backup[k] || backup[k] === '[]' || backup[k] === '{}') {
                    try {
                        const parsed = JSON.parse(localVal);
                        saveBackup(k, parsed);
                        console.log(`[Auto-Sync to Server] ${k}`);
                    } catch(e) {
                        saveBackup(k, localVal);
                    }
                }
            }
        }
    } catch(e) {
        console.warn('[Backup restore error]', e);
    }
}

function saveBackup(key, value) {
    try {
        fetch(`${API}/backup/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key, value })
        }).catch(() => {});
    } catch(e) {}
}

function renderTrendingSkeletons() {
    if (!$trendingList) return;
    $trendingList.innerHTML = Array(6).fill(0).map(() => `
        <div class="skeleton-card">
            <div class="skeleton-card-img skeleton-shimmer"></div>
            <div class="skeleton-card-body">
                <div class="skeleton-line skeleton-shimmer"></div>
                <div class="skeleton-line short skeleton-shimmer"></div>
            </div>
        </div>
    `).join('');
}

function renderListSkeletons($container, count = 5) {
    if (!$container) return;
    $container.innerHTML = Array(count).fill(0).map(() => `
        <div class="skeleton-item">
            <div class="skeleton-item-thumb skeleton-shimmer"></div>
            <div class="skeleton-item-info">
                <div class="skeleton-line skeleton-shimmer"></div>
                <div class="skeleton-line short skeleton-shimmer"></div>
            </div>
        </div>
    `).join('');
}

async function init() {
    detectDeviceType();
    window.addEventListener('resize', detectDeviceType);
    window.addEventListener('orientationchange', detectDeviceType);
    updateBandwidthUI();
    if (window.updateBandwidthProjection) window.updateBandwidthProjection(5);

    // Per smartphone garantiamo la modalità Orizzontale (Landscape)
    if (window.AndroidBridge && window.AndroidBridge.setOrientation) {
        window.AndroidBridge.setOrientation('landscape');
    }

    const skipSplash = sessionStorage.getItem('tortuga_skip_splash') === '1';
    if (skipSplash) {
        sessionStorage.removeItem('tortuga_skip_splash');
        $preloader.style.display = 'none';
        $app.style.display = 'block';
    } else {
        $preloaderStatus.textContent = 'Inizializzazione motore...';
    }

    // Animated sequential showcase between brand pills in preloader
    let brandIdx = 0;
    const brandPills = [
        { id: 'brand-music', cls: 'active-music' },
        { id: 'brand-video', cls: 'active-video' },
        { id: 'brand-tv', cls: 'active-tv' }
    ];
    const brandInterval = setInterval(() => {
        brandPills.forEach(p => {
            const el = document.getElementById(p.id);
            if (el) el.className = 'brand-pill';
        });
        brandIdx = (brandIdx + 1) % brandPills.length;
        const activeP = brandPills[brandIdx];
        const activeEl = document.getElementById(activeP.id);
        if (activeEl) activeEl.className = `brand-pill ${activeP.cls}`;
    }, 700);

    // Avvia l'audio del preloader (1.mp3) su interazione
    const preloaderAudio = document.getElementById('preloader-audio');
    const preloaderAudioBtn = document.getElementById('preloader-audio-btn');
    let audioFinished = false;
    let audioStarted = false;

    window.triggerPreloaderAudio = async function() {
        if (!preloaderAudio || audioStarted) return;
        try {
            preloaderAudio.volume = 0.25;
            await preloaderAudio.play();
            audioStarted = true;
            if (preloaderAudioBtn) preloaderAudioBtn.style.display = 'none';
        } catch(e) {
            console.warn('Trigger preloader audio failed:', e);
        }
    };

    if (preloaderAudio && !skipSplash) {
        preloaderAudio.volume = 0.25;
        preloaderAudio.addEventListener('ended', () => { audioFinished = true; }, { once: true });
        preloaderAudio.addEventListener('error', () => { audioFinished = true; }, { once: true });
    } else {
        audioFinished = true;
    }

    // ═══ Pre-preloader Simpson ("The Andreoni") ═══
    const $simpsonPreloader = document.getElementById('simpson-preloader');
    const $simpsonBubble = document.getElementById('simpson-bubble');
    const $simpsonPwd = document.getElementById('simpson-pwd');
    const $simpsonMsg = document.getElementById('simpson-msg');
    const $simpsonSubmitBtn = document.getElementById('simpson-submit-btn');

    let simpsonLockoutTimer = null;

    window.toggleSimpsonPwd = function() {
        if (!$simpsonPwd) return;
        $simpsonPwd.type = $simpsonPwd.type === 'password' ? 'text' : 'password';
    };

    function startLockoutCountdown(seconds) {
        if (simpsonLockoutTimer) clearInterval(simpsonLockoutTimer);
        let rem = seconds;
        const updateText = () => {
            if (rem <= 0) {
                clearInterval(simpsonLockoutTimer);
                if ($simpsonMsg) {
                    $simpsonMsg.className = 'simpson-msg';
                    $simpsonMsg.textContent = 'Puoi riprovare ora.';
                }
                if ($simpsonSubmitBtn) $simpsonSubmitBtn.disabled = false;
                if ($simpsonPwd) $simpsonPwd.disabled = false;
                return;
            }
            const m = Math.floor(rem / 60);
            const s = rem % 60;
            const str = m > 0 ? `${m}m ${s < 10 ? '0' : ''}${s}s` : `${s}s`;
            if ($simpsonMsg) {
                $simpsonMsg.className = 'simpson-msg locked';
                $simpsonMsg.textContent = `⛔ Blocco attivo: riprova tra ${str}`;
            }
            if ($simpsonSubmitBtn) $simpsonSubmitBtn.disabled = true;
            if ($simpsonPwd) $simpsonPwd.disabled = true;
            rem--;
        };
        updateText();
        simpsonLockoutTimer = setInterval(updateText, 1000);
    }

    if ($simpsonPreloader && !skipSplash) {
        // Controllo se c'è un blocco attivo per questo IP
        fetch('/api/auth/status')
            .then(r => r.json())
            .then(st => {
                if (st.locked && st.lockout_seconds > 0) {
                    startLockoutCountdown(st.lockout_seconds);
                }
            })
            .catch(() => {});

        // Fa comparire la nuvoletta dopo 1 secondo come richiesto
        setTimeout(() => {
            if ($simpsonBubble) {
                $simpsonBubble.classList.add('visible');
                if ($simpsonPwd && !$simpsonPwd.disabled) {
                    $simpsonPwd.focus();
                }
            }
        }, 1000);
    }

    const authPromise = new Promise(resolve => {
        if (!$simpsonPreloader || skipSplash) {
            if ($simpsonPreloader) $simpsonPreloader.style.display = 'none';
            resolve();
            return;
        }

        window.submitSimpsonAuth = async function(e) {
            if (e) e.preventDefault();
            if (!$simpsonPwd) return;
            const pwd = $simpsonPwd.value.trim();
            if (!pwd) return;

            if ($simpsonSubmitBtn) $simpsonSubmitBtn.disabled = true;
            if ($simpsonMsg) {
                $simpsonMsg.className = 'simpson-msg';
                $simpsonMsg.textContent = 'Verifica parola d\'ordine...';
            }

            try {
                const res = await fetch('/api/auth/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: pwd })
                });
                const data = await res.json();

                if (data.success) {
                    if ($simpsonMsg) {
                        $simpsonMsg.className = 'simpson-msg success';
                        $simpsonMsg.textContent = '🎉 Parola d\'ordine corretta! Benvenuto!';
                    }

                    // L'utente ha appena interagito: avviamo subito 1.mp3 senza blocchi del browser!
                    window.triggerPreloaderAudio();

                    // Dissolvenza fluida dello sfondo e della nuvoletta
                    $simpsonPreloader.classList.add('fade-out');
                    setTimeout(() => {
                        $simpsonPreloader.style.display = 'none';
                        resolve();
                    }, 500);
                } else {
                    if ($simpsonBubble) {
                        $simpsonBubble.classList.add('shake');
                        setTimeout(() => $simpsonBubble.classList.remove('shake'), 500);
                    }
                    if (data.locked) {
                        startLockoutCountdown(data.lockout_seconds || 900);
                    } else {
                        if ($simpsonMsg) {
                            $simpsonMsg.className = 'simpson-msg error';
                            $simpsonMsg.textContent = data.error || 'Password errata!';
                        }
                        if ($simpsonSubmitBtn) $simpsonSubmitBtn.disabled = false;
                        $simpsonPwd.select();
                    }
                }
            } catch(err) {
                if ($simpsonMsg) {
                    $simpsonMsg.className = 'simpson-msg error';
                    $simpsonMsg.textContent = 'Errore di connessione col server.';
                }
                if ($simpsonSubmitBtn) $simpsonSubmitBtn.disabled = false;
            }
        };
    });

    // Attendi che il server Flask sia pronto
    let ready = false;
    for (let i = 0; i < 30; i++) {
        try {
            const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(2000) });
            if (r.ok) { ready = true; break; }
        } catch(e) {}
        await sleep(400);
    }

    if (!ready) {
        $preloaderStatus.textContent = 'Errore connessione server!';
        clearInterval(brandInterval);
        return;
    }

    if (!skipSplash) {
        $preloaderStatus.textContent = 'Caricamento catalogo...';
    }

    // Restore playlists / history from SQLite or disk backup if fresh install
    await restoreUserDataBackup();

    // Inizializza il video player nel container dedicato espanso
    const expContainer = document.getElementById('expanded-video-container');
    if (expContainer && audio && !expContainer.contains(audio)) {
        expContainer.appendChild(audio);
    }
    if (audio) {
        audio.style.position = 'absolute';
        audio.style.top = '0';
        audio.style.left = '0';
        audio.style.width = '100%';
        audio.style.height = '100%';
        audio.style.objectFit = 'contain';
        audio.style.zIndex = '5';
    }

    // Setup Quality radio button in settings
    if (streamQuality === 'low') {
        const qLow = document.getElementById('q-low');
        if (qLow) qLow.checked = true;
    }

    // Init sezioni
    initPlayModeSwitches();
    await loadTrending();
    loadPlaylists();
    loadDownloads();

    // Setup audio & MediaSession events
    setupAudioEvents();
    setupMediaSession();

    // Setup search input
    $searchInput.addEventListener('input', onSearchInput);
    $searchInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const q = $searchInput.value.trim();
            if (q.length > 0) doSearch(q);
        }
    });

    if (!skipSplash) {
        $preloaderStatus.textContent = 'Pronto! 🎶';
    }

    // Attendi completamento autenticazione Simpson se presente
    await authPromise;

    // Attendi che l'audio del preloader (1.mp3, durata ~6.6s) finisca
    if (audioStarted && !audioFinished && !skipSplash) {
        await new Promise(resolve => {
            const timeout = setTimeout(resolve, 7500);
            preloaderAudio.addEventListener('ended', () => { clearTimeout(timeout); resolve(); }, { once: true });
            preloaderAudio.addEventListener('error', () => { clearTimeout(timeout); resolve(); }, { once: true });
        });
    }

    clearInterval(brandInterval);

    if (!skipSplash) {
        // Nascondi preloader con fade-out
        $preloader.style.transition = 'opacity 0.4s ease';
        $preloader.style.opacity = '0';
        setTimeout(() => {
            $preloader.style.display = 'none';
            $app.style.display = 'block';
            if (preloaderAudio) {
                preloaderAudio.pause();
                preloaderAudio.removeAttribute('src');
            }
        }, 400);
    } else {
        $preloader.style.display = 'none';
        $app.style.display = 'block';
    }
}


// ═══════════════════════════════════════════════════════════════
//  TAB NAVIGATION (Home / Playlist / Download - Context Aware)
// ═══════════════════════════════════════════════════════════════

function switchTab(tab) {
    currentTab = tab;
    
    // Update nav tabs (Desktop & Mobile)
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.mobile-nav-item').forEach(t => t.classList.remove('active'));
    const navBtn = document.getElementById(`nav-${tab}`);
    if (navBtn) navBtn.classList.add('active');
    const mobBtn = document.getElementById(`mob-nav-${tab}`);
    if (mobBtn) mobBtn.classList.add('active');
    
    // Show view
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    if (tab === 'home') {
        $viewHome.classList.add('active');
        loadTrending();
    } else if (tab === 'playlist') {
        $viewPlaylist.classList.add('active');
        loadPlaylists();
    } else if (tab === 'download') {
        $viewDownload.classList.add('active');
        loadDownloads();
    }
}

function showView(name) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.mobile-nav-item').forEach(t => t.classList.remove('active'));
    if (name === 'home') {
        $viewHome.classList.add('active');
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.getElementById('nav-home')?.classList.add('active');
        document.getElementById('mob-nav-home')?.classList.add('active');
        currentTab = 'home';
    } else if (name === 'search') {
        $viewSearch.classList.add('active');
    } else if (name === 'playlist') {
        $viewPlaylist.classList.add('active');
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.getElementById('nav-playlist')?.classList.add('active');
        document.getElementById('mob-nav-playlist')?.classList.add('active');
        currentTab = 'playlist';
    } else if (name === 'download') {
        $viewDownload.classList.add('active');
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.getElementById('nav-download')?.classList.add('active');
        document.getElementById('mob-nav-download')?.classList.add('active');
        currentTab = 'download';
    }
}


// ═══════════════════════════════════════════════════════════════
//  HOME — UNIFIED & POTENTIATED "IN TENDENZA PER TE" FEED
// ═══════════════════════════════════════════════════════════════

function getTrackThumbnail(t) {
    if (!t) return '/static/icona_app.jpg';
    if (t.thumbnail && typeof t.thumbnail === 'string' && !t.thumbnail.includes('icona_app') && !t.thumbnail.includes('tartuga')) {
        return t.thumbnail;
    }
    const id = (t.id && typeof t.id === 'string' && t.id.length === 11 && !t.id.includes('.') && !t.id.includes('/')) ? t.id :
               (t.url && typeof t.url === 'string' && t.url.includes('v=')) ? t.url.split('v=')[1].slice(0, 11) : null;
    if (id) {
        return `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
    }
    if (t.filename) {
        return `/api/offline_thumb/${encodeURIComponent(t.filename)}`;
    }
    return t.thumbnail || '/static/icona_app.jpg';
}

function handleThumbError(img, id) {
    if (id && id.length === 11 && !img.dataset.triedYt) {
        img.dataset.triedYt = '1';
        img.src = `https://i.ytimg.com/vi/${id}/mqdefault.jpg`;
    } else {
        img.src = '/static/icona_app.jpg';
    }
}

function getHistoryTracks(mode = currentMode) {
    const historyKey = mode === 'video' ? 'tortuga_history_video' : 'tortuga_history_music';
    try {
        return JSON.parse(localStorage.getItem(historyKey) || '[]');
    } catch(e) {
        return [];
    }
}

async function loadTrending() {
    renderTrendingSkeletons();
    const history = getHistoryTracks();
    const suggestedArtist = history[0]?.artist || '';
    
    try {
        const url = suggestedArtist
            ? `${API}/trending?q=${encodeURIComponent(suggestedArtist)}`
            : `${API}/trending`;
        const r = await fetch(url);
        const data = await r.json();
        const serverTracks = data.tracks || [];

        // Unifica la cronologia recente + consigliati/trend in un unico grande feed senza duplicati
        const unifiedTracks = [];
        const seenIds = new Set();

        // 1. Inserisci i brani ascoltati di recente (fino a 8) in cima
        for (const t of history.slice(0, 8)) {
            if (t && t.id && !seenIds.has(t.id)) {
                seenIds.add(t.id);
                unifiedTracks.push({
                    ...t,
                    thumbnail: getTrackThumbnail(t),
                    url: t.url || `https://www.youtube.com/watch?v=${t.id}`
                });
            }
        }

        // 2. Aggiungi i brani di tendenza e consigliati
        for (const t of serverTracks) {
            if (t && t.id && !seenIds.has(t.id)) {
                seenIds.add(t.id);
                unifiedTracks.push({
                    ...t,
                    thumbnail: getTrackThumbnail(t),
                    url: t.url || `https://www.youtube.com/watch?v=${t.id}`
                });
            }
        }

        currentTrendingTracks = unifiedTracks;
        if (unifiedTracks.length > 0) {
            $trendingList.innerHTML = unifiedTracks.map((t, i) => `
                <div class="track-card" onclick="playFromTrending(${i})">
                    <div class="track-card-img-wrap">
                        <img class="track-card-img" src="${getTrackThumbnail(t)}" alt="" loading="lazy" onerror="handleThumbError(this, '${t.id || ''}')" />
                        <span class="track-card-duration">${formatTime(t.duration)}</span>
                        <div class="track-card-play-btn">▶</div>
                    </div>
                    <div class="track-card-info">
                        <div class="track-card-title" title="${escHtml(t.title)}">${escHtml(t.title)}</div>
                        <div class="track-card-artist">${escHtml(t.artist)}</div>
                    </div>
                </div>
            `).join('');
        } else {
            $trendingList.innerHTML = '<div class="loading-placeholder">Nessun suggerimento disponibile</div>';
        }
    } catch(e) {
        console.error("Error loading trending", e);
        $trendingList.innerHTML = '<div class="loading-placeholder">Errore caricamento suggerimenti</div>';
    }
}

function saveToHistory(track) {
    if (!track || !track.id) return;
    const historyKey = currentMode === 'video' ? 'tortuga_history_video' : 'tortuga_history_music';
    try {
        let history = JSON.parse(localStorage.getItem(historyKey) || '[]');
        history = history.filter(t => t.id !== track.id);
        const trackUrl = track.url || `https://www.youtube.com/watch?v=${track.id}`;
        history.unshift({
            id: track.id,
            title: track.title || 'Sconosciuto',
            artist: track.artist || 'Artista',
            duration: track.duration || 0,
            thumbnail: getTrackThumbnail(track),
            url: trackUrl
        });
        if (history.length > 30) history = history.slice(0, 30);
        localStorage.setItem(historyKey, JSON.stringify(history));
        saveBackup(historyKey, history);
    } catch(e) {}
}


// ═══════════════════════════════════════════════════════════════
//  PLAYLIST MANAGEMENT (Context-aware based on active mode)
// ═══════════════════════════════════════════════════════════════

function getPlaylistKey(mode = currentMode) {
    return mode === 'video' ? 'tortuga_playlist_video' : 'tortuga_playlist_music';
}

function getPlaylistTracks(mode = currentMode) {
    try {
        const list = JSON.parse(localStorage.getItem(getPlaylistKey(mode)) || '[]');
        return list.map(t => ({
            ...t,
            thumbnail: getTrackThumbnail(t),
            url: t.url || (t.id ? `https://www.youtube.com/watch?v=${t.id}` : '')
        }));
    } catch(e) { return []; }
}

function savePlaylistTracks(mode, tracks) {
    try {
        const key = getPlaylistKey(mode);
        localStorage.setItem(key, JSON.stringify(tracks));
        saveBackup(key, tracks);
    } catch(e) {}
}

function prefetchStreamCache(track, mode = currentMode) {
    if (!track || !track.id) return;
    const targetUrl = track.url || `https://www.youtube.com/watch?v=${track.id}`;
    fetch(`${API}/stream?url=${encodeURIComponent(targetUrl)}&id=${encodeURIComponent(track.id)}&mode=${mode}&quality=${streamQuality}`)
        .catch(() => {});
}

function addToPlaylist() {
    if (!currentTrack || !currentTrack.id) {
        showCustomToast("Nessun brano in riproduzione");
        return;
    }
    
    const mode = currentMode;
    const tracks = getPlaylistTracks(mode);
    
    if (tracks.some(t => t.id === currentTrack.id)) {
        showCustomToast("Già nella playlist! 🎵");
        return;
    }
    
    const trackId = currentTrack.id;
    const trackUrl = currentTrack.url || `https://www.youtube.com/watch?v=${trackId}`;
    
    const newEntry = {
        id: trackId,
        title: currentTrack.title || 'Sconosciuto',
        artist: currentTrack.artist || 'Artista',
        duration: currentTrack.duration || 0,
        thumbnail: getTrackThumbnail(currentTrack),
        url: trackUrl
    };
    
    tracks.push(newEntry);
    savePlaylistTracks(mode, tracks);
    
    // Pre-cache in background per caricamento ultra-istantaneo
    prefetchStreamCache(newEntry, mode);

    showCustomToast(`Aggiunto alla ${mode === 'video' ? 'Playlist Video' : 'Playlist Musica'}! 🎵`);
    
    if (currentTab === 'playlist') loadPlaylists();
}

function removeFromPlaylist(id, event) {
    if (event) event.stopPropagation();
    
    const mode = currentMode;
    let tracks = getPlaylistTracks(mode);
    tracks = tracks.filter(t => t.id !== id);
    savePlaylistTracks(mode, tracks);
    
    showCustomToast("Rimosso dalla playlist");
    loadPlaylists();
}

function loadPlaylists() {
    const mode = currentMode;
    const tracks = getPlaylistTracks(mode);
    const $list = document.getElementById('playlist-list');
    const $title = document.getElementById('playlist-section-title');
    const $count = document.getElementById('playlist-count');
    
    if ($title) {
        $title.innerHTML = mode === 'video' 
            ? `🎬 Playlist Video <span id="playlist-count" class="section-badge">${tracks.length}</span>`
            : `🎵 Playlist Musica <span id="playlist-count" class="section-badge">${tracks.length}</span>`;
    }
    if ($count) $count.textContent = tracks.length;
    if (!$list) return;
    
    if (tracks.length === 0) {
        $list.innerHTML = `<div class="loading-placeholder">Nessun ${mode === 'video' ? 'video' : 'brano'} in playlist. Usa ➕ nel player per aggiungere.</div>`;
        return;
    }
    
    $list.innerHTML = tracks.map((t, i) => `
        <div class="track-item" onclick="playFromPlaylist(${i})" style="animation-delay: ${i * 0.02}s">
            <img class="track-item-thumb" src="${getTrackThumbnail(t)}" alt="" loading="lazy" onerror="handleThumbError(this, '${t.id || ''}')" />
            <div class="track-item-info">
                <div class="track-item-title">${escHtml(t.title)}</div>
                <div class="track-item-artist">${escHtml(t.artist)}</div>
            </div>
            <span class="track-item-dur">${formatTime(t.duration)}</span>
            <button class="offline-delete-btn" onclick="removeFromPlaylist('${t.id}', event)" title="Rimuovi">✕</button>
        </div>
    `).join('');

    // Pre-cache i primi brani della playlist in background
    tracks.slice(0, 3).forEach(t => prefetchStreamCache(t, mode));
}

function playFromPlaylist(index) {
    const tracks = getPlaylistTracks(currentMode);
    playFromList(tracks, index, 'playlist');
}


// ═══════════════════════════════════════════════════════════════
//  DOWNLOAD VIEW (Context-aware based on active mode)
// ═══════════════════════════════════════════════════════════════

let offlineMusicCache = [];
let offlineVideoCache = [];

async function loadDownloads() {
    const $list = document.getElementById('download-list');
    if (!offlineMusicCache.length && !offlineVideoCache.length && $list) {
        renderListSkeletons($list, 3);
    }
    try {
        const [musicRes, videoRes] = await Promise.all([
            fetch(`${API}/offline?mode=music`),
            fetch(`${API}/offline?mode=video`)
        ]);
        const musicData = await musicRes.json();
        const videoData = await videoRes.json();
        offlineMusicCache = musicData.tracks || [];
        offlineVideoCache = videoData.tracks || [];
    } catch(e) {
        console.error("Error loading downloads", e);
    }
    renderDownloadSection();
}

function renderDownloadSection() {
    const mode = currentMode;
    const tracks = mode === 'music' ? offlineMusicCache : offlineVideoCache;
    const $list = document.getElementById('download-list');
    const $title = document.getElementById('download-section-title');
    const $count = document.getElementById('download-count');
    
    if ($title) {
        $title.innerHTML = mode === 'video'
            ? `🎬 Video Scaricati <span id="download-count" class="section-badge">${tracks.length}</span>`
            : `🎧 Canzoni Scaricate <span id="download-count" class="section-badge">${tracks.length}</span>`;
    }
    if ($count) $count.textContent = tracks.length;
    if (!$list) return;
    
    const activeCurrentMode = Object.values(activeDownloads).filter(d => d.mode === mode);
    
    if (tracks.length === 0 && activeCurrentMode.length === 0) {
        $list.innerHTML = `<div class="loading-placeholder">Nessun ${mode === 'video' ? 'video' : 'brano'} scaricato.</div>`;
        return;
    }
    
    let html = '';
    
    // Active downloads
    for (const d of activeCurrentMode) {
        const isErr = d.status === 'error';
        html += `
            <div class="track-item ${isErr ? 'offline-error' : ''}" style="opacity: 0.7;">
                <img class="track-item-thumb" src="${getTrackThumbnail(d)}" alt="" loading="lazy" onerror="handleThumbError(this, '${d.id || ''}')" />
                <div class="track-item-info">
                    <div class="track-item-title">${escHtml(d.title)}</div>
                    <div class="track-item-artist">${isErr ? '⚠️ Errore download' : `⏳ ${d.progress || '0%'} ${d.eta || ''}`}</div>
                </div>
            </div>
        `;
    }
    
    // Completed downloads
    for (let i = 0; i < tracks.length; i++) {
        const t = tracks[i];
        html += `
            <div class="track-item" onclick="playFromDownloads(${i})" style="animation-delay: ${i * 0.02}s">
                <img class="track-item-thumb" src="${getTrackThumbnail(t)}" alt="" loading="lazy" onerror="handleThumbError(this, '${t.id || ''}')" />
                <div class="track-item-info">
                    <div class="track-item-title">${escHtml(t.title)}</div>
                    <div class="track-item-artist">${escHtml(t.artist)} • Offline ✓</div>
                </div>
                <span class="track-item-dur">${formatTime(t.duration)}</span>
                <button class="offline-delete-btn" onclick="deleteOfflineTrack('${t.id}', event)" title="Elimina">✕</button>
            </div>
        `;
    }
    
    $list.innerHTML = html;
}

function playFromDownloads(index) {
    const tracks = currentMode === 'music' ? offlineMusicCache : offlineVideoCache;
    playFromList(tracks, index, 'download');
}


// ═══════════════════════════════════════════════════════════════
//  SEARCH
// ═══════════════════════════════════════════════════════════════

function onSearchInput() {
    const q = $searchInput.value.trim();
    if (q.length === 0) {
        clearSearch();
        return;
    }
    $btnClearSearch.classList.remove('hidden');
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => doSearch(q), 500);
}

async function doSearch(query) {
    renderListSkeletons($searchResults, 6);
    showView('search');
    try {
        const r = await fetch(`${API}/search?q=${encodeURIComponent(query)}&mode=${currentMode}`);
        const data = await r.json();
        renderSearchResults(data.tracks || []);
    } catch(e) {
        $searchResults.innerHTML = '<div class="loading-placeholder">Errore di ricerca</div>';
    }
}

function clearSearch() {
    $searchInput.value = '';
    $btnClearSearch.classList.add('hidden');
    clearTimeout(searchTimeout);
    showView(currentTab);
}

function renderSearchResults(tracks) {
    currentSearchResults = tracks || [];
    if (!tracks || !tracks.length) {
        $searchResults.innerHTML = '<div class="loading-placeholder">Nessun risultato trovato</div>';
        return;
    }
    $searchResults.innerHTML = tracks.map((t, i) => `
        <div class="track-card" onclick="playFromSearch(${i})">
            <div class="track-card-img-wrap">
                <img class="track-card-img" src="${getTrackThumbnail(t)}" alt="" loading="lazy" onerror="handleThumbError(this, '${t.id || ''}')" />
                <span class="track-card-duration">${formatTime(t.duration)}</span>
                <div class="track-card-play-btn">▶</div>
            </div>
            <div class="track-card-info">
                <div class="track-card-title" title="${escHtml(t.title)}">${escHtml(t.title)}</div>
                <div class="track-card-artist">${escHtml(t.artist)}</div>
            </div>
        </div>
    `).join('');
}


// ═══════════════════════════════════════════════════════════════
//  MODE SWITCH & BLUETOOTH
// ═══════════════════════════════════════════════════════════════

function setMode(mode) {
    if (currentMode === mode) return;
    currentMode = mode;
    
    // Update Tabs UI
    document.getElementById('tab-music').classList.toggle('active', mode === 'music');
    document.getElementById('tab-video').classList.toggle('active', mode === 'video');

    // Update Sidebar Logo Icon & Accent text dynamically
    const logoIcon = document.getElementById('sidebar-logo-icon');
    const logoAccent = document.getElementById('sidebar-logo-accent');
    if (mode === 'video') {
        if (logoIcon) logoIcon.textContent = '🎬';
        if (logoAccent) {
            logoAccent.textContent = 'Video';
            logoAccent.style.color = 'var(--accent-video, #ff4757)';
            logoAccent.style.textShadow = '0 0 12px rgba(255, 71, 87, 0.6)';
        }
        document.title = 'TortugaVideo — Web & Desktop';
    } else {
        if (logoIcon) logoIcon.textContent = '🎵';
        if (logoAccent) {
            logoAccent.textContent = 'Music';
            logoAccent.style.color = '';
            logoAccent.style.textShadow = '';
        }
        document.title = 'TortugaMusic — Web & Desktop';
    }

    // Manage Video Element Visibility
    if (mode === 'video') {
        audio.style.display = 'block';
        document.getElementById('player-expanded').classList.add('video-mode');
    } else {
        audio.style.display = 'none';
        document.getElementById('player-expanded').classList.remove('video-mode');
    }

    updateExpandedModeButton();

    // Refresh context-aware views for the new mode
    clearSearch();
    loadTrending();
    if (currentTab === 'playlist') loadPlaylists();
    if (currentTab === 'download') renderDownloadSection();

    resetPlayerState();
}

function updateExpandedModeButton() {
    const switchIcon = document.getElementById('switch-icon');
    const switchLabel = document.getElementById('switch-label');
    if (currentMode === 'music') {
        if (switchIcon) switchIcon.textContent = '🎬';
        if (switchLabel) switchLabel.textContent = 'Passa a Video';
    } else {
        if (switchIcon) switchIcon.textContent = '🎵';
        if (switchLabel) switchLabel.textContent = 'Passa a Musica';
    }
}

function toggleModeFromPlayer() {
    if (!currentTrack) return;
    const newMode = currentMode === 'music' ? 'video' : 'music';
    const targetModeName = newMode === 'video' ? 'Video' : 'Music';
    const trackToTransfer = { ...currentTrack };

    const historyKey = newMode === 'video' ? 'tortuga_history_video' : 'tortuga_history_music';
    try {
        let history = JSON.parse(localStorage.getItem(historyKey) || '[]');
        history = history.filter(t => t.id !== trackToTransfer.id);
        history.unshift(trackToTransfer);
        if (history.length > 30) history = history.slice(0, 30);
        localStorage.setItem(historyKey, JSON.stringify(history));
    } catch (e) {}

    setMode(newMode);
    
    if (window.AndroidBridge && window.AndroidBridge.showToast) {
        window.AndroidBridge.showToast("Inviato a Tortuga " + targetModeName + "!");
    }
}

function openBluetooth() {
    if (window.AndroidBridge && window.AndroidBridge.openBluetoothSettings) {
        window.AndroidBridge.openBluetoothSettings();
    } else {
        showCustomToast("Apertura impostazioni Bluetooth...");
    }
}


// ═══════════════════════════════════════════════════════════════
//  MEDIA SESSION & CAR CONTROLS
// ═══════════════════════════════════════════════════════════════

function setupMediaSession() {
    if ('mediaSession' in navigator) {
        navigator.mediaSession.setActionHandler('play', () => togglePlay(true));
        navigator.mediaSession.setActionHandler('pause', () => togglePlay(false));
        navigator.mediaSession.setActionHandler('previoustrack', () => prevTrack());
        navigator.mediaSession.setActionHandler('nexttrack', () => nextTrack());
        navigator.mediaSession.setActionHandler('seekto', (details) => {
            if (details.seekTime !== undefined && audio.duration) {
                audio.currentTime = details.seekTime;
            }
        });
    }
}

function syncMediaSession(playing) {
    if (!currentTrack) return;
    const title = currentTrack.title || 'Tortuga Music';
    const artist = currentTrack.artist || 'Artista';
    const thumb = currentTrack.thumbnail || '';
    const posMs = Math.floor((audio.currentTime || 0) * 1000);
    const durMs = Math.floor((audio.duration || currentTrack.duration || 0) * 1000);

    if (window.AndroidBridge && window.AndroidBridge.updateMediaSession) {
        try {
            window.AndroidBridge.updateMediaSession(title, artist, thumb, playing, posMs, durMs);
        } catch(e) {
            console.error("Bridge updateMediaSession error:", e);
        }
    }

    if ('mediaSession' in navigator) {
        try {
            navigator.mediaSession.metadata = new MediaMetadata({
                title: title,
                artist: artist,
                album: 'Tortuga Music',
                artwork: thumb ? [{ src: thumb, sizes: '512x512', type: 'image/jpeg' }] : []
            });
            navigator.mediaSession.playbackState = playing ? 'playing' : 'paused';
        } catch(e) {}
    }
}


// ═══════════════════════════════════════════════════════════════
//  AUDIO PLAYBACK & TRACK SWITCHING
// ═══════════════════════════════════════════════════════════════

function resetPlayerState() {
    if (streamAbortController) {
        streamAbortController.abort();
        streamAbortController = null;
    }
    
    try {
        audio.pause();
        audio.removeAttribute('src');
        audio.load();
    } catch(e) {}

    isPlaying = false;
    currentTrack = null;
    
    $timeCurrent.textContent = '0:00';
    $timeTotal.textContent = '0:00';
    $seekSlider.value = 0;
    $progressFill.style.width = '0%';
    
    updatePlayButtons();
    $playerBar.classList.add('hidden');
    collapsePlayer();
    syncMediaSession(false);
}

async function playFromList(tracks, index, section = null) {
    if (!tracks || tracks.length === 0) return;
    
    const mode = section ? (sectionPlayModes[section] || 'seq') : 'seq';
    
    if (mode === 'rnd' && tracks.length > 1) {
        const selectedTrack = tracks[index] || tracks[0];
        const otherTracks = tracks.filter((_, idx) => idx !== index);
        
        // Fisher-Yates shuffle
        for (let i = otherTracks.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [otherTracks[i], otherTracks[j]] = [otherTracks[j], otherTracks[i]];
        }
        
        queue = [selectedTrack, ...otherTracks];
        queueIndex = 0;
        await playTrack(queue[0]);
    } else {
        queue = [...tracks];
        queueIndex = (index >= 0 && index < tracks.length) ? index : 0;
        await playTrack(queue[queueIndex]);
    }
}

let isNativeAudioPlaying = false;

// ─── Native Audio Playback Callbacks (from MusicService) ───
window.onNativeProgress = function(currentSec, totalSec, playing) {
    if (currentMode !== 'music') return;
    isNativeAudioPlaying = playing;
    isPlaying = playing;
    updatePlayButtons();
    if (totalSec > 0) {
        const pct = (currentSec / totalSec) * 100;
        $progressFill.style.width = Math.min(100, Math.max(0, pct)) + '%';
        $seekSlider.value = pct;
        $timeCurrent.textContent = formatTime(currentSec);
        $timeTotal.textContent = formatTime(totalSec);
    }
};

window.onNativePlaybackState = function(playing) {
    if (currentMode !== 'music') return;
    isNativeAudioPlaying = playing;
    isPlaying = playing;
    updatePlayButtons();
};

window.onNativeAudioError = async function(err) {
    console.error("[Native Audio Error]", err);
    isNativeAudioPlaying = false;

    // Auto-recovery: if stream link expired or network IP changed (403), request a fresh stream with refresh=1
    if (currentTrack && !currentTrack._hasRetriedRefresh) {
        currentTrack._hasRetriedRefresh = true;
        console.log("[Auto-Recovery] Stream error encountered. Requesting fresh stream via refresh=1...");
        showCustomToast("Ripristino flusso audio...");
        await playTrack(currentTrack, true);
        return;
    }

    // Resilient fallback to HTML5 Web Audio engine
    if (currentTrack && currentTrack.directMediaUrl) {
        console.log("[Fallback] Playing via HTML5 Web Audio engine...");
        audio.style.display = (currentMode === 'video') ? 'block' : 'none';
        audio.src = currentTrack.directMediaUrl;
        audio.load();
        audio.play().then(() => {
            isPlaying = true;
            updatePlayButtons();
            syncMediaSession(true);
        }).catch(e => {
            console.error("[HTML5 Playback Fallback Error]", e);
            isPlaying = false;
            updatePlayButtons();
        });
    } else {
        isPlaying = false;
        updatePlayButtons();
    }
};

async function playTrack(track, isRetry = false, resumeTime = 0) {
    if (!track) return;
    if (!isRetry) {
        track._hasRetriedRefresh = false;
        if (!resumeTime) track._healAttempts = 0;
    }

    if (streamAbortController) {
        streamAbortController.abort();
    }
    streamAbortController = new AbortController();

    currentTrack = track;
    saveToHistory(track);

    // Reset UI
    if (!resumeTime) {
        if ($timeCurrent) $timeCurrent.textContent = '0:00';
        if ($timeTotal) $timeTotal.textContent = formatTime(track.duration || 0);
        if ($seekSlider) $seekSlider.value = 0;
        if ($progressFill) $progressFill.style.width = '0%';
        const curEl = document.getElementById('player-time-cur');
        const totEl = document.getElementById('player-time-tot');
        if (curEl) curEl.textContent = '0:00';
        if (totEl) totEl.textContent = formatTime(track.duration || 0);
    }

    try {
        audio.pause();
        audio.removeAttribute('src');
        audio.load();
    } catch(e) {}

    updatePlayerUI(track);
    showPlayerBar();
    updateExpandedModeButton();

    document.getElementById('btn-play').textContent = '⏳';
    document.getElementById('btn-play-ex').textContent = '⏳';

    try {
        if (track.offline && track.url) {
            let fullOfflineUrl = track.url;
            if (fullOfflineUrl && !fullOfflineUrl.startsWith('http://') && !fullOfflineUrl.startsWith('https://')) {
                fullOfflineUrl = window.location.origin + (fullOfflineUrl.startsWith('/') ? '' : '/') + fullOfflineUrl;
            }
            track.directMediaUrl = fullOfflineUrl;

            if (currentMode === 'video') {
                expandPlayer();
                if (window.AndroidBridge && window.AndroidBridge.stopNativeAudio) {
                    window.AndroidBridge.stopNativeAudio();
                }
                isNativeAudioPlaying = false;
                audio.style.display = 'block';
                audio.src = fullOfflineUrl;
                audio.load();
                if (resumeTime > 0) audio.currentTime = resumeTime;
                await audio.play();
                isPlaying = true;
            } else {
                audio.pause();
                audio.removeAttribute('src');
                audio.style.display = 'none';
                if (window.AndroidBridge && window.AndroidBridge.playNativeAudio) {
                    window.AndroidBridge.playNativeAudio(fullOfflineUrl, track.title || 'Tortuga Music', track.artist || 'Artista', track.thumbnail || '', track.duration || 0);
                    isNativeAudioPlaying = true;
                    isPlaying = true;
                } else {
                    audio.src = fullOfflineUrl;
                    audio.load();
                    if (resumeTime > 0) audio.currentTime = resumeTime;
                    await audio.play();
                    isPlaying = true;
                }
            }
            updatePlayButtons();
            syncMediaSession(true);
            return;
        }

        // Risolvi sempre URL/ID validi
        let targetUrl = track.url || '';
        if (!targetUrl.startsWith('http') && track.id) {
            targetUrl = 'https://www.youtube.com/watch?v=' + track.id;
            track.url = targetUrl;
        }

        const refreshParam = isRetry ? '&refresh=1' : '';
        const streamUrl = API + '/stream?url=' + encodeURIComponent(targetUrl) + '&id=' + encodeURIComponent(track.id || '') + '&mode=' + currentMode + '&quality=' + streamQuality + refreshParam;
        const r = await fetch(streamUrl, { signal: streamAbortController.signal });
        const data = await r.json();

        if (data.error || (!data.audio_url && !data.direct_url)) {
            console.error('Stream error:', data.error);
            if (window.SelfHealingPlayer) {
                window.SelfHealingPlayer.healError('STREAM_API_ERROR', data.error);
            } else {
                showCustomToast('Errore nel flusso multimediale: ' + (data.error || 'Flusso non disponibile'));
                document.getElementById('btn-play').textContent = '▶';
                document.getElementById('btn-play-ex').textContent = '▶';
            }
            return;
        }

        if (data.thumbnail && (!currentTrack.thumbnail || currentTrack.thumbnail.length < 5)) {
            currentTrack.thumbnail = data.thumbnail;
            updatePlayerUI(currentTrack);
        }

        currentTrack.audio_url = data.audio_url;
        currentTrack.direct_url = data.direct_url || data.stream_url;
        currentTrack.user_agent = data.user_agent;

        // Seleziona la sorgente iniziale (Proxy o Direct)
        let directMediaUrl = data.audio_url || data.direct_url;
        if (track._forceDirect && data.direct_url) {
            directMediaUrl = data.direct_url;
        }
        currentTrack.directMediaUrl = directMediaUrl;

        // Traccia stima consumo banda (Direct = 0 MB server upload, Proxy = streaming size)
        if (directMediaUrl.includes('/api/audio_proxy')) {
            window.sessionProxiedBytes += (track.duration || 210) * 16000;
        } else {
            window.sessionDirectBytes += (track.duration || 210) * 16000;
        }
        if (window.updateBandwidthUI) window.updateBandwidthUI();

        if (currentMode === 'video') {
            expandPlayer();
            if (window.AndroidBridge && window.AndroidBridge.stopNativeAudio) {
                window.AndroidBridge.stopNativeAudio();
            }
            isNativeAudioPlaying = false;
            audio.style.display = 'block';
            audio.src = directMediaUrl;
            audio.load();
            if (resumeTime > 0) audio.currentTime = resumeTime;
            await audio.play();
            isPlaying = true;
        } else {
            // MUSIC MODE: HTML5 playback
            audio.pause();
            audio.removeAttribute('src');
            audio.style.display = 'none';
            if (window.AndroidBridge && window.AndroidBridge.playNativeAudio) {
                window.AndroidBridge.playNativeAudio(directMediaUrl, currentTrack.title || 'Tortuga Music', currentTrack.artist || 'Artista', currentTrack.thumbnail || '', currentTrack.duration || 0);
                isNativeAudioPlaying = true;
                isPlaying = true;
            } else {
                audio.src = directMediaUrl;
                audio.load();
                if (resumeTime > 0) audio.currentTime = resumeTime;
                await audio.play();
                isPlaying = true;
            }
        }
        
        updatePlayButtons();
        syncMediaSession(isPlaying);

    } catch(e) {
        if (e.name === 'AbortError') {
            console.log('Stream request aborted for next song');
            return;
        }
        console.error('Play error:', e);
        if (window.SelfHealingPlayer) {
            window.SelfHealingPlayer.healError('PLAY_PROMISE_REJECT', e);
        } else {
            document.getElementById('btn-play').textContent = '▶';
            document.getElementById('btn-play-ex').textContent = '▶';
        }
    }
}


function togglePlay(forceState = null) {
    if (currentMode === 'music' && isNativeAudioPlaying && window.AndroidBridge && window.AndroidBridge.toggleNativeAudio) {
        if (forceState === true) {
            window.AndroidBridge.resumeNativeAudio();
        } else if (forceState === false) {
            window.AndroidBridge.pauseNativeAudio();
        } else {
            window.AndroidBridge.toggleNativeAudio();
        }
        return;
    }

    if (!audio.src || audio.src === window.location.href) {
        if (currentTrack) playTrack(currentTrack);
        return;
    }
    
    const targetPlay = (forceState !== null) ? forceState : audio.paused;
    if (targetPlay) {
        audio.play()
            .then(() => {
                isPlaying = true;
                updatePlayButtons();
                syncMediaSession(true);
            })
            .catch(e => console.error("Play error:", e));
    } else {
        audio.pause();
        isPlaying = false;
        updatePlayButtons();
        syncMediaSession(false);
    }
}

function nextTrack() {
    if (queueIndex < queue.length - 1) {
        queueIndex++;
        playTrack(queue[queueIndex]);
    } else if (queue.length > 0) {
        queueIndex = 0;
        playTrack(queue[queueIndex]);
    }
}

function prevTrack() {
    if (queueIndex > 0) {
        queueIndex--;
        playTrack(queue[queueIndex]);
    } else if (queue.length > 0) {
        playTrack(queue[0]);
    }
}

function seekTo(val) {
    const dur = (currentTrack && currentTrack.duration) ? currentTrack.duration : (audio.duration || 0);
    if (dur > 0) {
        const targetSec = (val / 100) * dur;
        if (currentMode === 'music' && isNativeAudioPlaying && window.AndroidBridge && window.AndroidBridge.seekNativeAudio) {
            window.AndroidBridge.seekNativeAudio(targetSec);
        } else if (audio.duration) {
            audio.currentTime = targetSec;
        }
    }
}
window.seekTo = seekTo;

function seekFromProgressBar(e) {
    const bar = e.currentTarget;
    if (!bar) return;
    const rect = bar.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const width = rect.width;
    if (width > 0) {
        const pct = Math.max(0, Math.min(100, (clickX / width) * 100));
        seekTo(pct);
    }
}
window.seekFromProgressBar = seekFromProgressBar;

function setDesktopVolume(val) {
    const v = Math.max(0, Math.min(100, parseFloat(val))) / 100;
    if (audio) {
        audio.volume = v;
        audio.muted = (v === 0);
    }
    const volIcon = document.querySelector('.vol-icon');
    if (volIcon) {
        if (v === 0) volIcon.textContent = '🔇';
        else if (v < 0.5) volIcon.textContent = '🔉';
        else volIcon.textContent = '🔊';
    }
}
window.setDesktopVolume = setDesktopVolume;

let lastDesktopVolume = 1.0;
function toggleMute() {
    if (!audio) return;
    const volSlider = document.getElementById('desktop-volume');
    const volIcon = document.querySelector('.vol-icon');
    if (audio.muted || audio.volume === 0) {
        audio.muted = false;
        audio.volume = lastDesktopVolume > 0 ? lastDesktopVolume : 1.0;
        if (volSlider) volSlider.value = Math.round(audio.volume * 100);
        if (volIcon) volIcon.textContent = audio.volume < 0.5 ? '🔉' : '🔊';
    } else {
        lastDesktopVolume = audio.volume > 0 ? audio.volume : 1.0;
        audio.muted = true;
        audio.volume = 0;
        if (volSlider) volSlider.value = 0;
        if (volIcon) volIcon.textContent = '🔇';
    }
}
window.toggleMute = toggleMute;


// ═══════════════════════════════════════════════════════════════
//  AUDIO EVENT LISTENERS & KEYBOARD SHORTCUTS
// ═══════════════════════════════════════════════════════════════

function setupAudioEvents() {
    audio.addEventListener('play', () => {
        isPlaying = true;
        updatePlayButtons();
        syncMediaSession(true);
    });

    audio.addEventListener('pause', () => {
        isPlaying = false;
        updatePlayButtons();
        syncMediaSession(false);
    });

    audio.addEventListener('timeupdate', () => {
        if (!audio.duration || isNaN(audio.duration)) return;
        const pct = (audio.currentTime / audio.duration) * 100;
        $progressFill.style.width = pct + '%';
        $seekSlider.value = pct;
        $timeCurrent.textContent = formatTime(audio.currentTime);
        $timeTotal.textContent = formatTime(audio.duration);
        const curEl = document.getElementById('player-time-cur');
        const totEl = document.getElementById('player-time-tot');
        if (curEl) curEl.textContent = formatTime(audio.currentTime);
        if (totEl) totEl.textContent = formatTime(audio.duration);
    });

    audio.addEventListener('loadedmetadata', () => {
        if (audio.duration && !isNaN(audio.duration)) {
            $timeTotal.textContent = formatTime(audio.duration);
            const totEl = document.getElementById('player-time-tot');
            if (totEl) totEl.textContent = formatTime(audio.duration);
            syncMediaSession(isPlaying);
        }
    });

    audio.addEventListener('ended', () => {
        nextTrack();
    });

    audio.addEventListener('error', (e) => {
        console.error('Audio playback error:', e);
        if (window.SelfHealingPlayer) {
            window.SelfHealingPlayer.healError('AUDIO_ELEMENT_ERROR', e);
        } else {
            isPlaying = false;
            updatePlayButtons();
            syncMediaSession(false);
        }
    });

    if (window.SelfHealingPlayer) {
        window.SelfHealingPlayer.startWatchdog();
    }

    setupDesktopKeyboardShortcuts();
}

function setupDesktopKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
        const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
        if (tag === 'input' || tag === 'textarea' || document.activeElement?.isContentEditable) {
            if (e.key === 'Escape') {
                document.activeElement.blur();
            }
            return;
        }

        switch (e.key) {
            case ' ':
                e.preventDefault();
                togglePlay();
                break;
            case 'ArrowRight':
                e.preventDefault();
                if (audio && audio.duration) {
                    audio.currentTime = Math.min(audio.duration, audio.currentTime + 5);
                }
                break;
            case 'ArrowLeft':
                e.preventDefault();
                if (audio) {
                    audio.currentTime = Math.max(0, audio.currentTime - 5);
                }
                break;
            case 'ArrowUp':
                e.preventDefault();
                if (audio) {
                    const newVol = Math.min(100, Math.round((audio.volume * 100) + 5));
                    setDesktopVolume(newVol);
                    const slider = document.getElementById('desktop-volume');
                    if (slider) slider.value = newVol;
                }
                break;
            case 'ArrowDown':
                e.preventDefault();
                if (audio) {
                    const newVol = Math.max(0, Math.round((audio.volume * 100) - 5));
                    setDesktopVolume(newVol);
                    const slider = document.getElementById('desktop-volume');
                    if (slider) slider.value = newVol;
                }
                break;
            case 'm':
            case 'M':
                e.preventDefault();
                toggleMute();
                break;
            case 'f':
            case 'F':
                e.preventDefault();
                if (isExpanded) collapsePlayer();
                else expandPlayer();
                break;
            case 'Escape':
                if (isExpanded) collapsePlayer();
                const settingsModal = document.getElementById('settings-modal');
                if (settingsModal && !settingsModal.classList.contains('hidden')) {
                    toggleSettings();
                }
                break;
        }
    });
}


// ═══════════════════════════════════════════════════════════════
//  UI HELPERS & MODALS
// ═══════════════════════════════════════════════════════════════

function updatePlayerUI(track) {
    const thumbUrl = getTrackThumbnail(track);
    const pThumb = document.getElementById('player-thumb');
    if (pThumb) {
        pThumb.src = thumbUrl;
        pThumb.onerror = () => handleThumbError(pThumb, track.id || '');
    }
    document.getElementById('player-title').textContent = track.title || '---';
    document.getElementById('player-artist').textContent = track.artist || '---';

    const expThumb = document.getElementById('expanded-thumb');
    if (expThumb) {
        expThumb.src = thumbUrl;
        expThumb.onerror = () => handleThumbError(expThumb, track.id || '');
    }
    document.getElementById('expanded-title').textContent = track.title || '---';
    document.getElementById('expanded-artist').textContent = track.artist || '---';
}

function updatePlayButtons() {
    const icon = isPlaying ? '⏸' : '▶';
    document.getElementById('btn-play').textContent = icon;
    document.getElementById('btn-play-ex').textContent = icon;
}

function showPlayerBar() {
    $playerBar.classList.remove('hidden');
}

function expandPlayer() {
    if (isExpanded) return;
    isExpanded = true;
    $playerExpanded.classList.remove('hidden');
    history.pushState({ expanded: true }, '');
}

function collapsePlayer() {
    if (!isExpanded) return;
    isExpanded = false;
    $playerExpanded.classList.add('hidden');
    if (history.state && history.state.expanded) {
        history.back();
    }
}

window.addEventListener('popstate', (e) => {
    if (isExpanded) {
        isExpanded = false;
        $playerExpanded.classList.add('hidden');
    }
} );

function showCustomToast(msg) {
    if (window.AndroidBridge && window.AndroidBridge.showToast) {
        window.AndroidBridge.showToast(msg);
    } else {
        let toastEl = document.getElementById('desktop-toast');
        if (!toastEl) {
            toastEl = document.createElement('div');
            toastEl.id = 'desktop-toast';
            toastEl.className = 'generic-toast';
            document.body.appendChild(toastEl);
        }
        toastEl.textContent = msg;
        toastEl.classList.add('show');
        clearTimeout(toastEl._timer);
        toastEl._timer = setTimeout(() => {
            toastEl.classList.remove('show');
        }, 2500);
    }
}


// ═══════════════════════════════════════════════════════════════
//  SETTINGS & CACHE MANAGEMENT
// ═══════════════════════════════════════════════════════════════

async function toggleSettings(forceState) {
    const $modal = document.getElementById('settings-modal');
    if (!$modal) return;
    const bModal = document.getElementById('bandwidth-modal');
    if (bModal) bModal.classList.add('hidden');
    
    if (typeof forceState === 'boolean') {
        $modal.classList.toggle('hidden', !forceState);
    } else {
        $modal.classList.toggle('hidden');
    }
    if (!$modal.classList.contains('hidden')) {
        await refreshCacheStats();
    }
}
window.toggleSettings = toggleSettings;

async function refreshCacheStats() {
    try {
        const r = await fetch(`${API}/cache/stats`);
        const stats = await r.json();
        document.getElementById('stat-streams').textContent = stats.active_streams || 0;
        document.getElementById('stat-searches').textContent = stats.active_searches || 0;
        document.getElementById('stat-size').textContent = (stats.db_size_kb || 0) + ' KB';
    } catch(e) {}
}

async function clearCache() {
    try {
        const r = await fetch(`${API}/cache/clear`, { method: 'POST' });
        const res = await r.json();
        if (res.status === 'ok') {
            await refreshCacheStats();
            showCustomToast('Cache temporanea svuotata con successo!');
        }
    } catch(e) {
        showCustomToast('Errore durante lo svuotamento cache');
    }
}

function setQuality(val) {
    streamQuality = val;
    localStorage.setItem('stream_quality', val);
    showCustomToast(`Qualità impostata su: ${val === 'high' ? 'Massima' : 'Risparmio Dati'}`);
}


// ═══════════════════════════════════════════════════════════════
//  DOWNLOADS & OFFLINE UX
// ═══════════════════════════════════════════════════════════════

async function startDownload() {
    if (!currentTrack) {
        showCustomToast("Nessun brano in riproduzione da scaricare");
        return;
    }
    
    const track = { ...currentTrack };
    const videoId = track.id;
    
    // Smoothly close expanded player if open
    if (isExpanded) {
        collapsePlayer();
    }
    
    const $toast = document.getElementById('download-toast');
    const $title = document.getElementById('download-title');
    const $eta   = document.getElementById('download-eta');
    const $fill  = document.getElementById('download-progress-fill');
    
    if ($toast) {
        $toast.classList.remove('hidden');
        $title.textContent = `Scaricamento: ${track.title}`;
        $eta.textContent = 'Avvio...';
        $fill.style.width = '0%';
    }
    
    activeDownloads[videoId] = {
        id: videoId,
        title: track.title,
        artist: track.artist,
        mode: currentMode,
        thumbnail: track.thumbnail,
        duration: track.duration,
        progress: '0%',
        percent: 0,
        eta: 'Inizializzazione...',
        status: 'downloading'
    };
    if (currentTab === 'download') renderDownloadSection();
    showCustomToast(`📥 Download avviato: ${track.title}`);
    
    try {
        const payload = {
            id: track.id,
            title: track.title,
            artist: track.artist,
            mode: currentMode,
            thumbnail: track.thumbnail,
            duration: track.duration
        };
        
        const r = await fetch(`${API}/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await r.json();
        
        if (data.status === 'started' || data.status === 'already_downloading') {
            startPollingDownloads();
        } else if (data.error) {
            activeDownloads[videoId].status = 'error';
            activeDownloads[videoId].eta = 'Errore server';
            if (currentTab === 'download') renderDownloadSection();
        }
    } catch(e) {
        console.error('Download start error', e);
        if (activeDownloads[videoId]) {
            activeDownloads[videoId].status = 'error';
            activeDownloads[videoId].eta = 'Errore connessione';
            if (currentTab === 'download') renderDownloadSection();
        }
    }
}

function startPollingDownloads() {
    if (downloadPollInterval) return;
    
    downloadPollInterval = setInterval(async () => {
        const downloadIds = Object.keys(activeDownloads);
        if (downloadIds.length === 0) {
            clearInterval(downloadPollInterval);
            downloadPollInterval = null;
            return;
        }
        
        const $toast = document.getElementById('download-toast');
        const $title = document.getElementById('download-title');
        const $eta   = document.getElementById('download-eta');
        const $fill  = document.getElementById('download-progress-fill');
        
        for (const id of downloadIds) {
            try {
                const pr = await fetch(`${API}/download/status?id=${id}`);
                const pdata = await pr.json();
                
                if (pdata.status === 'downloading') {
                    activeDownloads[id].progress = pdata.progress || '0%';
                    activeDownloads[id].percent = pdata.percent || 0;
                    activeDownloads[id].eta = `${pdata.progress} • ${pdata.eta || ''}`;
                    activeDownloads[id].status = 'downloading';
                    
                    if ($toast && !$toast.classList.contains('hidden')) {
                        $title.textContent = `Scaricamento: ${activeDownloads[id].title}`;
                        $eta.textContent = `${pdata.progress} (${pdata.eta || ''})`;
                        $fill.style.width = pdata.progress;
                    }
                } else if (pdata.status === 'finished' || pdata.status === 'completed') {
                    delete activeDownloads[id];
                    
                    if ($toast) {
                        $title.textContent = 'Download completato!';
                        $eta.textContent = '100%';
                        $fill.style.width = '100%';
                        setTimeout(() => $toast.classList.add('hidden'), 2000);
                    }
                    showCustomToast("Download completato! Salvato offline.");
                    await loadDownloads();
                    
                } else if (pdata.status === 'error') {
                    activeDownloads[id].status = 'error';
                    activeDownloads[id].eta = 'Errore download';
                    if ($toast) {
                        $title.textContent = 'Errore durante il download';
                        $eta.textContent = 'Errore';
                        setTimeout(() => $toast.classList.add('hidden'), 2500);
                    }
                }
            } catch(e) {
                console.error("Polling error for", id, e);
            }
        }
        
        if (currentTab === 'download') {
            renderDownloadSection();
        }
    }, 1200);
}

async function deleteOfflineTrack(trackId, event) {
    if (event) {
        event.stopPropagation();
    }
    
    try {
        const r = await fetch(`${API}/offline/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: trackId })
        });
        const res = await r.json();
        if (res.status === 'ok') {
            showCustomToast("Brano rimosso dai download offline");
            await loadDownloads();
        }
    } catch(e) {
        showCustomToast("Errore durante l'eliminazione");
    }
}


// ═══════════════════════════════════════════════════════════════
//  UTILITIES
// ═══════════════════════════════════════════════════════════════

function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    seconds = Math.floor(seconds);
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
}

function escHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

// ═══════════════════════════════════════════════════════════════
//  SELF-HEALING PLAYBACK ENGINE & ANTI-STALL WATCHDOG
// ═══════════════════════════════════════════════════════════════
const SelfHealingPlayer = {
    active: true,
    maxAttempts: 4,
    healingInProgress: false,
    lastPlaybackTime: 0,
    stallCounter: 0,
    stallWatchdogTimer: null,

    async healError(errorType, errorDetail) {
        if (this.healingInProgress || !currentTrack) return;
        this.healingInProgress = true;
        currentTrack._healAttempts = (currentTrack._healAttempts || 0) + 1;
        const attempts = currentTrack._healAttempts;
        console.warn(`[Self-Healing Audio Engine] Caught error "${errorType}" (Tentativo ${attempts}/${this.maxAttempts}) sul brano:`, currentTrack.title, errorDetail);

        const resumeAt = this.lastPlaybackTime > 0 ? this.lastPlaybackTime : (audio.currentTime || 0);

        // Strategia 1: Swap Immediato tra Proxy e CDN Diretto Google
        if (attempts === 1 && currentTrack.direct_url && audio.src && audio.src.includes('/api/audio_proxy')) {
            console.log('[Self-Healing] Strategia 1: Switch da Proxy a Stream Diretto Google CDN...');
            showCustomToast('⚡ Ottimizzazione connessione diretta...');
            try {
                audio.pause();
                audio.src = currentTrack.direct_url;
                audio.currentTime = resumeAt;
                await audio.play();
                isPlaying = true;
                updatePlayButtons();
                syncMediaSession(true);
                this.healingInProgress = false;
                window.sessionDirectBytes += (currentTrack.duration || 210) * 16000;
                if (window.updateBandwidthUI) window.updateBandwidthUI();
                return;
            } catch(e) {
                console.warn('[Self-Healing] Strategia 1 CDN fallita, passo alla Strategia 2...', e);
            }
        }

        // Strategia 2: Rigenerazione Live dei Token YouTube & yt-dlp Backend (/api/stream con refresh=1)
        if (attempts <= 2) {
            console.log('[Self-Healing] Strategia 2: Richiesta nuovo stream live a yt-dlp backend...');
            showCustomToast('🔄 Rigenerazione token audio in corso...');
            try {
                await playTrack(currentTrack, true, resumeAt);
                this.healingInProgress = false;
                return;
            } catch(e) {
                console.warn('[Self-Healing] Strategia 2 stream refresh fallita...', e);
            }
        }

        // Strategia 3: Fallback a qualità a bassa latenza (quality=low) per connessioni lente o instabili
        if (attempts === 3) {
            console.log('[Self-Healing] Strategia 3: Switch a flusso leggero a bassa latenza...');
            showCustomToast('📶 Adattamento bitrate per connessione lenta...');
            try {
                const targetUrl = currentTrack.url || (currentTrack.id ? `https://www.youtube.com/watch?v=${currentTrack.id}` : '');
                const fallbackUrl = `${API}/stream?url=${encodeURIComponent(targetUrl)}&id=${encodeURIComponent(currentTrack.id || '')}&mode=${currentMode}&quality=low&refresh=1`;
                const r = await fetch(fallbackUrl);
                const d = await r.json();
                if (d && (d.audio_url || d.direct_url)) {
                    currentTrack.audio_url = d.audio_url;
                    currentTrack.direct_url = d.direct_url;
                    audio.src = d.audio_url || d.direct_url;
                    audio.currentTime = resumeAt;
                    await audio.play();
                    isPlaying = true;
                    updatePlayButtons();
                    syncMediaSession(true);
                    this.healingInProgress = false;
                    return;
                }
            } catch(e) {
                console.warn('[Self-Healing] Strategia 3 low-latency fallita...', e);
            }
        }

        // Strategia 4: Se il video YouTube è eliminato/bloccato (404/410), cerca automaticamente un video alternativo per lo stesso brano
        if (attempts >= 4) {
            console.log('[Self-Healing] Strategia 4: Video originale non disponibile. Ricerca automatica mirror alternativo...');
            showCustomToast(`🔍 Ricerca sorgente alternativa per "${currentTrack.title}"...`);
            try {
                const query = `${currentTrack.title} ${currentTrack.artist || ''}`.trim();
                const res = await fetch(`${API}/search?q=${encodeURIComponent(query)}&mode=music`);
                const searchData = await res.json();
                if (searchData && searchData.results && searchData.results.length > 0) {
                    const candidate = searchData.results.find(t => t.id && t.id !== currentTrack.id);
                    if (candidate) {
                        console.log('[Self-Healing] Mirror trovato con successo:', candidate.title, candidate.id);
                        showCustomToast('✅ Sorgente alternativa trovata! Riproduzione avviata.');
                        const origTitle = currentTrack.title;
                        const origArtist = currentTrack.artist;
                        currentTrack = { ...candidate, title: origTitle, artist: origArtist, _healAttempts: 0 };
                        await playTrack(currentTrack, false, resumeAt);
                        this.healingInProgress = false;
                        return;
                    }
                }
            } catch(e) {
                console.error('[Self-Healing] Strategia 4 mirror search fallita:', e);
            }
        }

        this.healingInProgress = false;
        showCustomToast('⚠️ Impossibile riprodurre il brano dopo tutti i tentativi di autoriparazione.');
        isPlaying = false;
        updatePlayButtons();
    },

    startWatchdog() {
        if (this.stallWatchdogTimer) clearInterval(this.stallWatchdogTimer);
        let lastPos = -1;
        this.stallWatchdogTimer = setInterval(() => {
            if (isPlaying && audio && !audio.paused && audio.src && audio.readyState >= 2) {
                const cur = audio.currentTime;
                if (cur > 0 && Math.abs(cur - lastPos) < 0.05) {
                    this.stallCounter++;
                    if (this.stallCounter >= 3) { // 3 * 1.5s = 4.5s di freeze
                        console.warn('[Self-Healing Watchdog] Freeze audio rilevato a', cur.toFixed(1), 'secondi. Sblocco automatico buffer...');
                        this.stallCounter = 0;
                        audio.currentTime = cur + 0.1;
                        setTimeout(() => {
                            if (audio.paused && isPlaying) audio.play().catch(() => {});
                        }, 300);
                    }
                } else {
                    this.stallCounter = 0;
                    lastPos = cur;
                    this.lastPlaybackTime = cur;
                }
            }
        }, 1500);
    }
};
window.SelfHealingPlayer = SelfHealingPlayer;

// ═══════════════════════════════════════════════════════════════
//  DEVICE DETECTION & ORIENTATION GUARD (PC, TABLET, MOBILE)
// ═══════════════════════════════════════════════════════════════
function detectDeviceType() {
    const ua = navigator.userAgent;
    const isTouch = navigator.maxTouchPoints > 1;
    const width = window.innerWidth;
    const height = window.innerHeight;
    const minDim = Math.min(width, height);

    let deviceType = 'desktop';
    const isMobileUA = /Android.*Mobile|iPhone|iPod|Windows Phone|BlackBerry/i.test(ua);
    const isTabletUA = /iPad|Android(?!.*Mobile)|Tablet/i.test(ua);

    if (isMobileUA || (isTouch && minDim < 580)) {
        deviceType = 'mobile';
    } else if (isTabletUA || (isTouch && minDim >= 580 && minDim <= 950)) {
        deviceType = 'tablet';
    } else {
        deviceType = 'desktop';
    }

    document.body.classList.remove('device-desktop', 'device-tablet', 'device-mobile');
    document.body.classList.add(`device-${deviceType}`);

    // Check Orientation Guard for Mobile Phone (Obbligo Orizzontale)
    const rotateOverlay = document.getElementById('rotate-device-overlay');
    if (rotateOverlay) {
        if (deviceType === 'mobile') {
            const isPortrait = window.innerHeight > window.innerWidth;
            rotateOverlay.style.display = isPortrait ? 'flex' : 'none';
        } else {
            rotateOverlay.style.display = 'none';
        }
    }
}
window.detectDeviceType = detectDeviceType;

window.requestLandscapeMode = function() {
    const el = document.documentElement;
    const rfs = el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen || el.mozRequestFullScreen;
    if (rfs) {
        rfs.call(el).then(() => {
            if (screen.orientation && screen.orientation.lock) {
                screen.orientation.lock('landscape').catch(() => {});
            }
        }).catch(() => {});
    }
};

// ═══════════════════════════════════════════════════════════════
//  BANDWIDTH MONITOR & SIMULATOR
// ═══════════════════════════════════════════════════════════════
window.sessionDirectBytes = 0;
window.sessionProxiedBytes = 0;

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0.0 MB';
    const mb = bytes / (1024 * 1024);
    if (mb < 1) return (bytes / 1024).toFixed(0) + ' KB';
    if (mb >= 1024) return (mb / 1024).toFixed(2) + ' GB';
    return mb.toFixed(1) + ' MB';
}

function updateBandwidthUI() {
    const sessionEl = document.getElementById('bw-session-val');
    const totalBytes = (window.sessionProxiedBytes || 0) + (window.sessionDirectBytes || 0);
    if (sessionEl) {
        sessionEl.textContent = formatBytes(totalBytes);
    }
}
window.updateBandwidthUI = updateBandwidthUI;

function openBandwidthModal() {
    const bModal = document.getElementById('bandwidth-modal');
    const sModal = document.getElementById('settings-modal');
    if (sModal) sModal.classList.add('hidden');
    if (bModal) {
        bModal.classList.remove('hidden');
        updateBandwidthUI();
        calculateBandwidthProjection();
    }
}
window.openBandwidthModal = openBandwidthModal;

function closeBandwidthModal() {
    const bModal = document.getElementById('bandwidth-modal');
    if (bModal) bModal.classList.add('hidden');
}
window.closeBandwidthModal = closeBandwidthModal;

function calculateBandwidthProjection() {
    const songsSlider = document.getElementById('bw-slider-songs');
    const moviesSlider = document.getElementById('bw-slider-movies');
    
    const songsPerDay = songsSlider ? parseInt(songsSlider.value, 10) : 15;
    const moviesPerWeek = moviesSlider ? parseInt(moviesSlider.value, 10) : 3;
    
    const valSongs = document.getElementById('bw-val-songs');
    const valMovies = document.getElementById('bw-val-movies');
    if (valSongs) valSongs.textContent = `${songsPerDay} brani/dì`;
    if (valMovies) valMovies.textContent = `${moviesPerWeek} titoli/sett`;
    
    // Stima consumo realistica mensile (GB):
    // ~3.5 MB per brano audio HQ * 30.5 giorni
    const songsMonthlyMB = songsPerDay * 3.5 * 30.5;
    // ~1800 MB per film / puntata TV * 4.34 settimane
    const moviesMonthlyMB = moviesPerWeek * 1800 * 4.34;
    
    const totalGB = ((songsMonthlyMB + moviesMonthlyMB) / 1024).toFixed(1);
    
    const resTotal = document.getElementById('bw-res-total');
    const resSpeed = document.getElementById('bw-res-speed');
    
    if (resTotal) resTotal.textContent = `~ ${totalGB} GB / mese`;
    
    let speedText = "Min. 5 - 10 Mbps (ADSL o 4G standard)";
    if (moviesPerWeek > 8) {
        speedText = "Min. 15 - 30 Mbps (Fibra / 5G consigliata)";
    }
    if (resSpeed) resSpeed.textContent = speedText;
}
window.calculateBandwidthProjection = calculateBandwidthProjection;

// Global Escape Key per chiudere i modali
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const sModal = document.getElementById('settings-modal');
        const bModal = document.getElementById('bandwidth-modal');
        if (sModal && !sModal.classList.contains('hidden')) sModal.classList.add('hidden');
        if (bModal && !bModal.classList.contains('hidden')) bModal.classList.add('hidden');
    }
});
