/* ═══════════════════════════════════════════════════════════════
   Tortuga Music v2.2 — Application Logic (app.js)
   Handles: Unified Home Feed, Context-Aware Playlists & Downloads,
   Permanent Cache, Ultra-Fluid Playback, Foreground Service
   ═══════════════════════════════════════════════════════════════ */

const API = 'http://127.0.0.1:5000/api';
const audio = document.getElementById('audio-player');

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
        
        for (const [key, val] of Object.entries(backup)) {
            const currentVal = localStorage.getItem(key);
            if (!currentVal || currentVal === '[]' || currentVal === '{}' || currentVal === 'null') {
                const strVal = (typeof val === 'string') ? val : JSON.stringify(val);
                localStorage.setItem(key, strVal);
                console.log(`[Backup Restored] ${key}`);
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
    // Ensure Portrait mode for Tortuga Music
    if (window.AndroidBridge && window.AndroidBridge.setOrientation) {
        window.AndroidBridge.setOrientation('portrait');
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

    // Avvia l'audio del preloader (3.mp3) solo se non stiamo tornando da TV
    const preloaderAudio = document.getElementById('preloader-audio');
    let audioFinished = false;
    let audioStarted = false;

    if (preloaderAudio && !skipSplash) {
        preloaderAudio.volume = 1.0;
        preloaderAudio.addEventListener('ended', () => { audioFinished = true; }, { once: true });
        preloaderAudio.addEventListener('error', () => { audioFinished = true; }, { once: true });
        try {
            await preloaderAudio.play();
            audioStarted = true;
        } catch(e) {
            console.warn('Preloader audio autoplay bloccato:', e);
            audioFinished = true;
        }
    } else {
        audioFinished = true;
    }

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
    if (expContainer && !expContainer.contains(audio)) {
        expContainer.appendChild(audio);
    }
    audio.style.position = 'absolute';
    audio.style.top = '0';
    audio.style.left = '0';
    audio.style.width = '100%';
    audio.style.height = '100%';
    audio.style.objectFit = 'contain';
    audio.style.zIndex = '5';

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

    // Attendi che l'audio del preloader finisca con timeout di sicurezza (max 2.5s)
    if (audioStarted && !audioFinished && !skipSplash) {
        await new Promise(resolve => {
            const timeout = setTimeout(resolve, 2500);
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
    
    // Update nav tabs
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    const navBtn = document.getElementById(`nav-${tab}`);
    if (navBtn) navBtn.classList.add('active');
    
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
    if (name === 'home') {
        $viewHome.classList.add('active');
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.getElementById('nav-home')?.classList.add('active');
        currentTab = 'home';
    } else if (name === 'search') {
        $viewSearch.classList.add('active');
    } else if (name === 'playlist') {
        $viewPlaylist.classList.add('active');
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.getElementById('nav-playlist')?.classList.add('active');
        currentTab = 'playlist';
    } else if (name === 'download') {
        $viewDownload.classList.add('active');
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.getElementById('nav-download')?.classList.add('active');
        currentTab = 'download';
    }
}


// ═══════════════════════════════════════════════════════════════
//  HOME — UNIFIED & POTENTIATED "IN TENDENZA PER TE" FEED
// ═══════════════════════════════════════════════════════════════

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
                    url: t.url || `https://www.youtube.com/watch?v=${t.id}`
                });
            }
        }

        currentTrendingTracks = unifiedTracks;
        if (unifiedTracks.length > 0) {
            $trendingList.innerHTML = unifiedTracks.map((t, i) => `
                <div class="track-card" onclick="playFromTrending(${i})">
                    <img class="track-card-img" src="${t.thumbnail || '/static/icona_app.jpg'}" alt="" loading="lazy" onerror="this.style.background='var(--bg-elevated)'" />
                    <span class="track-card-duration">${formatTime(t.duration)}</span>
                    <div class="track-card-info">
                        <div class="track-card-title">${escHtml(t.title)}</div>
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
            thumbnail: track.thumbnail || '',
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
        thumbnail: currentTrack.thumbnail || '',
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
            <img class="track-item-thumb" src="${t.thumbnail || '/static/icona_app.jpg'}" alt="" loading="lazy" onerror="this.style.background='var(--bg-elevated)'" />
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
                <img class="track-item-thumb" src="${d.thumbnail || '/static/icona_app.jpg'}" alt="" loading="lazy" />
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
                <img class="track-item-thumb" src="${t.thumbnail || '/static/icona_app.jpg'}" alt="" loading="lazy" onerror="this.style.background='var(--bg-elevated)'" />
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
        <div class="track-item" onclick="playFromSearch(${i})" style="animation-delay: ${i * 0.02}s">
            <img class="track-item-thumb" src="${t.thumbnail || '/static/icona_app.jpg'}" alt="" loading="lazy" onerror="this.style.background='var(--bg-elevated)'" />
            <div class="track-item-info">
                <div class="track-item-title">${escHtml(t.title)}</div>
                <div class="track-item-artist">${escHtml(t.artist)}</div>
            </div>
            <span class="track-item-dur">${formatTime(t.duration)}</span>
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

async function playTrack(track, isRetry = false) {
    if (!track) return;
    if (!isRetry) {
        track._hasRetriedRefresh = false;
    }

    if (streamAbortController) {
        streamAbortController.abort();
    }
    streamAbortController = new AbortController();

    currentTrack = track;
    saveToHistory(track);

    // Reset UI
    $timeCurrent.textContent = '0:00';
    $timeTotal.textContent = formatTime(track.duration || 0);
    $seekSlider.value = 0;
    $progressFill.style.width = '0%';

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
                fullOfflineUrl = `http://127.0.0.1:5000${fullOfflineUrl.startsWith('/') ? '' : '/'}${fullOfflineUrl}`;
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
            targetUrl = `https://www.youtube.com/watch?v=${track.id}`;
            track.url = targetUrl;
        }

        const refreshParam = isRetry ? '&refresh=1' : '';
        const streamUrl = `${API}/stream?url=${encodeURIComponent(targetUrl)}&id=${encodeURIComponent(track.id || '')}&mode=${currentMode}&quality=${streamQuality}${refreshParam}`;
        const r = await fetch(streamUrl, { signal: streamAbortController.signal });
        const data = await r.json();

        if (data.error || !data.audio_url) {
            if (!isRetry) {
                console.warn('First stream attempt failed, trying fresh fallback extraction...');
                await playTrack(track, true);
                return;
            }
            console.error('Stream error:', data.error);
            showCustomToast('Errore nel flusso multimediale: ' + (data.error || 'Flusso non disponibile'));
            document.getElementById('btn-play').textContent = '▶';
            document.getElementById('btn-play-ex').textContent = '▶';
            return;
        }

        if (data.thumbnail && (!currentTrack.thumbnail || currentTrack.thumbnail.length < 5)) {
            currentTrack.thumbnail = data.thumbnail;
            updatePlayerUI(currentTrack);
        }

        const directMediaUrl = data.audio_url;
        currentTrack.directMediaUrl = directMediaUrl;

        if (currentMode === 'video') {
            expandPlayer();
            if (window.AndroidBridge && window.AndroidBridge.stopNativeAudio) {
                window.AndroidBridge.stopNativeAudio();
            }
            isNativeAudioPlaying = false;
            audio.style.display = 'block';
            audio.src = directMediaUrl;
            audio.load();
            await audio.play();
            isPlaying = true;
        } else {
            // MUSIC MODE: Play in background native service with HTML5 fallback
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
        document.getElementById('btn-play').textContent = '▶';
        document.getElementById('btn-play-ex').textContent = '▶';
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


// ═══════════════════════════════════════════════════════════════
//  AUDIO EVENT LISTENERS
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
    });

    audio.addEventListener('loadedmetadata', () => {
        if (audio.duration && !isNaN(audio.duration)) {
            $timeTotal.textContent = formatTime(audio.duration);
            syncMediaSession(isPlaying);
        }
    });

    audio.addEventListener('ended', () => {
        nextTrack();
    });

    audio.addEventListener('error', (e) => {
        console.error('Audio playback error:', e);
        isPlaying = false;
        updatePlayButtons();
        syncMediaSession(false);
    });
}


// ═══════════════════════════════════════════════════════════════
//  UI HELPERS & MODALS
// ═══════════════════════════════════════════════════════════════

function updatePlayerUI(track) {
    const thumbUrl = track.thumbnail || '/static/icona_app.jpg';
    document.getElementById('player-thumb').src = thumbUrl;
    document.getElementById('player-title').textContent = track.title || '---';
    document.getElementById('player-artist').textContent = track.artist || '---';

    document.getElementById('expanded-thumb').src = thumbUrl;
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
    document.getElementById('content').style.paddingBottom = 'calc(var(--player-height) + var(--nav-height) + 24px)';
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
});

function showCustomToast(msg) {
    if (window.AndroidBridge && window.AndroidBridge.showToast) {
        window.AndroidBridge.showToast(msg);
    } else {
        console.log("[Toast]", msg);
    }
}


// ═══════════════════════════════════════════════════════════════
//  SETTINGS & CACHE MANAGEMENT
// ═══════════════════════════════════════════════════════════════

async function toggleSettings() {
    const $modal = document.getElementById('settings-modal');
    $modal.classList.toggle('hidden');
    if (!$modal.classList.contains('hidden')) {
        await refreshCacheStats();
    }
}

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
                } else if (pdata.status === 'finished') {
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
