
/**
 * TortugaTV — Film, Serie TV & Anime Dashboard
 * Rich homepage with genre rows, hero billboard, IPTV live and offline downloads
 */

// Set screen orientation to Landscape for Tortuga TV
if (typeof AndroidBridge !== "undefined" && AndroidBridge.setOrientation) {
    AndroidBridge.setOrientation('landscape');
}

window.goToMusicApp = function() {
    try {
        sessionStorage.setItem('tortuga_skip_splash', '1');
    } catch(e) {}
    if (typeof AndroidBridge !== "undefined" && AndroidBridge.setOrientation) {
        AndroidBridge.setOrientation('portrait');
    }
    location.href = '/';
};

// ═══════════════════════════════════════════════════════════════════
// Device Detection
// ═══════════════════════════════════════════════════════════════════
window._isTV = true;
if (typeof AndroidBridge !== "undefined" && AndroidBridge.isTV) {
    window._isTV = AndroidBridge.isTV();
}
if (!window._isTV) {
    document.documentElement.classList.add("phone-mode");
}

// ═══════════════════════════════════════════════════════════════════
// Router
// ═══════════════════════════════════════════════════════════════════

const router = {
    currentView: null,
    currentData: null,

    navigate(view, data = null, push = true) {
        this.currentView = view;
        this.currentData = data;
        if (push) history.pushState({ view, data }, "", "");

        // Update nav links
        document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
        const activeLink = document.querySelector(`.nav-link[data-view="${view}"]`);
        if (activeLink) activeLink.classList.add("active");

        const app = document.getElementById("app");

        switch (view) {
            case "home": renderHome(app); break;
            case "search": renderSearchResults(app, data); break;
            case "detail": renderDetail(app, data); break;
            case "filtered": renderFiltered(app, data); break;
            case "iptv": renderIptv(app, data); break;
            default: renderHome(app);
        }

        window.scrollTo(0, 0);
    },
};

// ═══════════════════════════════════════════════════════════════════
// API
// ═══════════════════════════════════════════════════════════════════

async function apiHomepage() {
    const r = await fetch("/api/homepage");
    return r.json();
}

async function apiSearch(query, forceProvider = null) {
    let provider = forceProvider || "all";
    // When inside the Anime section, search only AnimeUnity
    if (!forceProvider && router.currentView === "filtered" && typeof currentExploreType !== "undefined" && currentExploreType === "anime") {
        provider = "animeunity";
    }
    const r = await fetch(`/api/search?q=${encodeURIComponent(query)}&provider=${provider}`);
    return r.json();
}

async function apiGenre(genreName) {
    const r = await fetch(`/api/genre?name=${encodeURIComponent(genreName)}`);
    return r.json();
}

async function apiMedia(id, slug, provider) {
    const r = await fetch(`/api/media?id=${id}&slug=${slug}&provider=${provider}`);
    return r.json();
}

async function apiEpisode(mediaId, slug, episodeId, provider) {
    const ua = encodeURIComponent(navigator.userAgent);
    const r = await fetch(`/api/episode?id=${mediaId}&slug=${slug}&episode_id=${episodeId}&provider=${provider}&ua=${ua}`);
    return r.json();
}

// ═══════════════════════════════════════════════════════════════════
// Home View
// ═══════════════════════════════════════════════════════════════════

let _homepageCache = null;

async function renderHome(container) {
    // Navbar scroll behavior
    window.addEventListener("scroll", handleNavScroll);
    startDownloadMonitoring();
    handleNavScroll();

    container.innerHTML = `<div class="loading" style="padding-top:30vh"><div class="spinner"></div></div>`;

    try {
        if (!_homepageCache) {
            _homepageCache = await apiHomepage();
        }
        const data = _homepageCache;
        if (data.error) throw new Error(data.error);

        const hero = data.hero;
        const sliders = data.sliders || [];
        const genres = data.genres || [];

        // Build hero
        let heroHtml = "";
        if (hero) {
            heroHtml = `
                <div class="hero-billboard" style="background-image: url('${esc(hdImage(hero.background || hero.image))}')">
                    <div class="hero-content">
                        <div class="hero-badge">${hero.type === "movie" ? "Film" : "Serie TV"}</div>
                        <h1 class="hero-title">${esc(hero.title)}</h1>
                        <div class="hero-actions">
                            <button class="btn btn-play" onclick="openTitle(${hero.id}, '${esc(hero.slug)}')">
                                ▶ Riproduci
                            </button>
                            <button class="btn btn-info" onclick="openTitle(${hero.id}, '${esc(hero.slug)}')">
                                ⓘ Altre info
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }

        // Build slider rows
        let rowsHtml = "";
        for (const sl of sliders) {
            if (sl.label && sl.label.includes("Top 10")) {
                rowsHtml += buildTop10Row(sl.label, sl.titles);
            } else {
                rowsHtml += buildPosterRow(sl.label, sl.titles);
            }
        }

        // Offline downloaded & downloading files
        let offlineHtml = "";
        try {
            offlineHtml = await buildOfflineRowHtml();
        } catch (e) { console.error("Offline UI error", e); }

        // Watch history
        const history = getHistory();
        if (history.length > 0) {
            rowsHtml = buildPosterRow("Visti di Recente", history) + rowsHtml;
        }
        
        rowsHtml = offlineHtml + rowsHtml;

        // Genre chips
        let genreHtml = "";
        if (genres.length > 0) {
            const topGenres = genres.filter(g =>
                ["Azione", "Commedia", "Dramma", "Horror", "Thriller", "Fantasy", "Fantascienza", "Crime", "Avventura", "Famiglia", "Animazione", "Romance"].includes(g.name)
            );
            genreHtml = `
                <div class="row-section">
                    <div class="row-title">Esplora per Genere</div>
                    <div class="genre-chips">
                        ${topGenres.map(g => `
                            <div class="genre-chip" tabindex="0" onclick="loadGenre(${g.id}, '${esc(g.name)}', this)">${esc(g.name)}</div>
                        `).join("")}
                    </div>
                </div>
            `;
        }

        container.innerHTML = `
            ${heroHtml}
            <div class="main-content">
                ${rowsHtml}
                ${genreHtml}
                <div id="genre-rows"></div>
            </div>
        `;

        // Preload some genres for richer content
        preloadGenres(genres);

    } catch (err) {
        container.innerHTML = `<div class="loading"><p>Errore: ${err.message}</p></div>`;
    }
}

async function preloadGenres(genres) {
    const interestingIds = [];
    for (const g of genres) {
        if (["Azione", "Commedia", "Horror", "Thriller", "Fantasy", "Crime"].includes(g.name)) {
            interestingIds.push({ id: g.id, name: g.name });
        }
    }

    const container = document.getElementById("genre-rows");
    if (!container) return;

    for (const g of interestingIds) {
        try {
            const res = await apiGenre(g.name);
            if (res.titles && res.titles.length > 0) {
                container.insertAdjacentHTML("beforeend", buildPosterRow(g.name, res.titles));
            }
        } catch (e) {
            // ignore
        }
    }
}

async function loadGenre(genreId, genreName, chipEl) {
    const container = document.getElementById("genre-rows");
    if (!container) return;

    // Check if already loaded
    if (container.querySelector(`[data-genre-id="${genreId}"]`)) {
        container.querySelector(`[data-genre-id="${genreId}"]`).scrollIntoView({ behavior: "smooth" });
        return;
    }

    // Highlight chip
    document.querySelectorAll(".genre-chip").forEach(c => c.classList.remove("active"));
    if (chipEl) chipEl.classList.add("active");

    try {
        showToast(`Caricamento ${genreName}...`, "success");
        const res = await apiGenre(genreName);
        if (res.titles && res.titles.length > 0) {
            const rowHtml = `<div data-genre-id="${genreId}">${buildPosterRow(genreName, res.titles)}</div>`;
            container.insertAdjacentHTML("afterbegin", rowHtml);
            container.querySelector(`[data-genre-id="${genreId}"]`).scrollIntoView({ behavior: "smooth" });
        } else {
            showToast(`Nessun titolo trovato per ${genreName}`, "error");
        }
    } catch (e) {
        showToast("Errore caricamento genere", "error");
    }
}

// ═══════════════════════════════════════════════════════════════════
// Row Builders
// ═══════════════════════════════════════════════════════════════════

let _rowCounter = 0;

function scrollRow(rowId, direction) {
    const el = document.getElementById(rowId);
    if (!el) return;
    const scrollAmount = el.clientWidth * 0.75;
    el.scrollBy({ left: direction * scrollAmount, behavior: 'smooth' });
}

function buildPosterRow(title, items) {
    if (!items || items.length === 0) return "";
    const rowId = `row-${_rowCounter++}`;
    const cards = items.map(item => `
        <button class="poster-card" tabindex="0" onclick="openTitle(${item.id}, '${esc(item.slug)}', '${item.provider || "streamingcommunity"}')">
            <div class="poster-img-wrap">
                <img class="poster-img" src="${esc(item.image)}" alt="${esc(item.title)}" loading="lazy"
                     onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 300%22><rect fill=%22%231a1a22%22 width=%22200%22 height=%22300%22/><text x=%22100%22 y=%22150%22 fill=%22%23444%22 font-size=%2240%22 text-anchor=%22middle%22>🎬</text></svg>'">
                <div class="poster-type">${item.type === "movie" ? "Film" : "Serie"}</div>
                ${item.score ? `<div class="poster-score">★ ${item.score}</div>` : ""}
                <div class="poster-overlay">
                    <div class="poster-play">▶</div>
                </div>
            </div>
            <div class="poster-title">${esc(item.title)}</div>
        </button>
    `).join("");

    return `
        <div class="row-section">
            <div class="row-title">${esc(title)} <span class="count-badge">${items.length}</span></div>
            <div class="row-scroll-container">
                <button class="row-arrow row-arrow-left" onclick="scrollRow('${rowId}', -1)" aria-label="Scorri a sinistra">‹</button>
                <div class="row-scroll" id="${rowId}">${cards}</div>
                <button class="row-arrow row-arrow-right" onclick="scrollRow('${rowId}', 1)" aria-label="Scorri a destra">›</button>
            </div>
        </div>
    `;
}

function buildTop10Row(title, items) {
    if (!items || items.length === 0) return "";
    const rowId = `row-${_rowCounter++}`;
    const cards = items.slice(0, 10).map((item, i) => `
        <button class="top10-card" tabindex="0" onclick="openTitle(${item.id}, '${esc(item.slug)}', '${item.provider || "streamingcommunity"}')">
            <div class="top10-number">${i + 1}</div>
            <div class="top10-poster">
                <img src="${esc(item.image)}" alt="${esc(item.title)}" loading="lazy">
            </div>
        </button>
    `).join("");

    return `
        <div class="row-section">
            <div class="row-title">${esc(title)}</div>
            <div class="row-scroll-container">
                <button class="row-arrow row-arrow-left" onclick="scrollRow('${rowId}', -1)" aria-label="Scorri a sinistra">‹</button>
                <div class="row-scroll" id="${rowId}">${cards}</div>
                <button class="row-arrow row-arrow-right" onclick="scrollRow('${rowId}', 1)" aria-label="Scorri a destra">›</button>
            </div>
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════════════
// Filter by type (Film / Serie TV)
// ═══════════════════════════════════════════════════════════════════

// Global observer and loading state for infinite scroll
let currentExplorePage = 1;
let currentExploreType = "";
let isExploreLoading = false;
let exploreHasMore = true;

async function filterByType(type) {
    const label = type === "movie" ? "Film" : "Serie TV";
    currentExplorePage = 1;
    currentExploreType = type;
    exploreHasMore = true;

    const appContainer = document.getElementById("app");
    document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
    renderFiltered(appContainer, { type, label, titles: [], loading: true });

    try {
        const r = await fetch(`/api/explore?type=${type}&page=1`);
        const data = await r.json();
        exploreHasMore = data.has_more;
        router.navigate("filtered", { type, label, titles: data.titles || [], loading: false }, true);
    } catch (e) {
        showToast("Errore caricamento", "error");
        router.navigate("filtered", { type, label, titles: [], error: e.message, loading: false }, true);
    }
}

async function loadAnimeSection() {
    currentExplorePage = 1;
    currentExploreType = "anime";
    exploreHasMore = true;

    const appContainer = document.getElementById("app");
    document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
    renderFiltered(appContainer, { type: "anime", label: "Anime", titles: [], loading: true });

    try {
        const r = await fetch(`/api/explore?type=anime&page=1`);
        const data = await r.json();
        exploreHasMore = data.has_more;

        const au_r = await fetch("/api/search?q=%20&provider=animeunity");
        const au_data = await au_r.json();

        const allTitles = [...(au_data.results || []), ...(data.titles || [])];
        const seen = new Set();
        const uniqueTitles = allTitles.filter(t => {
            if (seen.has(t.id)) return false;
            seen.add(t.id);
            return true;
        });

        router.navigate("filtered", { type: "anime", label: "Anime", titles: uniqueTitles, loading: false }, true);
    } catch (e) {
        showToast("Errore caricamento anime", "error");
        router.navigate("filtered", { type: "anime", label: "Anime", titles: [], error: e.message, loading: false }, true);
    }
}

function renderFiltered(container, data) {
    if (!data) return;
    window.removeEventListener("scroll", handleNavScroll);
    document.getElementById("navbar").classList.add("scrolled");

    if (data.loading && (!data.titles || data.titles.length === 0)) {
        container.innerHTML = `<div class="search-view"><h2 style="font-size:24px; font-weight:700; margin-bottom:24px;">${esc(data.label)}</h2><div class="loading"><div class="spinner"></div></div></div>`;
        return;
    }

    if (data.error) {
        container.innerHTML = `<div class="search-view"><p>Errore: ${esc(data.error)}</p></div>`;
        return;
    }

    if (!data.titles || data.titles.length === 0) {
        container.innerHTML = `
            <div class="search-view" style="text-align:center">
                <h2 style="font-size:24px; font-weight:700; margin-bottom:24px;">${esc(data.label)}</h2>
                <p style="color:var(--text-secondary)">Nessun titolo trovato.</p>
            </div>
        `;
        return;
    }

    const buildCards = (titles) => titles.map(item => `
        <button class="poster-card" tabindex="0" onclick="openTitle(${item.id}, '${esc(item.slug)}', '${item.provider || "streamingcommunity"}')">
            <div class="poster-img-wrap">
                <img class="poster-img" src="${esc(item.image)}" alt="${esc(item.title)}" loading="lazy" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 300%22><rect fill=%22%231a1a22%22 width=%22200%22 height=%22300%22/><text x=%22100%22 y=%22150%22 fill=%22%23444%22 font-size=%2240%22 text-anchor=%22middle%22>🎬</text></svg>'">
                <div class="poster-type">${item.type === "movie" ? "Film" : item.type === "tv" ? "Serie" : item.type || ""}</div>
                ${item.score ? `<div class="poster-score">★ ${item.score}</div>` : ""}
                <div class="poster-overlay"><div class="poster-play">▶</div></div>
            </div>
            <div class="poster-title">${esc(item.title)}</div>
        </button>
    `).join("");

    container.innerHTML = `
        <div class="search-view">
            <h2 style="font-size:24px; font-weight:700; margin-bottom:24px;">${esc(data.label)} <span style="color:var(--text-muted); font-size:14px;" id="filtered-count">(${data.titles.length})</span></h2>
            <div class="results-grid" id="filtered-grid">${buildCards(data.titles)}</div>
            <div id="infinite-scroll-trigger" style="height: 50px; display: flex; justify-content: center; align-items: center; margin-top: 20px;">
                ${exploreHasMore ? '<div class="spinner" style="width:30px;height:30px;border-width:3px;"></div>' : ''}
            </div>
        </div>
    `;

    if (exploreHasMore) {
        const trigger = document.getElementById("infinite-scroll-trigger");
        const observer = new IntersectionObserver(async (entries) => {
            if (entries[0].isIntersecting && !isExploreLoading && exploreHasMore) {
                isExploreLoading = true;
                currentExplorePage++;
                try {
                    const r = await fetch(`/api/explore?type=${currentExploreType}&page=${currentExplorePage}`);
                    const newData = await r.json();
                    exploreHasMore = newData.has_more;

                    if (newData.titles && newData.titles.length > 0) {
                        router.currentData.titles = [...router.currentData.titles, ...newData.titles];
                        history.replaceState({ view: "filtered", data: router.currentData }, "", "");

                        document.getElementById("filtered-grid").insertAdjacentHTML("beforeend", buildCards(newData.titles));
                        document.getElementById("filtered-count").textContent = `(${router.currentData.titles.length})`;
                    }

                    if (!exploreHasMore) {
                        trigger.innerHTML = "";
                        observer.disconnect();
                    }
                } catch (e) {
                    console.error("Infinite scroll error:", e);
                }
                isExploreLoading = false;
            }
        }, { rootMargin: "200px" });
        observer.observe(trigger);
    }
}

// ═══════════════════════════════════════════════════════════════════
// Search
// ═══════════════════════════════════════════════════════════════════

async function performSearch(query) {
    const appContainer = document.getElementById("app");
    document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
    renderSearchResults(appContainer, { query, loading: true });

    try {
        const data = await apiSearch(query);
        router.navigate("search", { query, results: data.results || [], suggestion: data.suggestion, loading: false }, true);
    } catch (err) {
        router.navigate("search", { query, error: err.message, loading: false }, true);
    }
}

function renderSearchResults(container, data) {
    if (!data) return;
    window.removeEventListener("scroll", handleNavScroll);
    document.getElementById("navbar").classList.add("scrolled");

    if (data.loading) {
        container.innerHTML = `<div class="search-view"><div class="loading"><div class="spinner"></div></div></div>`;
        return;
    }

    if (data.error) {
        container.innerHTML = `<div class="search-view"><p>Errore: ${esc(data.error)}</p></div>`;
        return;
    }

    if (!data.results || data.results.length === 0) {
        let suggestion = "";
        if (data.suggestion) {
            suggestion = `<p style="margin-top:16px">Forse cercavi: <a href="javascript:void(0)" onclick="performSearch('${esc(data.suggestion)}')" style="color:var(--accent-pink)">${esc(data.suggestion)}</a>?</p>`;
        }
        container.innerHTML = `
            <div class="search-view" style="text-align:center">
                <h2 style="font-size:22px; margin-bottom:10px;">Nessun risultato</h2>
                <p style="color:var(--text-secondary)">Nessun titolo trovato per "${esc(data.query)}"</p>
                ${suggestion}
            </div>
        `;
        return;
    }

    const cards = data.results.map(item => {
        let typeLabel = item.type === "movie" ? "Film" : item.type === "tv" ? "Serie" : item.type || "";
        if (item.provider === "animeunity") typeLabel = "Anime";
        return `
        <button class="poster-card" tabindex="0" onclick="openTitle(${item.id}, '${esc(item.slug)}', '${item.provider || "streamingcommunity"}')">
            <div class="poster-img-wrap">
                <img class="poster-img" src="${esc(item.image)}" alt="${esc(item.title)}" loading="lazy">
                <div class="poster-type">${typeLabel}</div>
                ${item.score ? `<div class="poster-score">★ ${item.score}</div>` : ""}
                <div class="poster-overlay"><div class="poster-play">▶</div></div>
            </div>
            <div class="poster-title">${esc(item.title)}</div>
        </button>`;
    }).join("");

    container.innerHTML = `
        <div class="search-view">
            <h2 style="font-size:22px; font-weight:700; margin-bottom:24px;">
                Risultati per "${esc(data.query)}" <span style="color:var(--text-muted); font-size:14px;">(${data.results.length})</span>
            </h2>
            <div class="results-grid">${cards}</div>
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════════════
// Detail View
// ═══════════════════════════════════════════════════════════════════

async function openTitle(id, slug, provider = "streamingcommunity") {
    const appContainer = document.getElementById("app");
    document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
    renderDetail(appContainer, { loading: true });

    try {
        const data = await apiMedia(id, slug, provider);
        if (data.error) throw new Error(data.error);
        data.provider = provider;
        saveHistory(id, slug, data);

        // ── Smart Cache: detect new episodes/seasons ──
        const cacheKey = `tortuga_cache_${provider}_${id}`;
        try {
            const oldRaw = localStorage.getItem(cacheKey);
            if (oldRaw && data.type === "tv") {
                const old = JSON.parse(oldRaw);
                const oldSeasonCount = (old.seasons || []).length;
                const newSeasonCount = (data.seasons || []).length;

                if (newSeasonCount > oldSeasonCount) {
                    showToast(`🆕 Nuova stagione disponibile per "${data.title}"!`, "success");
                } else {
                    // Check for new episodes in the last season
                    const oldLast = (old.seasons || []).slice(-1)[0];
                    const newLast = (data.seasons || []).slice(-1)[0];
                    if (oldLast && newLast && newLast.number === oldLast.number) {
                        const oldEpCount = (oldLast.episodes || []).length;
                        const newEpCount = (newLast.episodes || []).length;
                        if (newEpCount > oldEpCount) {
                            showToast(`🆕 ${newEpCount - oldEpCount} nuovi episodi per "${data.title}"!`, "success");
                        }
                    }
                }
            }
            // Save updated cache
            localStorage.setItem(cacheKey, JSON.stringify({
                title: data.title,
                type: data.type,
                seasons: (data.seasons || []).map(s => ({
                    number: s.number,
                    episodes: (s.episodes || []).map(e => ({ id: e.id, number: e.number }))
                })),
                updated: Date.now()
            }));
        } catch (cacheErr) { /* ignore cache errors */ }

        router.navigate("detail", { id, slug, ...data, loading: false }, true);
    } catch (err) {
        showToast("Errore: " + err.message, "error");
        router.navigate("detail", { id, slug, provider, error: err.message, loading: false }, true);
    }
}

function renderDetail(container, data) {
    if (!data) return;
    window.removeEventListener("scroll", handleNavScroll);
    document.getElementById("navbar").classList.add("scrolled");

    if (data.loading) {
        container.innerHTML = `<div class="detail-view"><div class="loading"><div class="spinner"></div></div></div>`;
        return;
    }

    if (data.error) {
        container.innerHTML = `
            <div class="detail-view" style="padding: 100px 4%;">
                <button class="btn btn-info" onclick="history.back()">← Indietro</button>
                <p style="margin-top:30px;">Errore: ${esc(data.error)}</p>
            </div>
        `;
        return;
    }

    // Helper to render episodes HTML
    window.renderEpisodesGrid = function (eps, item) {
        if (!eps || eps.length === 0) return `<p style="color:var(--text-muted); padding: 20px;">Nessun episodio disponibile.</p>`;
        return eps.map(ep => `
            <button class="ep-card" tabindex="0" id="ep-item-${ep.id}" onclick="playEpisode(${item.id}, '${esc(item.slug)}', ${ep.id}, ${ep.number}, '${item.provider || "streamingcommunity"}')">
                <div class="ep-num">${ep.number}</div>
                <div class="ep-info">
                    <div class="ep-name">${esc(ep.name || `Episodio ${ep.number}`)}</div>
                    <div class="ep-sub">${esc(ep.file_name || "")}</div>
                </div>
                <div class="ep-actions">
                    <div class="icon-btn" title="Scarica Episodio" onclick="event.stopPropagation(); downloadEp(${item.id}, '${esc(item.slug)}', ${ep.id}, ${ep.number}, '${esc(ep.file_name || `${item.title || 'Serie'}_Ep${ep.number}.mp4`)}', '${esc(item.title || 'Serie')} - Ep ${ep.number}', '${esc(item.image || '')}')">⬇</div>
                </div>
            </button>
        `).join("");
    };

    window.loadSeason = async function (mediaId, slug, seasonNum) {
        // Update tabs styling
        document.querySelectorAll('.season-tab').forEach(t => {
            t.classList.remove('btn-primary');
            t.classList.add('btn-info');
        });
        const activeTab = document.getElementById(`tab-s${seasonNum}`);
        if (activeTab) {
            activeTab.classList.remove('btn-info');
            activeTab.classList.add('btn-primary');
        }

        const grid = document.getElementById('episodes-grid');
        grid.innerHTML = `<div class="loading" style="padding: 40px; margin: 0 auto;"><div class="spinner"></div></div>`;
        document.getElementById('current-season-title').innerText = `Episodi — Stagione ${seasonNum}`;

        try {
            const provider = window._currentAnime ? window._currentAnime.provider : "streamingcommunity";
            const res = await fetch(`/api/season?provider=${provider}&id=${mediaId}&slug=${slug}&season_num=${seasonNum}`);
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            // Update the stored anime object so next/prev works correctly for the new season
            if (window._currentAnime && window._currentAnime.id === mediaId) {
                // Find and update the season in the _currentAnime object
                const sIdx = window._currentAnime.seasons.findIndex(s => s.number === seasonNum);
                if (sIdx !== -1) {
                    window._currentAnime.seasons[sIdx].episodes = data.episodes;
                }
            }

            grid.innerHTML = renderEpisodesGrid(data.episodes, { id: mediaId, slug: slug });
        } catch (err) {
            grid.innerHTML = `<p style="color:red; padding: 20px;">Errore: ${err.message}</p>`;
        }
    };

    const item = data;
    const seasons = item.seasons || [];
    const isMovie = item.type === "movie";
    let firstEpId = null, firstEpNum = null;

    if (isMovie && seasons.length > 0 && seasons[0].episodes && seasons[0].episodes.length > 0) {
        // For movies, the single "episode" is the movie itself
        firstEpId = seasons[0].episodes[0].id;
        firstEpNum = 1;
    } else if (!isMovie && seasons.length > 0) {
        // For TV, find first season with loaded episodes
        for (const s of seasons) {
            if (s.episodes && s.episodes.length > 0) {
                firstEpId = s.episodes[0].id;
                firstEpNum = s.episodes[0].number;
                break;
            }
        }
    }

    window._currentAnime = item;

    let episodesHtml = "";
    if (seasons.length > 0 && !isMovie) {
        const eps = seasons[0].episodes || [];
        const tabsHtml = seasons.map(s => `
            <button class="btn ${s.number === seasons[0].number ? 'btn-primary' : 'btn-info'} season-tab" 
                    id="tab-s${s.number}" 
                    onclick="loadSeason(${item.id}, '${esc(item.slug)}', ${s.number})">
                ${s.name || "Stagione " + s.number}
            </button>
        `).join(" ");

        episodesHtml = `
            <div class="episodes-section">
                <div class="seasons-tabs" style="margin-bottom: 20px; display: flex; gap: 10px; overflow-x: auto;">
                    ${tabsHtml}
                </div>
                <div class="episodes-header">
                    <div class="episodes-title" id="current-season-title">Episodi — ${seasons[0].name || "Stagione " + seasons[0].number}</div>
                </div>
                <div class="episodes-grid" id="episodes-grid">
                    ${renderEpisodesGrid(eps, item)}
                </div>
            </div>
        `;
    }

    container.innerHTML = `
        <div class="detail-view">
            <div class="detail-banner" style="background-image: url('${esc(hdImage(item.background || item.image))}')">
                <div class="detail-info">
                    <h1 class="detail-title">${esc(item.title)}</h1>
                    <div class="detail-meta">
                        ${item.score ? `<span class="score">★ ${item.score}</span>` : ""}
                        <span class="maturity">${item.status || "HD"}</span>
                        <span>${isMovie ? "Film" : (item.episodes_count ? item.episodes_count + " Episodi" : "Serie TV")}</span>
                    </div>
                    <p class="detail-plot">${esc(item.plot || "Nessuna descrizione disponibile.")}</p>
                    <div class="detail-actions">
                        ${firstEpId ? `
                            <button class="btn btn-play" onclick="playEpisode(${item.id}, '${esc(item.slug)}', ${firstEpId}, ${firstEpNum}, '${item.provider || "streamingcommunity"}')">▶ Riproduci</button>
                            ${isMovie ? `
                                <button class="btn btn-info" onclick="downloadMovie(${item.id}, '${esc(item.slug)}', ${firstEpId}, '${esc(item.title)}', '${esc(item.image)}', '${item.provider || "streamingcommunity"}')">⬇ Scarica</button>
                            ` : `
                                <button class="btn btn-info" onclick="openSeriesDownloadModal()">⬇ Scarica Serie</button>
                            `}
                        ` : ""}
                        <button class="btn btn-info" onclick="history.back()">← Indietro</button>
                    </div>
                </div>
            </div>

            <div id="player-section" class="hidden">
                <div id="player-container">
                    <video id="video-player" controls crossorigin="anonymous" style="width:100%; height:100%;"></video>
                    <div class="player-overlay" id="player-overlay" onclick="resumePlayer()" tabindex="0">
                        <div class="big-play">▶</div>
                    </div>
                </div>
                <div class="player-nav">
                    <button class="btn btn-info" id="btn-prev-ep" tabindex="0" onclick="prevEpisode()" style="display:none">← Episodio Prec.</button>
                    <button class="btn btn-play" tabindex="0" onclick="togglePlayPause()">⏯ Play / Pausa</button>
                    <button class="btn btn-info" tabindex="0" onclick="videoSeek(-10)">⏪ Indietro 10s</button>
                    <button class="btn btn-info" tabindex="0" onclick="videoSeek(10)">Avanti 10s ⏩</button>
                    <button class="btn btn-play" id="btn-fullscreen" tabindex="0" onclick="toggleFullscreen()">⛶ Schermo Intero</button>
                    <button class="btn btn-info" id="btn-next-ep" tabindex="0" onclick="nextEpisode()" style="display:none">Episodio Succ. →</button>
                    <button class="btn btn-cast" id="btn-share-tv" tabindex="0" onclick="shareToTV()">📺 Trasmetti su TV</button>
                </div>
            </div>

            ${episodesHtml}
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════════════
// Player
// ═══════════════════════════════════════════════════════════════════

let currentHls = null;
let currentEpisodeIndex = -1;

async function playEpisode(mediaId, slug, episodeId, episodeNum, provider) {
    const section = document.getElementById("player-section");
    const video = document.getElementById("video-player");
    const overlay = document.getElementById("player-overlay");

    section.classList.remove("hidden");
    section.scrollIntoView({ behavior: "smooth" });
    overlay.classList.remove("hidden");

    document.querySelectorAll(".ep-card").forEach(el => el.classList.remove("active"));
    const active = document.getElementById(`ep-item-${episodeId}`);
    if (active) active.classList.add("active");

    // Find episode index across all seasons for nav
    if (window._currentAnime?.seasons) {
        window._currentPlayingSeason = null;
        for (const s of window._currentAnime.seasons) {
            if (s.episodes) {
                const idx = s.episodes.findIndex(e => e.id === episodeId);
                if (idx !== -1) {
                    currentEpisodeIndex = idx;
                    window._currentPlayingSeason = s;
                    break;
                }
            }
        }
    }
    updatePlayerNav();

    try {
        const data = await apiEpisode(mediaId, slug, episodeId, provider);
        if (data.error) { showToast("Errore: " + data.error, "error"); return; }

        if (data.stream_url) {
            const iframe = document.getElementById("iframe-player");
            if (iframe) {
                iframe.style.display = "none";
                iframe.src = "about:blank";
            }
            const nav = document.querySelector(".player-nav");
            if (nav) {
                nav.querySelectorAll(".btn:not(#btn-prev-ep):not(#btn-next-ep)").forEach(btn => btn.style.display = "");
            }

            if (currentHls) { currentHls.destroy(); currentHls = null; }
            video.style.display = "block";

            // Per file nativi mp4 (fallback rarissimo se non c'è HLS)
            if (data.stream_url.includes(".mp4") && !data.stream_url.includes(".m3u8")) {
                video.removeAttribute("crossorigin");
                video.src = data.stream_url;
                overlay.classList.add("hidden");

                video.onerror = () => {
                    showToast("Video offline o non trovato. Riprovare.", "error");
                };

                if (typeof AndroidBridge !== "undefined" && AndroidBridge.isCastConnected && AndroidBridge.isCastConnected()) {
                    setTimeout(() => shareToTV(), 500);
                } else {
                    video.play().catch(() => { });
                }
                setupPlayerAutoHide(video, overlay);
                return;
            }

            // Vixcloud ha bloccato Python (proxy). Usiamo l'URL diretto e lasciamo che la WebView scarichi il file nativamente.
            const streamUrl = data.stream_url;

            if (typeof Hls !== "undefined" && Hls.isSupported()) {
                currentHls = new Hls({ xhrSetup: xhr => xhr.withCredentials = false });
                currentHls.loadSource(streamUrl);
                currentHls.attachMedia(video);

                currentHls.on(Hls.Events.ERROR, function (event, data) {
                    if (data.fatal) {
                        switch (data.type) {
                            case Hls.ErrorTypes.NETWORK_ERROR:
                                 const statusText = data.response ? ` status: ${data.response.code}` : "";
                                 showToast(`Errore di rete: ${data.details}${statusText}`, "error");
                                 currentHls.startLoad();
                                break;
                            case Hls.ErrorTypes.MEDIA_ERROR:
                                currentHls.recoverMediaError();
                                break;
                            default:
                                showToast("Video offline o non trovato. Riprovare.", "error");
                                currentHls.destroy();
                                break;
                        }
                    }
                });

                currentHls.on(Hls.Events.MANIFEST_PARSED, () => {
                    overlay.classList.add("hidden");

                    if (typeof AndroidBridge !== "undefined" && AndroidBridge.isCastConnected && AndroidBridge.isCastConnected()) {
                        setTimeout(() => shareToTV(), 500);
                    } else {
                        video.play().catch(() => { });
                    }

                    setupPlayerAutoHide(video, overlay);
                });
                currentHls.on(Hls.Events.ERROR, (_, d) => {
                    if (d.fatal) {
                        showToast("Errore stream, riprova", "error");
                    }
                });
            } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
                video.src = streamUrl;
                overlay.classList.add("hidden");

                if (typeof AndroidBridge !== "undefined" && AndroidBridge.isCastConnected && AndroidBridge.isCastConnected()) {
                    setTimeout(() => shareToTV(), 500);
                } else {
                    video.play().catch(() => { });
                }
            }
        } else if (data.iframe_url) {
            // AnimeUnity fallback — open in new tab (no iframe ads)
            window.open(data.iframe_url, '_blank');
            section.classList.add("hidden");
        } else {
            showToast("Nessun video disponibile", "error");
        }
    } catch (err) {
        showToast("Errore: " + err.message, "error");
        // Show retry button in player area
        const overlay = document.getElementById("player-overlay");
        if (overlay) {
            overlay.classList.remove("hidden");
            overlay.innerHTML = `
                <div style="text-align:center; color:white;">
                    <div style="font-size:2rem; margin-bottom:16px;">⚠️</div>
                    <p style="margin-bottom:16px;">Errore di caricamento video</p>
                    <button class="btn btn-play" onclick="retryPlayback(${mediaId}, '${slug}', ${episodeId}, ${episodeNum}, '${provider}')" style="margin-right:10px;">🔄 Riprova</button>
                    <button class="btn btn-info" onclick="this.closest('.player-overlay,.hidden').classList.add('hidden')">✕ Chiudi</button>
                </div>
            `;
        }
    }
}

async function retryPlayback(mediaId, slug, episodeId, episodeNum, provider) {
    showToast("Aggiornamento domini e riprova...", "info");
    try {
        await fetch("/api/refresh-domains");
    } catch(e) { /* ignore */ }
    // Small delay to let the server reinitialize
    await new Promise(r => setTimeout(r, 500));
    playEpisode(mediaId, slug, episodeId, episodeNum, provider);
}

function resumePlayer() {
    const overlay = document.getElementById("player-overlay");
    const video = document.getElementById("video-player");

    // If Cast is connected, pressing play on overlay should cast it
    if (typeof AndroidBridge !== "undefined" && AndroidBridge.isCastConnected && AndroidBridge.isCastConnected()) {
        shareToTV();
        return;
    }

    overlay.classList.add("hidden");
    video.play().catch(() => { });
    setupPlayerAutoHide(video, overlay);
}

function setupPlayerAutoHide(video, overlay) {
    // Auto-hide overlay when video starts playing
    video.addEventListener("playing", () => {
        overlay.classList.add("hidden");
    });
    video.addEventListener("pause", () => {
        // Only show overlay if not in fullscreen (avoid blocking fullscreen view)
        if (!document.fullscreenElement) {
            overlay.classList.remove("hidden");
        }
    });
}

function updatePlayerNav() {
    const season = window._currentPlayingSeason;
    if (!season?.episodes) return;
    const eps = season.episodes;
    const prev = document.getElementById("btn-prev-ep");
    const next = document.getElementById("btn-next-ep");
    if (prev) prev.style.display = (currentEpisodeIndex > 0 && eps.length > 1) ? "block" : "none";
    if (next) next.style.display = (currentEpisodeIndex < eps.length - 1 && eps.length > 1) ? "block" : "none";
}

function prevEpisode() {
    const season = window._currentPlayingSeason;
    if (!window._currentAnime || !season?.episodes || currentEpisodeIndex <= 0) return;
    const ep = season.episodes[currentEpisodeIndex - 1];
    playEpisode(window._currentAnime.id, window._currentAnime.slug, ep.id, ep.number, window._currentAnime.provider);
}

function nextEpisode() {
    const season = window._currentPlayingSeason;
    if (!season?.episodes) return;
    const eps = season.episodes;
    if (currentEpisodeIndex >= eps.length - 1) return;
    const ep = eps[currentEpisodeIndex + 1];
    playEpisode(window._currentAnime.id, window._currentAnime.slug, ep.id, ep.number, window._currentAnime.provider);
}

function videoSeek(seconds) {
    const video = document.getElementById("video-player");
    if (video) {
        video.currentTime = Math.max(0, Math.min(video.duration || 0, video.currentTime + seconds));
    }
}



// ═══════════════════════════════════════════════════════════════════
// History
// ═══════════════════════════════════════════════════════════════════

function getHistory() {
    try {
        let history = JSON.parse(localStorage.getItem("tortuga_history") || "[]");
        // Migrate old CDN URLs
        let updated = false;
        history.forEach(item => {
            if (item.image && item.image.includes("streamingcommunityz.us")) {
                item.image = item.image.replace("streamingcommunityz.us", "streamingcommunityz.tech");
                updated = true;
            }
        });
        if (updated) localStorage.setItem("tortuga_history", JSON.stringify(history));
        return history;
    } catch { return []; }
}

function saveHistory(id, slug, data) {
    try {
        let h = getHistory().filter(x => x.id !== id);
        h.unshift({ id, slug, title: data.title, image: data.image, type: data.type, provider: data.provider || "streamingcommunity" });
        if (h.length > 20) h = h.slice(0, 20);
        localStorage.setItem("tortuga_history", JSON.stringify(h));
    } catch (e) { /* ignore */ }
}

// ═══════════════════════════════════════════════════════════════════
// Offline Download System & UI Manager
// ═══════════════════════════════════════════════════════════════════

let _activeDownloadIds = new Set();
let _lastDownloadStatus = { active: [], completed: [] };

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return "0 MB";
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

async function buildOfflineRowHtml() {
    try {
        const res = await fetch("/api/tv/download/status");
        const status = await res.json();
        _lastDownloadStatus = status;
        
        const active = status.active || [];
        const completed = status.completed || [];
        
        if (active.length === 0 && completed.length === 0) {
            return "";
        }
        
        const rowId = "row-offline";
        let cards = "";
        
        // Render Active Downloads with live progress bar and spinner
        active.forEach(item => {
            _activeDownloadIds.add(item.id);
            cards += `
                <button class="poster-card is-downloading" tabindex="0" id="offline-card-${item.id}">
                    <div class="poster-img-wrap">
                        <img class="poster-img" src="${esc(hdImage(item.image))}" alt="${esc(item.title)}" loading="lazy">
                        <div class="download-overlay">
                            <div class="download-spinner-ring"></div>
                            <div class="download-pct-badge" id="card-p-${item.id}">${item.progress || 0}%</div>
                            <div class="download-subtext" id="card-s-${item.id}">${item.speed || 'In avvio...'}</div>
                        </div>
                        <div class="card-prog-wrap">
                            <div class="card-prog-bar" id="card-b-${item.id}" style="width: ${item.progress || 0}%"></div>
                        </div>
                    </div>
                    <div class="poster-title">${esc(item.title)}</div>
                    <div style="font-size:12px; color:#ff4444; margin-top:5px; cursor:pointer; font-weight:600;" onclick="event.stopPropagation(); cancelDownload('${item.id}')">✕ Annulla</div>
                </button>
            `;
        });
        
        // Render Completed Offline Movies/Episodes
        completed.forEach(item => {
            cards += `
                <button class="poster-card" tabindex="0" onclick="playLocalFile('${esc(item.fileName)}', '${esc(item.title)}')">
                    <div class="poster-img-wrap">
                        <img class="poster-img" src="${esc(hdImage(item.image))}" alt="${esc(item.title)}" loading="lazy">
                        <div class="poster-type" style="background:#10b981;">📥 OFFLINE</div>
                        <div class="poster-overlay">
                            <div class="poster-play">▶</div>
                        </div>
                    </div>
                    <div class="poster-title">${esc(item.title)}</div>
                    <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px; color:var(--text-muted); margin-top:4px;">
                        <span>💾 ${formatBytes(item.size)}</span>
                        <span style="color:#ff4444; cursor:pointer; font-weight:600;" onclick="event.stopPropagation(); deleteOfflineFile('${esc(item.fileName)}')">🗑 Elimina</span>
                    </div>
                </button>
            `;
        });
        
        const totalCount = active.length + completed.length;
        return `
            <div class="row-section" id="offline-row-section">
                <div class="row-title">📥 Film & Serie Scaricati Offline <span class="count-badge">${totalCount}</span></div>
                <div class="row-scroll-container">
                    <button class="row-arrow row-arrow-left" onclick="scrollRow('${rowId}', -1)">‹</button>
                    <div class="row-scroll" id="${rowId}">${cards}</div>
                    <button class="row-arrow row-arrow-right" onclick="scrollRow('${rowId}', 1)">›</button>
                </div>
            </div>
        `;
    } catch (e) {
        console.error("Error building offline row:", e);
        return "";
    }
}

async function downloadMovie(mediaId, slug, episodeId, title, image, provider = "streamingcommunity") {
    showToast("Avvio download: " + title, "success");
    const cleanName = (title + ".mp4").replace(/[^a-zA-Z0-9_\-\.]/g, "_");
    try {
        const res = await fetch(`/api/tv/download/start?id=${mediaId}&slug=${slug}&episode_id=${episodeId || 'movie'}&provider=${provider}&title=${encodeURIComponent(title)}&image=${encodeURIComponent(image)}&filename=${encodeURIComponent(cleanName)}`);
        const data = await res.json();
        if (data.status === "already_downloading") {
            showToast("Download già in corso per " + title, "info");
        } else if (data.status === "started") {
            showToast("📥 Download avviato: " + title, "success");
        } else if (data.error) {
            showToast("Errore download: " + data.error, "error");
        }
        pollDownloadStatus(true);
    } catch (e) {
        showToast("Errore connessione: " + e.message, "error");
    }
}

async function downloadEp(mediaId, slug, episodeId, episodeNum, fileName, customTitle, customImage) {
    const provider = window._currentAnime ? window._currentAnime.provider : "streamingcommunity";
    const title = customTitle || (window._currentAnime ? `${window._currentAnime.title} - Ep ${episodeNum}` : `Episodio ${episodeNum}`);
    const image = customImage || (window._currentAnime ? window._currentAnime.image : "");
    showToast("Avvio download: " + title, "success");
    
    const cleanName = (fileName || `${title}.mp4`).replace(/[^a-zA-Z0-9_\-\.]/g, "_");
    try {
        const res = await fetch(`/api/tv/download/start?id=${mediaId}&slug=${slug}&episode_id=${episodeId}&provider=${provider}&title=${encodeURIComponent(title)}&image=${encodeURIComponent(image)}&filename=${encodeURIComponent(cleanName)}`);
        const data = await res.json();
        if (data.status === "already_downloading") {
            showToast("Download già in corso per " + title, "info");
        } else if (data.status === "started") {
            showToast("📥 Download avviato: " + title, "success");
        } else if (data.error) {
            showToast("Errore download: " + data.error, "error");
        }
        pollDownloadStatus(true);
    } catch (e) {
        showToast("Errore connessione: " + e.message, "error");
    }
}

function openSeriesDownloadModal() {
    const item = window._currentAnime;
    if (!item) return;
    
    let modal = document.getElementById("series-download-modal");
    if (!modal) {
        modal = document.createElement("div");
        modal.id = "series-download-modal";
        modal.className = "modal-container";
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(12px);
            z-index: 10000; display: flex; align-items: center; justify-content: center;
            padding: 20px;
        `;
        document.body.appendChild(modal);
    }
    
    const seasons = item.seasons || [];
    const totalEps = item.episodes_count || (seasons.reduce((acc, s) => acc + (s.episodes ? s.episodes.length : 0), 0)) || 'Tutti';
    
    modal.innerHTML = `
        <div style="background: rgba(20, 20, 35, 0.98); border: 1px solid rgba(181, 55, 242, 0.4); border-radius: 16px; padding: 24px; max-width: 480px; width: 100%; box-shadow: 0 10px 40px rgba(0,0,0,0.8), 0 0 25px rgba(181, 55, 242, 0.25); text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">📥</div>
            <h2 style="font-size: 1.3rem; font-weight: 700; color: #fff; margin-bottom: 8px;">Opzioni Download Serie</h2>
            <p style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 20px;">${esc(item.title)}</p>
            
            <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px;">
                <button class="btn btn-play" style="width: 100%; justify-content: center; padding: 12px; font-weight: 700;" onclick="downloadEntireSeries(false)">
                    ⬇ Scarica Tutta la Serie (${totalEps} Episodi)
                </button>
                <button class="btn btn-info" style="width: 100%; justify-content: center; padding: 12px; font-weight: 700;" onclick="downloadEntireSeries(true)">
                    ⬇ Scarica Stagione Attuale
                </button>
            </div>
            
            <p style="font-size: 0.8rem; color: #a1a1aa; line-height: 1.4; margin-bottom: 20px;">
                💡 <em>Suggerimento: Per scaricare un singolo episodio, tocca l'icona ⬇ posizionata a destra di ogni episodio nella lista sottostante.</em>
            </p>
            
            <button class="btn btn-info" style="width: 100%; justify-content: center; border: 1px solid rgba(255,255,255,0.2);" onclick="closeSeriesDownloadModal()">
                ✕ Chiudi
            </button>
        </div>
    `;
    modal.style.display = "flex";
}

function closeSeriesDownloadModal() {
    const modal = document.getElementById("series-download-modal");
    if (modal) modal.style.display = "none";
}

async function downloadEntireSeries(seasonOnly = false) {
    closeSeriesDownloadModal();
    const item = window._currentAnime;
    if (!item) return;
    
    const provider = item.provider || "streamingcommunity";
    const seasons = item.seasons || [];
    
    if (seasons.length === 0) {
        showToast("Nessun episodio trovato per il download", "error");
        return;
    }
    
    let episodesToDownload = [];
    
    if (seasonOnly) {
        // Find current season episodes
        const currentSeason = seasons[0];
        if (currentSeason && currentSeason.episodes) {
            episodesToDownload = currentSeason.episodes.map(ep => ({
                epId: ep.id,
                epNum: ep.number,
                seasonNum: currentSeason.number,
                title: `${item.title} - S${currentSeason.number}E${ep.number}`,
                fileName: `${item.title}_S${currentSeason.number}E${ep.number}.mp4`
            }));
        }
    } else {
        // Collect all episodes from all seasons
        for (const s of seasons) {
            let eps = s.episodes;
            if (!eps || eps.length === 0) {
                try {
                    const res = await fetch(`/api/season?provider=${provider}&id=${item.id}&slug=${item.slug}&season_num=${s.number}`);
                    const data = await res.json();
                    eps = data.episodes || [];
                } catch(e) {}
            }
            if (eps && eps.length > 0) {
                eps.forEach(ep => {
                    episodesToDownload.push({
                        epId: ep.id,
                        epNum: ep.number,
                        seasonNum: s.number,
                        title: `${item.title} - S${s.number}E${ep.number}`,
                        fileName: `${item.title}_S${s.number}E${ep.number}.mp4`
                    });
                });
            }
        }
    }
    
    if (episodesToDownload.length === 0) {
        showToast("Nessun episodio disponibile", "error");
        return;
    }
    
    showToast(`🚀 Accodamento di ${episodesToDownload.length} episodi in download...`, "success");
    
    for (const ep of episodesToDownload) {
        const cleanName = ep.fileName.replace(/[^a-zA-Z0-9_\-\.]/g, "_");
        try {
            fetch(`/api/tv/download/start?id=${item.id}&slug=${item.slug}&episode_id=${ep.epId}&provider=${provider}&title=${encodeURIComponent(ep.title)}&image=${encodeURIComponent(item.image || '')}&filename=${encodeURIComponent(cleanName)}`);
        } catch(e) {}
        await new Promise(r => setTimeout(r, 200));
    }
    
    showToast(`✅ ${episodesToDownload.length} episodi accodati per il download offline!`, "success");
    pollDownloadStatus(true);
}

async function cancelDownload(taskId) {
    try {
        const res = await fetch(`/api/tv/download/cancel?id=${taskId}`);
        const data = await res.json();
        if (data.success) {
            showToast("Download annullato", "info");
            _activeDownloadIds.delete(taskId);
            pollDownloadStatus(true);
        }
    } catch (e) {
        showToast("Errore annullamento: " + e.message, "error");
    }
}

async function deleteOfflineFile(fileName) {
    if (!confirm("Sei sicuro di voler eliminare " + fileName + "?")) return;
    try {
        await fetch(`/api/tv/download/delete?filename=${encodeURIComponent(fileName)}`);
        if (typeof AndroidBridge !== "undefined" && AndroidBridge.deleteDownloadedFile) {
            AndroidBridge.deleteDownloadedFile(fileName);
        }
        showToast("🗑 File eliminato", "info");
        if (router.currentView === "home") {
            renderHome(document.getElementById("app"));
        } else {
            pollDownloadStatus(true);
        }
    } catch (e) {
        showToast("Errore eliminazione: " + e.message, "error");
    }
}

function playLocalFile(fileName, title) {
    const modal = document.getElementById("offline-player-modal");
    const video = document.getElementById("offline-video-player");
    const titleEl = document.getElementById("offline-player-title");
    
    if (!modal || !video) return;
    
    if (titleEl) titleEl.innerText = (title || fileName) + " [OFFLINE]";
    
    const localUrl = `http://127.0.0.1:5000/api/local_file?filename=${encodeURIComponent(fileName)}`;
    video.src = localUrl;
    
    modal.classList.remove("hidden");
    
    const closeBtn = document.getElementById("btn-close-offline-player");
    if (closeBtn) closeBtn.focus();
    
    video.play().catch(e => console.log("Local playback autoplay", e));
}

function closeOfflinePlayer() {
    const modal = document.getElementById("offline-player-modal");
    const video = document.getElementById("offline-video-player");
    if (video) {
        video.pause();
        video.src = "";
    }
    if (modal) {
        modal.classList.add("hidden");
    }
}

async function pollDownloadStatus(forceHomeUpdate = false) {
    try {
        const res = await fetch("/api/tv/download/status");
        const data = await res.json();
        const active = data.active || [];
        const completed = data.completed || [];
        
        const floatWidget = document.getElementById("download-progress");
        const floatTitle = document.getElementById("dl-title");
        const floatFill = document.getElementById("dl-fill");
        const floatText = document.getElementById("dl-text");
        
        if (active.length > 0) {
            const first = active[0];
            if (floatWidget) {
                floatWidget.classList.add("active");
                if (floatTitle) floatTitle.innerText = first.title || first.fileName;
                if (floatFill) floatFill.style.width = `${first.progress || 0}%`;
                if (floatText) floatText.innerText = `${first.progress || 0}% - ${first.speed || ''} (${first.current_segment || 0}/${first.total_segments || '?'})`;
            }
            
            // Live update DOM cards without re-rendering the whole page
            active.forEach(item => {
                const badge = document.getElementById(`card-p-${item.id}`);
                const bar = document.getElementById(`card-b-${item.id}`);
                const spd = document.getElementById(`card-s-${item.id}`);
                if (badge) badge.innerText = `${item.progress || 0}%`;
                if (bar) bar.style.width = `${item.progress || 0}%`;
                if (spd) spd.innerText = item.speed || 'Scaricamento...';
            });
        } else {
            if (floatWidget) floatWidget.classList.remove("active");
        }
        
        // Check for newly completed downloads
        const currentActiveIds = new Set(active.map(a => a.id));
        for (const prevId of _activeDownloadIds) {
            if (!currentActiveIds.has(prevId)) {
                // Completed!
                showToast("✅ Download completato al 100%!", "success");
                _activeDownloadIds.delete(prevId);
                if (router.currentView === "home") {
                    renderHome(document.getElementById("app"));
                }
            }
        }
        
        active.forEach(a => _activeDownloadIds.add(a.id));
        
        if (forceHomeUpdate && router.currentView === "home") {
            renderHome(document.getElementById("app"));
        }
    } catch (e) {
        // Silent poll error
    }
}

function startDownloadMonitoring() {
    setInterval(() => {
        pollDownloadStatus();
    }, 1500);
}


// ═══════════════════════════════════════════════════════════════════
// Utils
// ═══════════════════════════════════════════════════════════════════

function esc(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "\\'");
}

function hdImage(url) {
    if (!url) return "";
    if (url.includes("quality=") || !url.includes("images/")) return url;
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}quality=100`;
}

function showToast(message, type = "success") {
    const c = document.getElementById("toast-container");
    const t = document.createElement("div");
    t.className = `toast ${type}`;
    t.textContent = message;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity = "0"; t.style.transition = "0.3s"; setTimeout(() => t.remove(), 300); }, 3000);
}



function handleNavScroll() {
    const nav = document.getElementById("navbar");
    if (window.scrollY > 50) nav.classList.add("scrolled");
    else nav.classList.remove("scrolled");
}

function clearNavSearch() {
    const input = document.getElementById("nav-search-input");
    input.value = "";
    document.getElementById("nav-search-clear").classList.remove("visible");
    input.focus();
}

// ═══════════════════════════════════════════════════════════════════
// Background Tasks & Periodic Domain Refresh
// ═══════════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
    // Auto-refresh domains every 20 minutes in background
    setInterval(async () => {
        try {
            const r = await fetch("/api/refresh-domains");
            const data = await r.json();
            if (data.success) {
                console.log("[AutoRefresh] Domain updated: " + data.new_domain);
            }
        } catch (e) {
            console.warn("[AutoRefresh] Failed:", e);
        }
    }, 20 * 60 * 1000); // 20 minutes

    const input = document.getElementById("nav-search-input");
    const clear = document.getElementById("nav-search-clear");

    if (input && clear) {
        input.addEventListener("input", () => {
            clear.classList.toggle("visible", input.value.length > 0);
        });

        const isTouch = ('ontouchstart' in window) || navigator.maxTouchPoints > 0 || window.matchMedia("(pointer: coarse)").matches;

        if (!isTouch) {
            // TV Context
            input.readOnly = true;
            input.addEventListener("click", openOSK);
            input.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    openOSK();
                }
            });
        } else {
            // Mobile Context
            input.readOnly = false;
            input.addEventListener("keydown", (e) => {
                if (e.key === "Enter" && input.value.trim().length >= 2) {
                    performSearch(input.value.trim());
                }
            });
        }

        // Keyboard shortcut: Ctrl+K or / to focus search
        document.addEventListener("keydown", (e) => {
            if ((e.ctrlKey && e.key === "k") || (e.key === "/" && !e.target.closest("input"))) {
                e.preventDefault();
                input.focus();
                input.select();
            }
            if (e.key === "Escape" && router.currentView !== "home") {
                history.back();
            }
        });
    }

    // ═══ Player keyboard controls (Space to Play/Pause) ═══
    document.addEventListener("keydown", (e) => {
        const video = document.getElementById("video-player");
        if (!video || video.paused === undefined) return;
        const section = document.getElementById("player-section");
        if (!section || section.classList.contains("hidden")) return;
        if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

        switch (e.key) {
            case " ":
            case "MediaPlayPause":
                if (e.target.tagName !== "BUTTON") e.preventDefault();
                if (video.paused) {
                    video.play().catch(() => { });
                    const overlay = document.getElementById("player-overlay");
                    if (overlay) overlay.classList.add("hidden");
                } else {
                    video.pause();
                }
                break;
        }
    });

    // ═══════════════════════════════════════════════════════════════
    // ★ TV D-pad Spatial Navigation System
    // Intercepts Arrow keys to move focus between focusable elements.
    // Uses geometric distance to find the nearest element in each direction.
    // ═══════════════════════════════════════════════════════════════
    const FOCUSABLE_SELECTOR = 'button, [tabindex="0"], a[href], input, .genre-chip, .nav-link, .season-tab';

    function getFocusableElements() {
        return Array.from(document.querySelectorAll(FOCUSABLE_SELECTOR)).filter(el => {
            if (el.offsetParent === null && !el.closest('.player-nav')) return false; // hidden
            if (el.disabled) return false;
            if (el.style.display === 'none') return false;
            const rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        });
    }

    function getCenter(rect) {
        return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    }

    function findBestCandidate(current, direction, candidates) {
        const currentRect = current.getBoundingClientRect();
        const c = getCenter(currentRect);
        let best = null;
        let bestDist = Infinity;

        for (const el of candidates) {
            if (el === current) continue;
            const rect = el.getBoundingClientRect();
            const t = getCenter(rect);

            // Check direction filter
            let valid = false;
            switch (direction) {
                case "ArrowLeft": valid = t.x < c.x - 5; break;
                case "ArrowRight": valid = t.x > c.x + 5; break;
                case "ArrowUp": valid = t.y < c.y - 5; break;
                case "ArrowDown": valid = t.y > c.y + 5; break;
            }
            if (!valid) continue;

            // Distance calculation — favor elements directly in the line of movement
            let dx = t.x - c.x;
            let dy = t.y - c.y;
            let dist;
            if (direction === "ArrowLeft" || direction === "ArrowRight") {
                dist = Math.abs(dx) + Math.abs(dy) * 3; // penalize vertical offset
            } else {
                dist = Math.abs(dy) + Math.abs(dx) * 3; // penalize horizontal offset
            }

            if (dist < bestDist) {
                bestDist = dist;
                best = el;
            }
        }
        return best;
    }

    document.addEventListener("keydown", (e) => {
        if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter"].includes(e.key)) return;
        if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
        // Don't hijack video controls when the native <video> controls have focus
        if (e.target.tagName === "VIDEO") return;

        if (e.key === "Enter") {
            // Click the focused element
            const el = document.activeElement;
            if (el && el !== document.body) {
                e.preventDefault();
                el.click();
            }
            return;
        }

        // Spatial navigation for arrow keys
        const focusable = getFocusableElements();
        if (focusable.length === 0) return;

        let current = document.activeElement;
        // If nothing is focused, focus the first visible element
        if (!current || current === document.body || !focusable.includes(current)) {
            focusable[0].focus({ preventScroll: false });
            focusable[0].scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
            e.preventDefault();
            return;
        }

        const best = findBestCandidate(current, e.key, focusable);
        if (best) {
            e.preventDefault();
            best.focus({ preventScroll: false });
            best.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
        }
    });

    window.addEventListener("popstate", (e) => {
        if (!preloader || preloader.classList.contains("fade-out")) {
            if (e.state && e.state.view) {
                router.navigate(e.state.view, e.state.data, false);
            } else {
                router.navigate("home", null, false);
            }
        }
    });
});
// Add to the bottom of app.js
let longPressTimer;
const navbarBrand = document.querySelector('.navbar-brand');

if (navbarBrand) {
    navbarBrand.addEventListener('mousedown', startPress);
    navbarBrand.addEventListener('touchstart', startPress);

    navbarBrand.addEventListener('mouseup', cancelPress);
    navbarBrand.addEventListener('mouseleave', cancelPress);
    navbarBrand.addEventListener('touchend', cancelPress);
    navbarBrand.addEventListener('touchcancel', cancelPress);
}

function startPress(e) {
    longPressTimer = setTimeout(async () => {
        showToast("Aggiornamento domini in corso...", "info");
        try {
            const res = await fetch("/api/refresh-domains");
            const data = await res.json();
            if (data.success) {
                showToast("Domini aggiornati! Nuovo dominio: " + data.new_domain, "success");
            } else {
                showToast("Errore durante l'aggiornamento.", "error");
            }
        } catch (err) {
            showToast("Errore di rete.", "error");
        }
    }, 2000); // 2 seconds press
}

function cancelPress(e) {
    clearTimeout(longPressTimer);
}

// ═══════════════════════════════════════════════════════════════════
// OSK & Fullscreen
// ═══════════════════════════════════════════════════════════════════

function openOSK() {
    const osk = document.getElementById("tv-keyboard");
    const display = document.getElementById("keyboard-display");
    const input = document.getElementById("nav-search-input");
    osk.classList.remove("hidden");
    display.value = input.value;
    setTimeout(() => {
        const firstKey = document.getElementById("osk-first-key");
        if (firstKey) firstKey.focus();
    }, 100);
}

function closeOSK() {
    document.getElementById("tv-keyboard").classList.add("hidden");
    document.getElementById("nav-search-input").focus();
}

function handleKey(char) {
    const display = document.getElementById("keyboard-display");
    display.value += char;
}

function handleBackspace() {
    const display = document.getElementById("keyboard-display");
    display.value = display.value.slice(0, -1);
}

function submitOSK() {
    const display = document.getElementById("keyboard-display");
    const input = document.getElementById("nav-search-input");
    input.value = display.value;
    closeOSK();

    if (input.value.trim().length >= 2) {
        performSearch(input.value.trim());
    } else {
        clearNavSearch();
    }
}

function toggleFullscreen() {
    const video = document.getElementById("video-player");
    if (!video) return;
    if (video.requestFullscreen) {
        video.requestFullscreen();
    } else if (video.webkitRequestFullscreen) {
        video.webkitRequestFullscreen();
    } else if (video.msRequestFullscreen) {
        video.msRequestFullscreen();
    }
}

async function shareToTV() {
    const video = document.getElementById("video-player");
    if (!video || (!video.src && !currentHls)) {
        showToast("Nessun video in riproduzione", "error");
        return;
    }

    // Get the stream URL
    let url = video.src;
    if (!url || url.startsWith("blob:")) {
        if (currentHls && currentHls.url) {
            url = currentHls.url;
            if (url.startsWith("/")) {
                const port = location.port || "5000";

                // Fetch the actual LAN IP of the phone so the Chromecast can reach it!
                let serverIP = location.hostname; // Default 127.0.0.1
                if (typeof AndroidBridge !== "undefined") {
                    try {
                        const localIp = AndroidBridge.getLocalIpAddress();
                        if (localIp && localIp !== "127.0.0.1") {
                            serverIP = localIp;
                        }
                    } catch (e) { }
                }
                url = `http://${serverIP}:${port}${url}`;
            }
        } else {
            showToast("Impossibile estrarre URL per il cast", "error");
            return;
        }
    }

    const title = document.querySelector(".title-name") ? document.querySelector(".title-name").textContent : "Tortuga TV";
    const image = window._currentAnime ? window._currentAnime.image : "";

    if (typeof AndroidBridge !== "undefined") {
        try {
            if (AndroidBridge.isCastConnected()) {
                // Native Chromecast is connected! Send the video.
                AndroidBridge.castVideo(url, title, image);
                if (video && !video.paused) {
                    video.pause();
                }
            } else {
                // Not connected natively.
                showToast("Avvio lettore esterno in corso...", "info");
                setTimeout(() => {
                    AndroidBridge.openExternal(url);
                }, 1500);
            }
        } catch (e) {
            showToast("Errore di comunicazione con l'app: " + e.message, "error");
        }
    } else {
        showToast("Cast disponibile solo sull'app Android", "error");
    }
}

function togglePlayPause() {
    const video = document.getElementById("video-player");
    if (!video) return;

    // If Cast is connected, pressing play should cast it
    if (typeof AndroidBridge !== "undefined" && AndroidBridge.isCastConnected && AndroidBridge.isCastConnected()) {
        shareToTV();
        return;
    }

    const overlay = document.getElementById("player-overlay");
    if (video.paused) {
        video.play().catch(() => { });
        if (overlay) overlay.classList.add("hidden");
    } else {
        video.pause();
    }
}

// ═══════════════════════════════════════════════════════════════════
// IPTV Live Channels (Nazionali & Internazionali)
// ═══════════════════════════════════════════════════════════════════

let iptvChannelsCache = [];
let iptvCurrentCountry = 'all';
let iptvCurrentCategory = 'all';
let iptvSearchQuery = '';
let currentIptvIndex = -1;
let currentIptvHls = null;

window.loadIptvSection = function() {
    router.navigate("iptv");
};

async function renderIptv(container, data = null) {
    window.removeEventListener("scroll", handleNavScroll);
    document.getElementById("navbar").classList.add("scrolled");

    container.innerHTML = `
        <div class="iptv-view">
            <!-- Header Banner -->
            <div class="iptv-header">
                <div class="iptv-header-content">
                    <div class="iptv-badge">🔴 IN DIRETTA STREAMING HD</div>
                    <h1 class="iptv-title">📡 IPTV Live — Nazionali & Internazionali</h1>
                    <p class="iptv-subtitle">Guarda tutti i canali TV in chiaro dell'Italia e del mondo in alta definizione.</p>
                </div>
            </div>

            <!-- Filters Bar -->
            <div class="iptv-controls">
                <!-- Country Filter Flags -->
                <div class="iptv-filter-group countries" id="iptv-countries">
                    <button class="iptv-chip active" onclick="setIptvCountry('all', this)" data-focusable tabindex="0">🌍 Tutti</button>
                    <button class="iptv-chip" onclick="setIptvCountry('IT', this)" data-focusable tabindex="0">🇮🇹 Italia</button>
                    <button class="iptv-chip" onclick="setIptvCountry('US', this)" data-focusable tabindex="0">🇺🇸 USA</button>
                    <button class="iptv-chip" onclick="setIptvCountry('GB', this)" data-focusable tabindex="0">🇬🇧 UK</button>
                    <button class="iptv-chip" onclick="setIptvCountry('ES', this)" data-focusable tabindex="0">🇪🇸 Spagna</button>
                    <button class="iptv-chip" onclick="setIptvCountry('FR', this)" data-focusable tabindex="0">🇫🇷 Francia</button>
                    <button class="iptv-chip" onclick="setIptvCountry('DE', this)" data-focusable tabindex="0">🇩🇪 Germania</button>
                    <button class="iptv-chip" onclick="setIptvCountry('JP', this)" data-focusable tabindex="0">🇯🇵 Giappone</button>
                </div>

                <!-- Category Filter Pills -->
                <div class="iptv-filter-group categories" id="iptv-categories">
                    <button class="iptv-pill active" onclick="setIptvCategory('all', this)" data-focusable tabindex="0">Tutti</button>
                    <button class="iptv-pill" onclick="setIptvCategory('news', this)" data-focusable tabindex="0">📰 Notizie</button>
                    <button class="iptv-pill" onclick="setIptvCategory('music', this)" data-focusable tabindex="0">🎵 Musica TV</button>
                    <button class="iptv-pill" onclick="setIptvCategory('sport', this)" data-focusable tabindex="0">⚽ Sport</button>
                    <button class="iptv-pill" onclick="setIptvCategory('movies', this)" data-focusable tabindex="0">🎬 Cinema & Serie</button>
                    <button class="iptv-pill" onclick="setIptvCategory('general', this)" data-focusable tabindex="0">📺 Generali</button>
                    <button class="iptv-pill" onclick="setIptvCategory('documentary', this)" data-focusable tabindex="0">🌍 Documentari</button>
                    <button class="iptv-pill" onclick="setIptvCategory('kids', this)" data-focusable tabindex="0">🧸 Ragazzi</button>
                </div>

                <!-- Live Channel Search -->
                <div class="iptv-search-wrap">
                    <span class="search-icon">🔍</span>
                    <input type="text" id="iptv-search-input" class="iptv-search-input" placeholder="Cerca canale (es. Rai, Sky, Mediaset, BBC)..." oninput="onIptvSearchInput(this.value)" autocomplete="off" data-focusable tabindex="0" />
                </div>
            </div>

            <!-- Channels Grid -->
            <div id="iptv-grid" class="iptv-grid">
                <div class="loading" style="grid-column: 1/-1; padding: 50px 0;"><div class="spinner"></div></div>
            </div>
        </div>

        <!-- Fullscreen IPTV Player Modal -->
        <div id="iptv-player-modal" class="iptv-player-modal hidden">
            <div class="iptv-player-container">
                <video id="iptv-video" class="iptv-video" playsinline controls autoplay></video>
                <div id="iptv-player-header" class="iptv-player-header">
                    <div class="iptv-now-playing">
                        <img id="iptv-modal-logo" src="" alt="" class="iptv-modal-logo" />
                        <div>
                            <div id="iptv-modal-title" class="iptv-modal-title">Canale</div>
                            <div id="iptv-modal-badge" class="iptv-modal-badge">🔴 LIVE HD</div>
                        </div>
                    </div>
                    <div class="iptv-player-actions">
                        <button class="btn btn-info" onclick="prevIptvChannel()" data-focusable tabindex="0" title="Canale Precedente">⏮ Precedente</button>
                        <button class="btn btn-info" onclick="nextIptvChannel()" data-focusable tabindex="0" title="Canale Successivo">⏭ Successivo</button>
                        <button class="btn btn-danger" onclick="closeIptvPlayer()" data-focusable tabindex="0" title="Chiudi">✕ Chiudi</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    try {
        const r = await fetch('/api/iptv/channels');
        const data = await r.json();
        iptvChannelsCache = data.channels || [];
        renderIptvGrid();
    } catch(e) {
        document.getElementById('iptv-grid').innerHTML = `<p style="color:red; grid-column:1/-1; text-align:center;">Errore caricamento canali: ${e.message}</p>`;
    }
}

function renderIptvGrid() {
    const grid = document.getElementById('iptv-grid');
    if (!grid) return;

    let filtered = iptvChannelsCache;
    if (iptvCurrentCountry !== 'all') {
        filtered = filtered.filter(c => c.country === iptvCurrentCountry);
    }
    if (iptvCurrentCategory !== 'all') {
        filtered = filtered.filter(c => c.category === iptvCurrentCategory);
    }
    if (iptvSearchQuery) {
        filtered = filtered.filter(c => c.name.toLowerCase().includes(iptvSearchQuery) || c.category.toLowerCase().includes(iptvSearchQuery));
    }

    if (filtered.length === 0) {
        grid.innerHTML = `<p style="color:var(--text-muted); grid-column:1/-1; text-align:center; padding: 40px;">Nessun canale trovato con i filtri selezionati.</p>`;
        return;
    }

    grid.innerHTML = filtered.map((c, i) => `
        <button class="iptv-card" onclick="openIptvPlayerByIndex(${i})" data-focusable tabindex="0">
            <div class="iptv-card-top">
                <span class="iptv-flag">${c.flag || '📺'}</span>
                <span class="iptv-live-tag">🔴 LIVE</span>
            </div>
            <div class="iptv-logo-wrap">
                <img src="${c.logo}" alt="${esc(c.name)}" class="iptv-logo" loading="lazy" onerror="this.src='/static/icona_app.jpg'" />
            </div>
            <div class="iptv-card-info">
                <div class="iptv-card-name">${esc(c.name)}</div>
                <div class="iptv-card-cat">${c.quality || '1080p'} • ${getCategoryLabel(c.category)}</div>
            </div>
        </button>
    `).join('');
}

function getCategoryLabel(cat) {
    const map = {
        'general': 'Generale',
        'news': 'Notizie',
        'music': 'Musica TV',
        'sport': 'Sport',
        'movies': 'Cinema & Serie',
        'documentary': 'Documentari',
        'kids': 'Ragazzi'
    };
    return map[cat] || cat;
}

window.setIptvCountry = function(country, btn) {
    iptvCurrentCountry = country;
    document.querySelectorAll('#iptv-countries .iptv-chip').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    renderIptvGrid();
};

window.setIptvCategory = function(cat, btn) {
    iptvCurrentCategory = cat;
    document.querySelectorAll('#iptv-categories .iptv-pill').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    renderIptvGrid();
};

window.onIptvSearchInput = function(val) {
    iptvSearchQuery = val.toLowerCase().trim();
    renderIptvGrid();
};

window.openIptvPlayerByIndex = function(filteredIdx) {
    let filtered = iptvChannelsCache;
    if (iptvCurrentCountry !== 'all') filtered = filtered.filter(c => c.country === iptvCurrentCountry);
    if (iptvCurrentCategory !== 'all') filtered = filtered.filter(c => c.category === iptvCurrentCategory);
    if (iptvSearchQuery) filtered = filtered.filter(c => c.name.toLowerCase().includes(iptvSearchQuery));

    const channel = filtered[filteredIdx];
    if (!channel) return;

    currentIptvIndex = iptvChannelsCache.findIndex(c => c.id === channel.id);
    playIptvChannel(channel);
};

function playIptvChannel(channel) {
    const modal = document.getElementById('iptv-player-modal');
    const video = document.getElementById('iptv-video');
    const logo = document.getElementById('iptv-modal-logo');
    const title = document.getElementById('iptv-modal-title');
    const badge = document.getElementById('iptv-modal-badge');

    if (!modal || !video) return;

    modal.classList.remove('hidden');
    logo.src = channel.logo || '/static/icona_app.jpg';
    title.textContent = `${channel.flag} ${channel.name}`;
    badge.textContent = `🔴 LIVE • ${channel.quality || 'HD'}`;

    if (currentIptvHls) {
        currentIptvHls.destroy();
        currentIptvHls = null;
    }

    let triedBackup = false;
    const proxiedUrl = `/api/iptv/stream?url=${encodeURIComponent(channel.url)}`;

    if (typeof Hls !== "undefined" && Hls.isSupported()) {
        currentIptvHls = new Hls({
            enableWorker: true,
            lowLatencyMode: true,
            maxBufferLength: 30,
            xhrSetup: xhr => xhr.withCredentials = false
        });
        currentIptvHls.loadSource(proxiedUrl);
        currentIptvHls.attachMedia(video);

        currentIptvHls.on(Hls.Events.ERROR, (event, data) => {
            if (data.fatal) {
                console.warn('[IPTV Stream Fatal Error]', data);
                if (!triedBackup && channel.backup_url && channel.backup_url.length > 8) {
                    triedBackup = true;
                    showToast("Passaggio al flusso di backup...", "info");
                    const proxiedBackup = `/api/iptv/stream?url=${encodeURIComponent(channel.backup_url)}`;
                    currentIptvHls.loadSource(proxiedBackup);
                } else {
                    if (currentIptvHls) {
                        currentIptvHls.destroy();
                        currentIptvHls = null;
                    }
                    showToast("Canale temporaneamente non disponibile.", "error");
                }
            }
        });

        currentIptvHls.on(Hls.Events.MANIFEST_PARSED, () => {
            video.play().catch(() => {});
        });
    } else {
        video.src = proxiedUrl;
        video.play().catch(() => {});
    }
}

window.closeIptvPlayer = function() {
    const modal = document.getElementById('iptv-player-modal');
    const video = document.getElementById('iptv-video');
    if (modal) modal.classList.add('hidden');
    if (currentIptvHls) {
        currentIptvHls.destroy();
        currentIptvHls = null;
    }
    if (video) {
        video.pause();
        video.removeAttribute('src');
    }
};

window.prevIptvChannel = function() {
    if (iptvChannelsCache.length === 0) return;
    currentIptvIndex = (currentIptvIndex - 1 + iptvChannelsCache.length) % iptvChannelsCache.length;
    playIptvChannel(iptvChannelsCache[currentIptvIndex]);
};

window.nextIptvChannel = function() {
    if (iptvChannelsCache.length === 0) return;
    currentIptvIndex = (currentIptvIndex + 1) % iptvChannelsCache.length;
    playIptvChannel(iptvChannelsCache[currentIptvIndex]);
};

// ═══════════════════════════════════════════════════════════════════
// Initialization & Preloader (Audio: 4.mp3)
// ═══════════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", async () => {
    const preloader = document.getElementById("preloader");
    const preloaderAudio = document.getElementById("preloader-audio");
    const preloaderStatus = document.getElementById("preloader-status");

    if (preloaderStatus) preloaderStatus.textContent = "Connessione server Tortuga TV...";

    let audioFinished = false;
    if (preloaderAudio) {
        preloaderAudio.volume = 1.0;
        preloaderAudio.addEventListener("ended", () => { audioFinished = true; }, { once: true });
        preloaderAudio.addEventListener("error", () => { audioFinished = true; }, { once: true });
        try {
            await preloaderAudio.play();
        } catch (e) {
            audioFinished = true;
        }
    } else {
        audioFinished = true;
    }

    // Initialize Home view
    try {
        router.navigate("home");
    } catch(e) {
        console.error("Home navigation error:", e);
    }

    if (!audioFinished && preloaderAudio) {
        await new Promise(res => {
            preloaderAudio.addEventListener("ended", res, { once: true });
            preloaderAudio.addEventListener("error", res, { once: true });
            setTimeout(res, 3500); // safety fallback
        });
    }

    if (preloader) {
        preloader.style.transition = "opacity 0.4s ease";
        preloader.style.opacity = "0";
        setTimeout(() => {
            preloader.style.display = "none";
            if (preloaderAudio) {
                preloaderAudio.pause();
                preloaderAudio.removeAttribute("src");
            }
        }, 400);
    }
});

