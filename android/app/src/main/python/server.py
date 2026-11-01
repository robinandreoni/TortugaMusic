"""
Tortuga Music & Tortuga TV v3.0 - Unified Backend Server (Python/Flask)
- Motore di estrazione audio/video da YouTube via yt-dlp con Cache SQLite persistente.
- Motore di streaming film/serie/anime da StreamingCommunity & AnimeUnity con VixCloud Adaptive Strategy.
- Download Manager in background per tracce musicali, video e produzioni TV.
"""

from flask import Flask, request, jsonify, send_from_directory, Response, send_file
import os, sys, json, threading, time, traceback, sqlite3, re, random, html, urllib.parse
import requests, urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── CloudScraper Safe Loader ───────────────────────────────────
_scraper_lock = threading.Lock()
_scraper_created_at = time.time()
_SCRAPER_TTL = 1800  # 30 mins
_cached_scraper = None

def get_scraper(force_new=False):
    global _cached_scraper, _scraper_created_at
    with _scraper_lock:
        if force_new or _cached_scraper is None or (time.time() - _scraper_created_at) > _SCRAPER_TTL:
            try:
                import cloudscraper
                _cached_scraper = cloudscraper.create_scraper()
            except Exception as e:
                print(f"[CloudScraper Fallback] {e}")
                s = requests.Session()
                s.verify = False
                s.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
                })
                _cached_scraper = s
            _scraper_created_at = time.time()
    return _cached_scraper

# ─── Global HTTP Session ────────────────────────────────────────
http_requests = requests.Session()
http_requests.verify = False
http_requests.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
})

# ─── Flask App ──────────────────────────────────────────────────
_base_dir = os.environ.get("HOME", os.path.dirname(os.path.abspath(__file__)))
static_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
app = Flask(__name__, static_folder=static_folder_path, static_url_path="/static")
app.config['JSON_AS_ASCII'] = False

@app.route('/<path:filename>')
def serve_root_static(filename):
    if not filename.startswith('api/'):
        fpath = os.path.join(app.static_folder, filename)
        if os.path.exists(fpath) and os.path.isfile(fpath):
            return send_from_directory(app.static_folder, filename)
    return jsonify({"error": "Not Found"}), 404

# ─── Directories & Migrations ───────────────────────────────────
downloads_dir = os.path.join(_base_dir, 'downloads')
if not os.path.exists(downloads_dir):
    os.makedirs(downloads_dir, exist_ok=True)

tv_downloads_dir = os.path.join(_base_dir, 'TortugaTV_Downloads')
if not os.path.exists(tv_downloads_dir):
    os.makedirs(tv_downloads_dir, exist_ok=True)

def get_movies_dir():
    return tv_downloads_dir

def get_all_download_dirs():
    dirs = [downloads_dir]
    extra = [
        os.path.join(_base_dir, 'downloads'),
        os.path.join(os.path.dirname(__file__), 'downloads'),
        os.path.join('/data/data/com.TortugaMusic/files', 'downloads'),
        os.path.join('/data/user/0/com.TortugaMusic/files', 'downloads'),
        os.path.join('/sdcard/Music', 'TortugaMusic'),
        os.path.join('/sdcard/Download', 'TortugaMusic'),
    ]
    for d in extra:
        if os.path.exists(d) and d not in dirs:
            dirs.append(d)
    return dirs

def migrate_legacy_data():
    for leg_dir in get_all_download_dirs():
        try:
            if os.path.exists(leg_dir) and os.path.abspath(leg_dir) != os.path.abspath(downloads_dir):
                import shutil
                for fname in os.listdir(leg_dir):
                    src_f = os.path.join(leg_dir, fname)
                    dst_f = os.path.join(downloads_dir, fname)
                    if os.path.isfile(src_f) and not os.path.exists(dst_f):
                        shutil.copy2(src_f, dst_f)
                        print(f"[Migration] Copiato file ripristinato: {fname}")
        except Exception as e:
            print(f"[Migration Warning] {e}")

try:
    migrate_legacy_data()
except Exception:
    pass

# ─── SQLite Cache for YouTube Streams & User Data Backup ─────────
db_path = os.path.join(_base_dir, 'tortuga_cache.db')

def get_db_conn():
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass
    return conn

def init_db():
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS stream_cache (
                    cache_key TEXT PRIMARY KEY,
                    data_json TEXT,
                    expires_at REAL,
                    created_at REAL
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key TEXT PRIMARY KEY,
                    data_json TEXT,
                    expires_at REAL,
                    created_at REAL
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS user_data_backup (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at REAL
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS offline_tracks (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    artist TEXT,
                    mode TEXT,
                    filename TEXT,
                    thumbnail TEXT,
                    duration REAL,
                    downloaded_at REAL
                )
            ''')
            conn.commit()
    except Exception as e:
        print(f"[Cache DB Init Error] {e}")

try:
    init_db()
except Exception:
    pass

def get_cached_item(table, key):
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute(f"SELECT data_json, expires_at FROM {table} WHERE cache_key = ?", (key,))
            row = c.fetchone()
            if row:
                data_json, expires_at = row
                if time.time() < expires_at:
                    return json.loads(data_json)
                else:
                    c.execute(f"DELETE FROM {table} WHERE cache_key = ?", (key,))
                    conn.commit()
    except Exception as e:
        print(f"[Cache Read Error] {e}")
    return None

def set_cached_item(table, key, data, ttl_seconds):
    try:
        expires_at = time.time() + ttl_seconds
        created_at = time.time()
        data_json = json.dumps(data)
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute(f'''
                INSERT OR REPLACE INTO {table} (cache_key, data_json, expires_at, created_at)
                VALUES (?, ?, ?, ?)
            ''', (key, data_json, expires_at, created_at))
            conn.commit()
    except Exception as e:
        print(f"[Cache Write Error] {e}")

# ═══════════════════════════════════════════════════════════════════
# 1. TORTUGA MUSIC & VIDEO ENGINE (YouTube / yt-dlp)
# ═══════════════════════════════════════════════════════════════════

_ytdlp_module = None
_ytdlp_lock = threading.Lock()

def get_ytdlp():
    global _ytdlp_module
    if _ytdlp_module is None:
        with _ytdlp_lock:
            if _ytdlp_module is None:
                import yt_dlp
                _ytdlp_module = yt_dlp
    return _ytdlp_module

def _clean_title(raw_title):
    t = re.sub(r'[\(\[\{].*?[\)\]\}]', '', raw_title)
    for kw in ['Official Video', 'Official Audio', 'Lyric Video', 'Visualizer',
               'Video Ufficiale', 'Audio Ufficiale', 'Testo', 'Lyrics', '4K', 'HD',
               'Remastered', r'ft\.', r'feat\.', 'HQ']:
        t = re.sub(kw, '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+', ' ', t).strip(' -_')
    return t or raw_title

def _split_artist_title(clean_title, uploader):
    parts = re.split(r'\s*[-–—:]\s*', clean_title, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return uploader or "Artista Sconosciuto", clean_title

def _get_best_thumbnail(entry):
    thumbs = entry.get('thumbnails', [])
    if thumbs:
        for t in reversed(thumbs):
            url = t.get('url', '')
            if url and 'hqdefault' in url:
                return url
        for t in reversed(thumbs):
            url = t.get('url', '')
            if url and ('sqp=' in url or url.startswith('http')):
                return url
    return entry.get('thumbnail', '')

def _format_entry(entry):
    raw_title = entry.get('title', 'Sconosciuto')
    uploader = entry.get('uploader', '')
    clean_t = _clean_title(raw_title)
    artist, title = _split_artist_title(clean_t, uploader)
    
    thumb = _get_best_thumbnail(entry)
    duration = entry.get('duration', 0)
    video_id = entry.get('id', '')
    webpage_url = entry.get('webpage_url', f"https://www.youtube.com/watch?v={video_id}")
    
    return {
        "id": video_id,
        "title": title,
        "artist": artist,
        "thumbnail": thumb,
        "duration": duration,
        "url": webpage_url,
        "mode": "video" if entry.get('is_video') else "music"
    }

def search_youtube(query, mode="music", limit=20):
    cache_key = f"{mode}_{query.lower().strip()}_{limit}"
    cached = get_cached_item('search_cache', cache_key)
    if cached:
        return cached

    yt_dlp = get_ytdlp()
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 12,
        'extractor_args': {'youtube': {'player_client': ['android_vr', 'android', 'web']}},
    }
    
    q_strip = query.strip()
    if q_strip.startswith('http://') or q_strip.startswith('https://') or 'youtu.be/' in q_strip:
        search_q = q_strip
    elif len(q_strip) == 11 and not ' ' in q_strip and not ':' in q_strip:
        search_q = f"https://www.youtube.com/watch?v={q_strip}"
    else:
        search_q = f"ytsearch{limit}:{q_strip}"
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(search_q, download=False)
            if not res:
                return []
            
            entries = res.get('entries', []) if 'entries' in res else [res]
            tracks = []
            for e in entries:
                if e:
                    e['is_video'] = (mode == "video")
                    tracks.append(_format_entry(e))
            
            if tracks:
                set_cached_item('search_cache', cache_key, tracks, 3600)
            return tracks
    except Exception as e:
        print(f"[Search Error] {e}")
        # Fallback with simple search if custom clients failed
        try:
            fallback_opts = {
                'extract_flat': 'in_playlist',
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 15,
            }
            with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                res = ydl.extract_info(search_q, download=False)
                entries = res.get('entries', []) if res and 'entries' in res else ([res] if res else [])
                tracks = [_format_entry(e) for e in entries if e]
                if tracks:
                    set_cached_item('search_cache', cache_key, tracks, 1800)
                return tracks
        except Exception as e2:
            print(f"[Search Fallback Error] {e2}")
            return []

def extract_stream_url(url, mode="music", quality="high"):
    cache_key = f"{mode}_{quality}_{url}"
    cached = get_cached_item('stream_cache', cache_key)
    if cached:
        return cached

    yt_dlp = get_ytdlp()
    
    if mode == "video":
        if quality == "low":
            fmt = "18/best[ext=mp4][height<=480]/best[ext=mp4]/best"
        else:
            fmt = "22/18/best[ext=mp4][height<=720]/best[ext=mp4]/best"
    else:
        # Prioritize Format 18 (progressive MP4 with AAC 44.1kHz audio) to prevent 403 Forbidden
        if quality == "low":
            fmt = "18/ba[ext=m4a]/ba[ext=mp4]/ba/b/best"
        else:
            fmt = "18/ba[ext=m4a]/ba[ext=mp4]/ba/b/best"

    client_strategies = [
        ['android'],
        ['android', 'web'],
        ['android_vr', 'android'],
        ['web', 'mweb']
    ]

    result = None
    for client_list in client_strategies:
        ydl_opts = {
            'format': fmt,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 15,
            'noplaylist': True,
            'extractor_args': {'youtube': {'player_client': client_list}},
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    continue
                
                stream_url = info.get('url', '')
                if not stream_url:
                    continue
                
                thumb = _get_best_thumbnail(info)
                duration = info.get('duration', 0)
                clean_t = _clean_title(info.get('title', ''))
                artist, title = _split_artist_title(clean_t, info.get('uploader', ''))
                
                result = {
                    "audio_url": stream_url,
                    "thumbnail": thumb,
                    "duration": duration,
                    "title": title,
                    "artist": artist,
                    "mode": mode
                }
                
                # YouTube stream URLs expire in ~6h. Calculate TTL safely (max 3 hours)
                ttl = 3600 * 3
                if 'expire=' in stream_url:
                    try:
                        exp_match = re.search(r'expire=(\d+)', stream_url)
                        if exp_match:
                            exp_ts = int(exp_match.group(1))
                            ttl = max(120, min(10800, int(exp_ts - time.time() - 300)))
                    except Exception:
                        pass
                
                set_cached_item('stream_cache', cache_key, result, ttl)
                return result
        except Exception as e:
            print(f"[Stream Extract Strategy {client_list} Error] {e}")
            continue

    # Final fallback if specific format extraction failed
    try:
        fallback_opts = {
            'format': '18/bestaudio/b/best' if mode == 'music' else '18/best[ext=mp4]/best',
            'extractor_args': {'youtube': {'player_client': ['android']}},
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 20,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and info.get('url'):
                stream_url = info.get('url', '')
                thumb = _get_best_thumbnail(info)
                duration = info.get('duration', 0)
                clean_t = _clean_title(info.get('title', ''))
                artist, title = _split_artist_title(clean_t, info.get('uploader', ''))
                result = {
                    "audio_url": stream_url,
                    "thumbnail": thumb,
                    "duration": duration,
                    "title": title,
                    "artist": artist,
                    "mode": mode
                }
                set_cached_item('stream_cache', cache_key, result, 1800)
                return result
    except Exception as e:
        print(f"[Stream Fallback Error] {e}")

    return None

# ═══════════════════════════════════════════════════════════════════
# 2. TORTUGA TV ENGINE: StreamingCommunity, AnimeUnity & VixCloud
# ═══════════════════════════════════════════════════════════════════

class VixCloudStrategy:
    STRATEGIES = [
        "&h=1",
        "",
        "&h=1&scz=1",
        "&h=1&ub=1",
        "&b=1",
        "&scz=1",
        "&h=1&b=1&scz=1",
    ]
    def __init__(self):
        self._lock = threading.Lock()
        self._best_strategy_idx = 0
        self._last_success_time = 0
        self._fail_count = 0
        self._strategy_log = []

    def get_ordered_strategies(self):
        with self._lock:
            best = self._best_strategy_idx
        return [best] + [i for i in range(len(self.STRATEGIES)) if i != best]

    def report_success(self, strategy_idx):
        with self._lock:
            self._best_strategy_idx = strategy_idx
            self._last_success_time = time.time()
            self._fail_count = 0
            self._strategy_log.append((time.time(), strategy_idx, True))
            if len(self._strategy_log) > 50:
                self._strategy_log = self._strategy_log[-25:]

    def report_failure(self, strategy_idx):
        with self._lock:
            self._fail_count += 1
            self._strategy_log.append((time.time(), strategy_idx, False))

    def apply_strategy(self, base_url, strategy_idx):
        suffix = self.STRATEGIES[strategy_idx]
        if not suffix:
            return base_url
        if suffix.replace("&", "") in base_url:
            return base_url
        return base_url + suffix

    def strip_strategy_params(self, url):
        for param in ['&h=1', '&b=1', '&scz=1', '&ub=1']:
            url = url.replace(param, '')
        return url

vix_strategy = VixCloudStrategy()

class AnimeUnitySession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(http_requests.headers)
        self.csrf_token = None
        self.initialized = False
        self.domain = "https://www.animeunity.so"

    def init_session(self, force=False):
        if self.initialized and not force:
            return True
        try:
            r = self.session.get("https://www.animeunity.so/", timeout=8)
            self.domain = r.url.rstrip('/')
            match = re.search(r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', r.text)
            if match:
                self.csrf_token = match.group(1)
                self.initialized = True
                return True
            return False
        except Exception:
            return False

    def search(self, query):
        if not self.init_session():
            return {"error": "Failed to init AU session"}
        try:
            headers = {'X-CSRF-TOKEN': self.csrf_token}
            r = self.session.post(f"{self.domain}/livesearch", data={'title': query}, headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                records = data.get("records", data) if isinstance(data, dict) else data
                results = []
                for rec in records:
                    results.append({
                        "id": rec.get("id"),
                        "title": rec.get("title_eng") or rec.get("title_ita") or rec.get("title"),
                        "slug": rec.get("slug"),
                        "type": rec.get("type", "Anime"),
                        "year": rec.get("date", "").split("-")[0] if rec.get("date") else "N/A",
                        "episodes_count": rec.get("episodes_count"),
                        "score": rec.get("score"),
                        "image": rec.get("imageurl"),
                        "provider": "animeunity"
                    })
                return {"results": results}
            return {"error": f"Search failed: HTTP {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def get_details(self, anime_id):
        try:
            if not self.init_session():
                return {"error": "Failed to init AU session"}
            headers = {'X-CSRF-TOKEN': self.csrf_token} if self.csrf_token else {}
            r = self.session.get(f"{self.domain}/anime/{anime_id}-dummy", headers=headers, timeout=8)
            match = re.search(r'<video-player\s+[^>]*?:?anime=["\']({.*?})["\']', r.text)
            if not match:
                return {"error": "Could not extract anime info"}
            anime_data = json.loads(html.unescape(match.group(1)))
            
            episodes_match = re.search(r'\bepisodes=["\'](\[[\s\S]*?\])["\']', r.text)
            episodes_data = []
            if episodes_match:
                episodes_data = json.loads(html.unescape(episodes_match.group(1)))
            
            episodes = []
            for ep in episodes_data:
                episodes.append({
                    "id": ep.get("id"),
                    "number": ep.get("number"),
                    "scws_id": ep.get("scws_id"),
                    "file_name": ep.get("file_name"),
                    "created_at": ep.get("created_at")
                })
            
            return {
                "id": anime_data.get("id"),
                "title": anime_data.get("title_eng") or anime_data.get("title_ita"),
                "plot": anime_data.get("plot"),
                "type": anime_data.get("type"),
                "status": anime_data.get("status"),
                "score": anime_data.get("score"),
                "image": anime_data.get("imageurl"),
                "seasons": [{"name": "Stagione 1", "episodes": episodes}]
            }
        except Exception as e:
            return {"error": str(e)}

    def get_video_url(self, anime_id, episode_id):
        if not self.init_session():
            return {"error": "Failed to init AU session"}
        try:
            headers = {'X-CSRF-TOKEN': self.csrf_token} if self.csrf_token else {}
            r = self.session.get(f"{self.domain}/anime/{anime_id}-dummy/{episode_id}", headers=headers, timeout=8)
            embed_match = re.search(r'embed_url=["\']([^"\']+)["\']', r.text)
            if embed_match:
                embed_url = html.unescape(embed_match.group(1))
                r_embed = self.session.get(embed_url, headers={'Referer': f"{self.domain}/"}, timeout=8)
                
                url_match = re.search(r"url:\s*['\"]([^'\"]+)['\"]", r_embed.text)
                token_match = re.search(r"['\"]token['\"]:\s*['\"]([^'\"]+)['\"]", r_embed.text)
                expires_match = re.search(r"['\"]expires['\"]:\s*['\"]([^'\"]+)['\"]", r_embed.text)
                
                stream_url = ""
                if url_match and token_match and expires_match:
                    playlist_url = url_match.group(1)
                    token = token_match.group(1)
                    expires = expires_match.group(1)
                    sep = "&" if "?" in playlist_url else "?"
                    stream_url = f"{playlist_url}{sep}token={token}&expires={expires}&h=1"
                else:
                    master_match = re.search(r'window\.masterPlaylist\s*=\s*["\']([^"\']+)["\']', r_embed.text)
                    if master_match:
                        stream_url = master_match.group(1).replace('\\/', '/')
                
                dl_match = re.search(r'window\.downloadUrl\s*=\s*["\']([^"\']+)["\']', r_embed.text)
                download_url = dl_match.group(1) if dl_match else ""
                
                if stream_url:
                    proxied_url = f"/api/playlist?url={urllib.parse.quote(stream_url)}&ref={urllib.parse.quote(embed_url)}"
                    return {"stream_url": proxied_url, "download_url": download_url}
                if download_url:
                    return {"stream_url": download_url, "iframe_url": embed_url}
                
                return {"iframe_url": embed_url}
            return {"error": "Embed URL not found in Anime page"}
        except Exception as e:
            return {"error": str(e)}

class StreamingCommunitySession:
    GIST_RAW_URL = os.environ.get("GIST_DOMAINS_URL", "")
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(http_requests.headers)
        self.session.verify = False
        self.domain = "https://streamingcommunityz.rip"
        self.initialized = False
        self.last_init_time = 0
        self.last_error = None
        self._auto_refresh_started = False

    def _start_auto_refresh(self):
        if self._auto_refresh_started:
            return
        self._auto_refresh_started = True
        def _refresh_loop():
            while True:
                time.sleep(1800)
                try:
                    self.init_session(force=True)
                except Exception:
                    pass
        t = threading.Thread(target=_refresh_loop, daemon=True)
        t.start()

    def init_session(self, force=False):
        if self.initialized and not force:
            return True
            
        fallback_domain = "https://streamingcommunityz.rip"
        
        try:
            r = self.session.get(self.GIST_RAW_URL, timeout=6)
            if r.status_code == 200:
                raw_text = r.text.strip()
                if raw_text.startswith("http"):
                    try:
                        test_r = self.session.get(raw_text, timeout=6, verify=False)
                        inertia = re.search(r'data-page=["\']', test_r.text)
                        if inertia or 'streamingcommunity' in test_r.text.lower():
                            self.domain = raw_text.rstrip('/')
                            self.initialized = True
                            self.last_init_time = time.time()
                            self.last_error = None
                            self._start_auto_refresh()
                            return True
                    except Exception:
                        pass
        except Exception:
            pass

        discovery_urls = [
            fallback_domain,
            "https://streamingcommunityz.rip",
            "https://streamingcommunityz.team",
            "https://streamingcommunityz.taxi",
            "https://streamingcommunityz.tools",
            "https://streamingcommunityz.luxe",
            "https://streamingcommunityz.xyz",
            "https://streamingcommunityz.live",
        ]
        
        for d_url in discovery_urls:
            try:
                r = self.session.get(d_url, timeout=6, verify=False)
                if r.status_code == 200 and ('streamingcommunity' in r.text.lower() or 'data-page' in r.text):
                    self.domain = r.url.rstrip('/')
                    self.initialized = True
                    self.last_init_time = time.time()
                    self.last_error = None
                    self._start_auto_refresh()
                    return True
            except Exception:
                pass
                
        self.domain = fallback_domain
        self.initialized = True
        self.last_init_time = time.time()
        self._start_auto_refresh()
        return True

    def search(self, query):
        if not self.init_session():
            return {"error": "Failed to init SC session"}
        try:
            r = self.session.get(f"{self.domain}/it/search", params={'q': query}, timeout=8)
            inertia = re.search(r'data-page=["\']([^"\']+)["\']', r.text)
            if inertia:
                data = json.loads(html.unescape(inertia.group(1)))
                props = data.get("props", {})
                cdn_url = props.get("cdn_url", self.domain.replace("https://", "https://cdn."))
                records = props.get("titles", [])
                results = []
                for rec in records:
                    images = rec.get("images", [])
                    img_id = ""
                    bg_id = ""
                    if images:
                        poster = next((i for i in images if i.get("type") == "poster"), images[0])
                        img_id = poster.get("filename", "")
                        bg = next((i for i in images if i.get("type") in ["background", "cover"]), None)
                        if bg: bg_id = bg.get("filename", "")
                    
                    results.append({
                        "id": rec.get("id"),
                        "title": rec.get("name"),
                        "slug": rec.get("slug"),
                        "type": rec.get("type"),
                        "year": rec.get("last_air_date", "").split("-")[0] if rec.get("last_air_date") else "N/A",
                        "score": rec.get("score"),
                        "image": f"{cdn_url}/images/{img_id}" if img_id else "",
                        "background": f"{cdn_url}/images/{bg_id}" if bg_id else "",
                        "provider": "streamingcommunity"
                    })
                return {"results": results}
            return {"error": "No inertia data found"}
        except Exception as e:
            return {"error": str(e)}

    def get_details(self, media_id, slug=""):
        if not self.init_session():
            return {"error": "Init failed"}
        try:
            r = self.session.get(f"{self.domain}/it/titles/{media_id}-{slug}", timeout=8)
            inertia = re.search(r'data-page=["\']([^"\']+)["\']', r.text)
            if not inertia:
                return {"error": "Could not extract media info"}
            
            data = json.loads(html.unescape(inertia.group(1)))
            props = data.get("props", {})
            cdn_url = props.get("cdn_url", self.domain.replace("https://", "https://cdn."))
            title_obj = props.get("title", {})
            
            seasons_out = []
            if title_obj.get("type") == "tv":
                seasons = title_obj.get("seasons", [])
                for s in seasons:
                    episodes = []
                    loaded_season = props.get("loadedSeason", {})
                    if s.get("number") == loaded_season.get("number") and loaded_season.get("episodes"):
                        for ep in loaded_season.get("episodes"):
                            episodes.append({
                                "id": ep.get("id"),
                                "number": ep.get("number"),
                                "scws_id": ep.get("scws_id"),
                                "file_name": f"{title_obj.get('name')} S{s.get('number')}E{ep.get('number')}",
                                "name": ep.get("name")
                            })
                    seasons_out.append({
                        "id": s.get("id"),
                        "number": s.get("number"),
                        "name": f"Stagione {s.get('number')}",
                        "episodes": episodes
                    })
            else:
                seasons_out.append({
                    "name": "Film",
                    "episodes": [{
                        "id": title_obj.get("id"),
                        "number": 1,
                        "scws_id": title_obj.get("scws_id"),
                        "file_name": title_obj.get("name")
                    }]
                })
                
            images = title_obj.get("images", [])
            img_id = ""
            bg_id = ""
            if images:
                poster = next((i for i in images if i.get("type") == "poster"), images[0])
                img_id = poster.get("filename", "")
                bg = next((i for i in images if i.get("type") in ["background", "cover"]), None)
                if bg: bg_id = bg.get("filename", "")

            return {
                "id": title_obj.get("id"),
                "slug": title_obj.get("slug"),
                "title": title_obj.get("name"),
                "plot": title_obj.get("plot"),
                "type": title_obj.get("type"),
                "status": title_obj.get("status"),
                "score": title_obj.get("score"),
                "image": f"{cdn_url}/images/{img_id}" if img_id else "",
                "background": f"{cdn_url}/images/{bg_id}" if bg_id else "",
                "seasons": seasons_out
            }
        except Exception as e:
            return {"error": str(e)}

    def get_season(self, media_id, slug, season_num):
        if not self.init_session():
            return {"error": "Init failed"}
        try:
            url = f"{self.domain}/it/titles/{media_id}-{slug}/season-{season_num}"
            r = self.session.get(url, timeout=8)
            inertia = re.search(r'data-page=["\']([^"\']+)["\']', r.text)
            if not inertia:
                return {"error": "Could not extract season info"}
            
            data = json.loads(html.unescape(inertia.group(1)))
            props = data.get("props", {})
            title_obj = props.get("title", {})
            loaded_season = props.get("loadedSeason", {})
            
            if not loaded_season.get("episodes"):
                return {"error": "No episodes found for this season"}
                
            episodes = []
            for ep in loaded_season.get("episodes"):
                episodes.append({
                    "id": ep.get("id"),
                    "number": ep.get("number"),
                    "scws_id": ep.get("scws_id"),
                    "file_name": f"{title_obj.get('name')} S{loaded_season.get('number')}E{ep.get('number')}",
                    "name": ep.get("name")
                })
            
            return {
                "id": loaded_season.get("id"),
                "number": loaded_season.get("number"),
                "name": f"Stagione {loaded_season.get('number')}",
                "episodes": episodes
            }
        except Exception as e:
            return {"error": str(e)}

    def get_video_url(self, media_id, episode_id=None, ua=None):
        if not self.init_session():
            if not self.init_session(force=True):
                return {"error": "Init failed"}
        try:
            if ua:
                self.session.headers.update({"User-Agent": ua})
            else:
                self.session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"})
            
            if episode_id and str(episode_id) != str(media_id) and str(episode_id) != "movie":
                iframe_url = f"{self.domain}/it/iframe/{media_id}?episode_id={episode_id}"
            else:
                iframe_url = f"{self.domain}/it/iframe/{media_id}"
            
            r = self.session.get(iframe_url, timeout=8)
            vixcloud = re.search(r'src=["\']((https://vixcloud|https://vix)[^"\']+)["\']', r.text)
            if not vixcloud:
                return {"error": "Embed URL not found"}
            
            embed_url = html.unescape(vixcloud.group(1))
            r_embed = self.session.get(embed_url, headers={'Referer': self.domain}, timeout=8)
            
            url_match = re.search(r"url:\s*['\"]([^'\"]+)['\"]", r_embed.text)
            token_match = re.search(r"['\"]token['\"]:\s*['\"]([^'\"]+)['\"]", r_embed.text)
            expires_match = re.search(r"['\"]expires['\"]:\s*['\"]([^'\"]+)['\"]", r_embed.text)
            
            if url_match and token_match and expires_match:
                playlist_url = url_match.group(1)
                token = token_match.group(1)
                expires = expires_match.group(1)
                
                sep = "&" if "?" in playlist_url else "?"
                stream_url = f"{playlist_url}{sep}token={token}&expires={expires}"
                proxied_url = f"/api/playlist?url={urllib.parse.quote(stream_url)}&ref={urllib.parse.quote(embed_url)}"
                return {"stream_url": proxied_url}
            
            return {"error": "Could not extract stream URL from embed"}
        except Exception as e:
            return {"error": str(e)}

    def get_new_releases(self):
        data = self.get_homepage()
        return {"results": data.get("sliders", [{}])[0].get("titles", []) if data.get("sliders") else []}

    def get_homepage(self):
        if not self.init_session():
            return {"error": "Init failed"}
        try:
            r = self.session.get(self.domain, timeout=10)
            inertia = re.search(r'data-page=["\']([^"\']+)["\']', r.text)
            if not inertia:
                return {"error": "No inertia data"}
            data = json.loads(html.unescape(inertia.group(1)))
            props = data.get("props", {})
            cdn_url = props.get("cdn_url", self.domain.replace("https://", "https://cdn."))

            def format_titles(titles):
                out = []
                for t in titles:
                    images = t.get("images", [])
                    img_id = ""
                    bg_id = ""
                    if images:
                        poster = next((i for i in images if i.get("type") == "poster"), images[0])
                        img_id = poster.get("filename", "")
                        bg = next((i for i in images if i.get("type") in ["background", "cover"]), None)
                        if bg: bg_id = bg.get("filename", "")
                        
                    out.append({
                        "id": t.get("id"),
                        "title": t.get("name"),
                        "slug": t.get("slug"),
                        "type": t.get("type"),
                        "score": t.get("score"),
                        "image": f"{cdn_url}/images/{img_id}" if img_id else "",
                        "background": f"{cdn_url}/images/{bg_id}" if bg_id else "",
                        "provider": "streamingcommunity"
                    })
                return out

            sliders = []
            trending_data = self.get_explore("all", 1, endpoint="trending")
            latest_data = self.get_explore("all", 1, endpoint="latest")
            
            if trending_data.get("titles"):
                sliders.append({"label": "Titoli del momento", "titles": trending_data["titles"]})
            if latest_data.get("titles"):
                sliders.append({"label": "Aggiunti di recente", "titles": latest_data["titles"]})
                
            for sl in props.get("sliders", []):
                label = sl.get("label", "")
                if "Top 10" in label:
                    sliders.append({
                        "label": label,
                        "titles": format_titles(sl.get("titles", []))
                    })

            genres = []
            for g in props.get("genres", []):
                genres.append({
                    "id": g.get("id"),
                    "name": g.get("name")
                })
            
            hero = None
            if sliders and sliders[0].get("titles"):
                hero = sliders[0]["titles"][0]

            return {
                "hero": hero,
                "sliders": sliders,
                "genres": genres,
                "cdn_url": cdn_url
            }
        except Exception as e:
            return {"error": str(e)}

    def get_genre_titles(self, genre_name):
        if not self.init_session():
            return {"error": "Init failed"}
        try:
            genre_quoted = urllib.parse.quote(genre_name)
            r = self.session.get(f"{self.domain}/it/browse/genre?g={genre_quoted}", timeout=8)
            inertia = re.search(r'data-page=["\'](.*?)["\']', r.text, re.DOTALL)
            if not inertia:
                return {"titles": []}
            data = json.loads(html.unescape(inertia.group(1)))
            props = data.get("props", {})
            cdn_url = props.get("cdn_url", self.domain.replace("https://", "https://cdn."))
            records = props.get("titles", [])
            if isinstance(records, dict):
                records = records.get("data", [])
            results = []
            for t in records[:30]:
                images = t.get("images", [])
                img_id = ""
                bg_id = ""
                if images:
                    poster = next((i for i in images if i.get("type") == "poster"), images[0])
                    img_id = poster.get("filename", "")
                    bg = next((i for i in images if i.get("type") in ["background", "cover"]), None)
                    if bg: bg_id = bg.get("filename", "")
                    
                results.append({
                    "id": t.get("id"),
                    "title": t.get("name"),
                    "slug": t.get("slug"),
                    "type": t.get("type"),
                    "score": t.get("score"),
                    "image": f"{cdn_url}/images/{img_id}" if img_id else "",
                    "background": f"{cdn_url}/images/{bg_id}" if bg_id else "",
                    "provider": "streamingcommunity"
                })
            return {"titles": results}
        except Exception as e:
            return {"error": str(e)}

    def get_explore(self, filter_type, page, endpoint="trending"):
        if not self.init_session():
            return {"error": "Init failed"}
        try:
            r = self.session.get(f"{self.domain}/it/browse/{endpoint}?page={page}", timeout=8)
            inertia = re.search(r'data-page=["\']([^"\']+)["\']', r.text)
            if not inertia:
                return {"titles": [], "has_more": False}
            data = json.loads(html.unescape(inertia.group(1)))
            props = data.get("props", {})
            cdn_url = props.get("cdn_url", self.domain.replace("https://", "https://cdn."))
            titles_data = props.get("titles", {})
            records = titles_data.get("data", []) if isinstance(titles_data, dict) else titles_data
            
            results = []
            for t in records:
                if filter_type != "all":
                    if filter_type == "movie" and t.get("type") != "movie": continue
                    if filter_type == "tv" and t.get("type") != "tv": continue
                    if filter_type == "anime":
                        is_anime = any(g.get("name") == "Animazione" for g in t.get("genres", []))
                        if not is_anime: continue

                images = t.get("images", [])
                img_id = ""
                bg_id = ""
                if images:
                    poster = next((i for i in images if i.get("type") == "poster"), images[0])
                    img_id = poster.get("filename", "")
                    bg = next((i for i in images if i.get("type") in ["background", "cover"]), None)
                    if bg: bg_id = bg.get("filename", "")
                    
                results.append({
                    "id": t.get("id"),
                    "title": t.get("name"),
                    "slug": t.get("slug"),
                    "type": t.get("type"),
                    "score": t.get("score"),
                    "image": f"{cdn_url}/images/{img_id}" if img_id else "",
                    "background": f"{cdn_url}/images/{bg_id}" if bg_id else "",
                    "provider": "streamingcommunity"
                })
            
            has_more = False
            if isinstance(titles_data, dict) and titles_data.get("next_page_url"):
                has_more = True
            elif isinstance(records, list) and len(records) >= 60:
                has_more = True
                
            return {"titles": results, "has_more": has_more}
        except Exception as e:
            return {"error": str(e)}

au_session = AnimeUnitySession()
sc_session = StreamingCommunitySession()

# ─── TV Background Download Manager ─────────────────────────────

class BackgroundDownloadManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.tasks = {}
        self._load_saved_catalog()

    def _get_catalog_file(self):
        return os.path.join(get_movies_dir(), "catalog.json")

    def _load_saved_catalog(self):
        try:
            cf = self._get_catalog_file()
            if os.path.exists(cf):
                with open(cf, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for item in saved:
                        file_path = os.path.join(get_movies_dir(), item.get("fileName", ""))
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 1024:
                            item["status"] = "completed"
                            item["progress"] = 100
                            item["size"] = os.path.getsize(file_path)
                            self.tasks[item["id"]] = item
        except Exception:
            pass

    def _save_catalog(self):
        try:
            cf = self._get_catalog_file()
            completed_items = [
                v for v in self.tasks.values() 
                if v.get("status") == "completed" and os.path.exists(os.path.join(get_movies_dir(), v.get("fileName", "")))
            ]
            with open(cf, "w", encoding="utf-8") as f:
                json.dump(completed_items, f, indent=2)
        except Exception:
            pass

    def start_download(self, media_id, slug, episode_id, provider, title, image, file_name):
        clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', file_name or f"{title}.mp4")
        if not clean_name.endswith('.mp4'):
            clean_name += '.mp4'
            
        task_id = f"{provider}_{media_id}_{episode_id or 'movie'}"
        
        with self.lock:
            if task_id in self.tasks and self.tasks[task_id].get("status") == "downloading":
                return {"status": "already_downloading", "task": self.tasks[task_id]}
                
            task_info = {
                "id": task_id,
                "mediaId": media_id,
                "slug": slug,
                "episodeId": episode_id,
                "provider": provider,
                "title": title or clean_name,
                "image": image or "",
                "fileName": clean_name,
                "progress": 0,
                "status": "starting",
                "speed": "",
                "total_segments": 0,
                "current_segment": 0,
                "downloaded_bytes": 0,
                "error": None,
                "created_at": time.time()
            }
            self.tasks[task_id] = task_info

        t = threading.Thread(target=self._worker, args=(task_id,), daemon=True)
        t.start()
        return {"status": "started", "task": task_info}

    def _worker(self, task_id):
        with self.lock:
            task = self.tasks.get(task_id)
        if not task:
            return

        out_path = os.path.join(get_movies_dir(), task["fileName"])
        tmp_path = out_path + ".tmp"
        
        try:
            task["status"] = "downloading"
            task["progress"] = 1
            
            provider = task["provider"]
            media_id = task["mediaId"]
            episode_id = task["episodeId"]
            
            video_data = au_session.get_video_url(media_id, episode_id) if provider == "animeunity" else sc_session.get_video_url(media_id, episode_id)
                
            if "error" in video_data:
                raise Exception(video_data["error"])
                
            direct_url = video_data.get("download_url")
            stream_url = video_data.get("stream_url")
            
            if direct_url and direct_url.startswith("http") and ".mp4" in direct_url:
                r = http_requests.get(direct_url, headers={'Referer': 'https://vixcloud.co/'}, stream=True, timeout=15)
                total_len = int(r.headers.get('content-length', 0))
                dl = 0
                start_time = time.time()
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=256*1024):
                        if task.get("cancelled"):
                            raise Exception("Download annullato")
                        if chunk:
                            f.write(chunk)
                            dl += len(chunk)
                            task["downloaded_bytes"] = dl
                            if total_len > 0:
                                task["progress"] = round((dl / total_len) * 100, 1)
                            elapsed = max(0.1, time.time() - start_time)
                            task["speed"] = f"{dl / (1024*1024*elapsed):.1f} MB/s"
            
            elif stream_url:
                s = get_scraper()
                
                if "/api/playlist" in stream_url:
                    parsed = urllib.parse.urlparse(stream_url)
                    qs = urllib.parse.parse_qs(parsed.query)
                    inner_url = qs.get("url", [""])[0]
                    ref = qs.get("ref", ["https://vixcloud.co/"])[0]
                else:
                    inner_url = stream_url
                    ref = "https://vixcloud.co/"
                    
                headers = {'Origin': 'https://vixcloud.co', 'Referer': ref, 'Accept': '*/*'}
                base_url = vix_strategy.strip_strategy_params(inner_url)
                r_master = None
                used_url = base_url
                for st_idx in vix_strategy.get_ordered_strategies():
                    try_url = vix_strategy.apply_strategy(base_url, st_idx)
                    try:
                        r_try = s.get(try_url, headers=headers, timeout=10)
                        if r_try.status_code == 200 and ("#EXTM3U" in r_try.text[:200] or 'mpegurl' in r_try.headers.get('content-type', '').lower()):
                            vix_strategy.report_success(st_idx)
                            r_master = r_try
                            used_url = try_url
                            break
                    except Exception:
                        pass
                        
                if not r_master or r_master.status_code != 200:
                    raise Exception("Impossibile scaricare la master playlist")
                    
                master_text = r_master.text
                sub_lines = [line.strip() if line.strip().startswith('http') else urllib.parse.urljoin(used_url, line.strip()) 
                             for line in master_text.split('\n') if line.strip() and not line.strip().startswith('#')]
                
                if not sub_lines:
                    sub_lines = [used_url]
                    
                target_sub_url = sub_lines[0]
                r_sub = s.get(target_sub_url, headers=headers, timeout=10)
                if r_sub.status_code != 200:
                    raise Exception(f"Errore sub-playlist: {r_sub.status_code}")
                    
                sub_text = r_sub.text
                segments = [line.strip() if line.strip().startswith('http') else urllib.parse.urljoin(target_sub_url, line.strip()) 
                            for line in sub_text.split('\n') if line.strip() and not line.strip().startswith('#')]
                            
                if not segments:
                    raise Exception("Nessun segmento video trovato nella playlist")
                    
                task["total_segments"] = len(segments)
                task["progress"] = 2
                
                dl = 0
                start_time = time.time()
                with open(tmp_path, "wb") as outfile:
                    for i, seg_url in enumerate(segments):
                        if task.get("cancelled"):
                            raise Exception("Download annullato")
                        seg_ok = False
                        for retry in range(3):
                            try:
                                seg_r = s.get(seg_url, headers=headers, timeout=15)
                                if seg_r.status_code == 200:
                                    outfile.write(seg_r.content)
                                    dl += len(seg_r.content)
                                    seg_ok = True
                                    break
                                elif seg_r.status_code == 403:
                                    s = get_scraper(force_new=True)
                            except Exception:
                                time.sleep(0.5)
                        task["current_segment"] = i + 1
                        task["downloaded_bytes"] = dl
                        task["progress"] = round(((i + 1) / len(segments)) * 100, 1)
                        elapsed = max(0.1, time.time() - start_time)
                        task["speed"] = f"{dl / (1024*1024*elapsed):.1f} MB/s"
            else:
                raise Exception("Nessun URL video valido trovato per il download")
                
            if os.path.exists(out_path):
                os.remove(out_path)
            os.rename(tmp_path, out_path)
            
            task["status"] = "completed"
            task["progress"] = 100
            task["size"] = os.path.getsize(out_path)
            task["completed_at"] = time.time()
            self._save_catalog()
            
        except Exception as e:
            task["status"] = "error"
            task["error"] = str(e)
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except: pass

    def cancel_download(self, task_id):
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]["cancelled"] = True
                self.tasks[task_id]["status"] = "cancelled"
                return True
        return False

    def delete_download(self, file_name):
        with self.lock:
            target_id = None
            for tid, t in self.tasks.items():
                if t.get("fileName") == file_name:
                    target_id = tid
                    break
            if target_id:
                del self.tasks[target_id]
                
        file_path = os.path.join(get_movies_dir(), file_name)
        if os.path.exists(file_path):
            for _ in range(5):
                try:
                    os.remove(file_path)
                    break
                except Exception:
                    time.sleep(0.1)
        self._save_catalog()
        return True

    def get_all_status(self):
        with self.lock:
            active = []
            completed = []
            seen_files = set()
            for t in self.tasks.values():
                st = t.get("status")
                if st in ["downloading", "starting"]:
                    active.append(t)
                elif st == "completed":
                    fname = t.get("fileName", "")
                    fpath = os.path.join(get_movies_dir(), fname)
                    if os.path.exists(fpath) and os.path.getsize(fpath) > 1024:
                        t["size"] = os.path.getsize(fpath)
                        completed.append(t)
                        seen_files.add(fname)
            
            # Scan disk for any files not in tasks cache
            m_dir = get_movies_dir()
            if os.path.exists(m_dir):
                for fname in os.listdir(m_dir):
                    if fname.endswith(".mp4") and fname not in seen_files:
                        fpath = os.path.join(m_dir, fname)
                        if os.path.getsize(fpath) > 1024:
                            clean_title = fname.replace('.mp4', '').replace('_', ' ')
                            disk_task = {
                                "id": f"disk_{fname}",
                                "title": clean_title,
                                "fileName": fname,
                                "image": "/static/tartugalogo_transparent.png",
                                "status": "completed",
                                "progress": 100,
                                "size": os.path.getsize(fpath),
                                "completed_at": os.path.getmtime(fpath)
                            }
                            completed.append(disk_task)
                            self.tasks[disk_task["id"]] = disk_task
            return {"active": active, "completed": completed}

tv_download_mgr = BackgroundDownloadManager()

# ═══════════════════════════════════════════════════════════════════
# 3. HTTP ROUTES & ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.route("/")
def route_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route("/tv")
@app.route("/tv.html")
def route_tv():
    return send_from_directory(app.static_folder, 'tv.html')

# ─── Search Dispatcher (Music/Video or TV) ───────────────────────
@app.route("/api/search")
def api_search():
    provider = request.args.get("provider")
    
    # If provider is specified, forward to Tortuga TV search (SC / AU)
    if provider:
        query = request.args.get("q", "")
        if not query:
            return jsonify({"results": []})
        results = []
        if provider in ["all", "animeunity"]:
            try:
                au_res = au_session.search(query)
                if "results" in au_res:
                    results.extend(au_res["results"])
            except Exception:
                pass
        if provider in ["all", "streamingcommunity"]:
            try:
                sc_res = sc_session.search(query)
                if "results" in sc_res:
                    results.extend(sc_res["results"])
            except Exception:
                pass
        return jsonify({"results": results})

    # Default: YouTube Music / Video search
    q = request.args.get('q', '').strip()
    mode = request.args.get('mode', 'music')
    limit = int(request.args.get('limit', 20))
    if not q:
        return jsonify({"tracks": []})
    
    tracks = search_youtube(q, mode=mode, limit=limit)
    return jsonify({"tracks": tracks})

# ─── YouTube Music / Video Endpoints ────────────────────────────
@app.route("/api/stream")
def api_stream():
    url = request.args.get('url', '')
    vid_id = request.args.get('id', '')
    mode = request.args.get('mode', 'music')
    quality = request.args.get('quality', 'high')
    refresh = request.args.get('refresh', '0') == '1'
    
    if not url and vid_id:
        url = f"https://www.youtube.com/watch?v={vid_id}"
        
    if not url:
        return jsonify({"error": "Missing URL or video ID"}), 400
        
    if refresh:
        cache_key = f"{mode}_{quality}_{url}"
        try:
            with get_db_conn() as conn:
                conn.cursor().execute("DELETE FROM stream_cache WHERE cache_key = ?", (cache_key,))
                conn.commit()
        except Exception:
            pass

    data = extract_stream_url(url, mode=mode, quality=quality)
    if not data or not data.get("audio_url"):
        return jsonify({"error": "Impossibile estrarre il flusso multimediale"}), 500
        
    return jsonify(data)

@app.route("/api/trending")
def api_trending():
    mode = request.args.get('mode', 'music')
    limit = int(request.args.get('limit', 30))
    suggested_q = request.args.get('q', '').strip()
    
    if suggested_q:
        query = f"{suggested_q} top canzoni famose"
    else:
        trending_queries = [
            "top hits italia 2026",
            "hit radio italia",
            "musica tendenze italia",
            "nuovi singoli italia",
            "top canzoni mondiali 2026",
            "estate canzoni famose"
        ]
        query = random.choice(trending_queries)
        
    tracks = search_youtube(query, mode=mode, limit=limit)
    return jsonify({"tracks": tracks})

# ─── Tortuga TV Endpoints ───────────────────────────────────────
@app.route("/api/homepage")
def api_homepage():
    try:
        return jsonify(sc_session.get_homepage())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/new-releases")
def api_new_releases():
    try:
        return jsonify(sc_session.get_new_releases())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/explore")
def api_explore():
    filter_type = request.args.get("type", "movie")
    page = request.args.get("page", 1, type=int)
    try:
        return jsonify(sc_session.get_explore(filter_type, page))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/genre")
def api_genre():
    genre_name = request.args.get("name", "") or request.args.get("id", "")
    if not genre_name:
        return jsonify({"error": "Missing genre name"}), 400
    try:
        return jsonify(sc_session.get_genre_titles(genre_name))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/media")
def api_media():
    provider = request.args.get("provider", "streamingcommunity")
    media_id = request.args.get("id")
    slug = request.args.get("slug", "")
    if not media_id:
        return jsonify({"error": "Missing id"}), 400
    try:
        if provider == "animeunity":
            return jsonify(au_session.get_details(media_id))
        return jsonify(sc_session.get_details(media_id, slug))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/season")
def api_season():
    provider = request.args.get("provider", "streamingcommunity")
    media_id = request.args.get("id")
    slug = request.args.get("slug", "")
    season_num = request.args.get("season_num")
    if not media_id or not season_num:
        return jsonify({"error": "Missing params"}), 400
    try:
        return jsonify(sc_session.get_season(media_id, slug, season_num))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/episode")
def api_episode():
    provider = request.args.get("provider", "streamingcommunity")
    media_id = request.args.get("id")
    episode_id = request.args.get("episode_id")
    if not media_id:
        return jsonify({"error": "Missing id"}), 400
    try:
        if provider == "animeunity":
            return jsonify(au_session.get_video_url(media_id, episode_id))
        ua = request.args.get("ua")
        return jsonify(sc_session.get_video_url(media_id, episode_id, ua))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/playlist")
def api_playlist():
    url = request.args.get("url")
    ref = request.args.get("ref", "https://vixcloud.co/")
    if not url:
        return "Missing URL", 400
    
    headers = {
        'Origin': 'https://vixcloud.co',
        'Referer': ref,
        'Accept': '*/*',
    }
    is_master_playlist = ('playlist/' in url and 'type=' not in url and '.ts' not in url and not url.endswith('.key'))
    
    try:
        s = get_scraper()
        if is_master_playlist:
            base_url = vix_strategy.strip_strategy_params(url)
            for st_idx in vix_strategy.get_ordered_strategies():
                try_url = vix_strategy.apply_strategy(base_url, st_idx)
                try:
                    r = s.get(try_url, headers=headers, stream=True, timeout=10)
                    if r.status_code == 200 and ("#EXTM3U" in r.text[:200] or 'mpegurl' in r.headers.get('content-type', '').lower()):
                        vix_strategy.report_success(st_idx)
                        url = try_url
                        break
                except Exception:
                    pass
        else:
            r = s.get(url, headers=headers, stream=True, timeout=10)
            if r.status_code == 403:
                s = get_scraper(force_new=True)
                r = s.get(url, headers=headers, stream=True, timeout=10)

        content_type = r.headers.get('content-type', '')
        if 'mpegurl' in content_type.lower() or 'text' in content_type.lower() or url.endswith('.m3u8') or 'playlist' in url:
            text = r.content.decode('utf-8', errors='ignore')
            
            def replace_uri(match):
                inner = match.group(1)
                if not inner.startswith("http"):
                    inner = urllib.parse.urljoin(url, inner)
                return f'URI="/api/playlist?url={urllib.parse.quote(inner)}&ref={urllib.parse.quote(ref)}"'
                
            text = re.sub(r'''URI=['"](.*?)['"]''', replace_uri, text)
            
            rewritten = []
            for line in text.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    if not line.startswith("http"):
                        line = urllib.parse.urljoin(url, line)
                    rewritten.append(f"/api/playlist?url={urllib.parse.quote(line)}&ref={urllib.parse.quote(ref)}")
                else:
                    rewritten.append(line)
            resp = Response("\n".join(rewritten), mimetype="application/vnd.apple.mpegurl")
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp
        else:
            resp_headers = {
                'Content-Type': content_type or 'video/mp2t',
                'Access-Control-Allow-Origin': '*',
            }
            if 'Content-Length' in r.headers:
                resp_headers['Content-Length'] = r.headers['Content-Length']
            return Response(r.content, headers=resp_headers)
    except Exception as e:
        return str(e), 500

@app.route("/api/tv/download/start")
def api_tv_download_start():
    media_id = request.args.get("id")
    slug = request.args.get("slug", "")
    episode_id = request.args.get("episode_id")
    provider = request.args.get("provider", "streamingcommunity")
    title = request.args.get("title", "")
    image = request.args.get("image", "")
    filename = request.args.get("filename", "")
    if not media_id:
        return jsonify({"error": "Missing id"}), 400
    try:
        res = tv_download_mgr.start_download(media_id, slug, episode_id, provider, title, image, filename)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tv/download/status")
def api_tv_download_status():
    try:
        return jsonify(tv_download_mgr.get_all_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tv/download/cancel")
def api_tv_download_cancel():
    task_id = request.args.get("id")
    if not task_id:
        return jsonify({"error": "Missing task id"}), 400
    try:
        return jsonify({"success": tv_download_mgr.cancel_download(task_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tv/download/delete")
def api_tv_download_delete():
    filename = request.args.get("filename")
    if not filename:
        return jsonify({"error": "Missing filename"}), 400
    try:
        return jsonify({"success": tv_download_mgr.delete_download(filename)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/local_file')
def api_tv_local_file():
    filename = request.args.get('filename')
    if not filename:
        return jsonify({"error": "Missing filename"}), 400
    try:
        file_path = os.path.join(get_movies_dir(), filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
        return send_file(file_path, mimetype='video/mp4', conditional=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/refresh-domains")
def api_refresh_domains():
    try:
        get_scraper(force_new=True)
        success = sc_session.init_session(force=True)
        return jsonify({"success": success, "new_domain": sc_session.domain})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── YouTube Music / Video Offline Downloads ────────────────────
music_download_tasks = {}

@app.route("/api/download", methods=["POST"])
def api_music_download():
    data = request.json or {}
    vid_id = data.get("id", str(int(time.time())))
    title = data.get("title", "Brano")
    artist = data.get("artist", "")
    mode = data.get("mode", "music")
    thumbnail = data.get("thumbnail", "")
    duration = data.get("duration", 0)
    url = data.get("url") or f"https://www.youtube.com/watch?v={vid_id}"
    
    if vid_id in music_download_tasks and music_download_tasks[vid_id].get("status") == "downloading":
        return jsonify({"status": "already_downloading", "id": vid_id})
        
    clean_t = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', f"{artist} - {title}" if artist else title)
    clean_t = re.sub(r'_+', '_', clean_t).strip('_') or f"track_{vid_id}"
    ext = "mp4" if mode == "video" else "m4a"
    out_filename = f"{clean_t}.{ext}"
    out_filepath = os.path.join(downloads_dir, out_filename)
    
    music_download_tasks[vid_id] = {
        "id": vid_id,
        "title": title,
        "artist": artist,
        "mode": mode,
        "status": "downloading",
        "progress": "0%",
        "percent": 0,
        "eta": "Connessione...",
        "fileName": out_filename
    }
    
    def _dl_worker():
        try:
            yt_dlp = get_ytdlp()
            
            def progress_hook(d):
                if d.get('status') == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded = d.get('downloaded_bytes', 0)
                    if total > 0:
                        pct = round((downloaded / total) * 100, 1)
                        music_download_tasks[vid_id]["percent"] = pct
                        music_download_tasks[vid_id]["progress"] = f"{int(pct)}%"
                    speed = d.get('speed', 0)
                    if speed:
                        music_download_tasks[vid_id]["eta"] = f"{speed / (1024*1024):.1f} MB/s"
                elif d.get('status') == 'finished':
                    music_download_tasks[vid_id]["percent"] = 100
                    music_download_tasks[vid_id]["progress"] = "100%"
            
            out_tmpl = os.path.join(downloads_dir, f"{clean_t}.%(ext)s")
            
            if mode == "video":
                ydl_opts = {
                    'format': '22/18/best[ext=mp4]/best',
                    'outtmpl': out_tmpl,
                    'progress_hooks': [progress_hook],
                    'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                    'quiet': True,
                    'no_warnings': True,
                    'socket_timeout': 25,
                    'noplaylist': True,
                }
            else:
                ydl_opts = {
                    'format': '18/ba[ext=m4a]/ba[ext=mp4]/ba/b/best',
                    'outtmpl': out_tmpl,
                    'progress_hooks': [progress_hook],
                    'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                    'quiet': True,
                    'no_warnings': True,
                    'socket_timeout': 25,
                    'noplaylist': True,
                }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                actual_filename = ydl.prepare_filename(info)
                base_fname = os.path.basename(actual_filename)
                
                # Record track metadata in SQLite
                try:
                    with get_db_conn() as conn:
                        conn.cursor().execute('''
                            INSERT OR REPLACE INTO offline_tracks 
                            (id, title, artist, mode, filename, thumbnail, duration, downloaded_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (vid_id, title, artist, mode, base_fname, thumbnail, duration, time.time()))
                        conn.commit()
                except Exception as e:
                    print(f"[Offline DB Write Error] {e}")
                
                music_download_tasks[vid_id]["status"] = "finished"
                music_download_tasks[vid_id]["percent"] = 100
                music_download_tasks[vid_id]["progress"] = "100%"
                music_download_tasks[vid_id]["fileName"] = base_fname
                
        except Exception as e:
            print(f"[Download Worker Error] {e}")
            music_download_tasks[vid_id]["status"] = "error"
            music_download_tasks[vid_id]["error"] = str(e)
                
    threading.Thread(target=_dl_worker, daemon=True).start()
    return jsonify({"status": "started", "id": vid_id})

@app.route("/api/download/status")
def api_download_status():
    task_id = request.args.get("id")
    if task_id:
        task = music_download_tasks.get(task_id)
        if task:
            return jsonify(task)
        return jsonify({"status": "not_found", "progress": "0%", "percent": 0})
    return jsonify(tv_download_mgr.get_all_status())

@app.route("/api/offline")
def api_offline():
    req_mode = request.args.get("mode", "all")
    tracks = []
    seen_ids = set()
    
    # 1. From SQLite database
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT id, title, artist, mode, filename, thumbnail, duration FROM offline_tracks")
            for row in c.fetchall():
                t_id, title, artist, t_mode, fname, thumb, dur = row
                
                # Locate file in any of download directories
                found = False
                for d in get_all_download_dirs():
                    fpath = os.path.join(d, fname)
                    if os.path.exists(fpath) and os.path.getsize(fpath) > 1024:
                        found = True
                        break
                
                if found:
                    if req_mode in ["all", t_mode]:
                        tracks.append({
                            "id": t_id,
                            "title": title,
                            "artist": artist or "Offline",
                            "mode": t_mode,
                            "filename": fname,
                            "thumbnail": thumb or "/static/icona_app.jpg",
                            "duration": dur or 0,
                            "url": f"/api/offline_file/{urllib.parse.quote(fname)}",
                            "offline": True
                        })
                        seen_ids.add(fname)
                        seen_ids.add(t_id)
    except Exception as e:
        print(f"[Offline DB Read Error] {e}")
        
    # 2. Check disk for any orphan mp3/mp4/m4a files not in DB
    for d in get_all_download_dirs():
        if os.path.exists(d):
            try:
                for fname in os.listdir(d):
                    lower_name = fname.lower()
                    if (lower_name.endswith(".mp3") or lower_name.endswith(".mp4") or lower_name.endswith(".m4a") or lower_name.endswith(".aac")) and fname not in seen_ids:
                        is_video = lower_name.endswith(".mp4")
                        file_mode = "video" if is_video else "music"
                        if req_mode in ["all", file_mode]:
                            raw_title = fname.rsplit(".", 1)[0]
                            artist, title = _split_artist_title(raw_title, "Offline")
                            tracks.append({
                                "id": fname,
                                "title": title,
                                "artist": artist,
                                "mode": file_mode,
                                "filename": fname,
                                "thumbnail": "/static/icona_app.jpg",
                                "duration": 0,
                                "url": f"/api/offline_file/{urllib.parse.quote(fname)}",
                                "offline": True
                            })
                            seen_ids.add(fname)
            except Exception as e:
                print(f"[Scan Orphan Error in {d}] {e}")
                
    return jsonify({"tracks": tracks, "files": tracks})

@app.route("/api/offline/delete", methods=["POST"])
def api_offline_delete():
    data = request.json or {}
    track_id = data.get("id")
    if not track_id:
        return jsonify({"error": "Missing id"}), 400
    try:
        filename = None
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT filename FROM offline_tracks WHERE id = ?", (track_id,))
            row = c.fetchone()
            if row:
                filename = row[0]
            c.execute("DELETE FROM offline_tracks WHERE id = ?", (track_id,))
            conn.commit()
        
        if not filename:
            filename = track_id
            
        for d in get_all_download_dirs():
            fpath = os.path.join(d, filename)
            if os.path.exists(fpath):
                try: os.remove(fpath)
                except Exception: pass
        return jsonify({"status": "ok", "success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/offline_file/<path:filename>")
def api_offline_file(filename):
    fname = os.path.basename(urllib.parse.unquote(filename))
    for d in get_all_download_dirs():
        fpath = os.path.join(d, fname)
        if os.path.exists(fpath) and os.path.isfile(fpath):
            mimetype = "video/mp4" if fname.lower().endswith(".mp4") else "audio/mpeg"
            return send_file(fpath, mimetype=mimetype, conditional=True)
    return jsonify({"error": "File not found"}), 404

# ─── Cache Management ───────────────────────────────────────────
@app.route("/api/cache/stats")
def api_cache_stats():
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM stream_cache")
            streams_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM search_cache")
            searches_count = c.fetchone()[0]
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        return jsonify({
            "streams_cached": streams_count,
            "searches_cached": searches_count,
            "db_size_kb": round(db_size / 1024, 1)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cache/clear", methods=["POST"])
def api_cache_clear():
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM stream_cache")
            c.execute("DELETE FROM search_cache")
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── User Data Backup & Restore (Playlists, History, Settings) ──
@app.route("/api/backup/save", methods=["POST"])
def api_backup_save():
    data = request.json or {}
    key = data.get("key")
    value = data.get("value")
    if not key:
        return jsonify({"error": "Missing key"}), 400
    try:
        val_str = json.dumps(value) if not isinstance(value, str) else value
        with get_db_conn() as conn:
            conn.cursor().execute(
                "INSERT OR REPLACE INTO user_data_backup (key, value, updated_at) VALUES (?, ?, ?)",
                (key, val_str, time.time())
            )
            conn.commit()
        # Mirror to disk backup file
        backup_file = os.path.join(_base_dir, "tortuga_user_backup.json")
        existing = {}
        if os.path.exists(backup_file):
            try:
                with open(backup_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass
        existing[key] = value
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/backup/load")
def api_backup_load():
    result = {}
    try:
        with get_db_conn() as conn:
            rows = conn.cursor().execute("SELECT key, value FROM user_data_backup").fetchall()
            for k, v in rows:
                try:
                    result[k] = json.loads(v)
                except Exception:
                    result[k] = v
        backup_file = os.path.join(_base_dir, "tortuga_user_backup.json")
        if not result and os.path.exists(backup_file):
            with open(backup_file, "r", encoding="utf-8") as f:
                result = json.load(f)
    except Exception as e:
        print(f"[Backup Load Error] {e}")
    return jsonify({"backup": result})

# ─── IPTV LIVE TV CHANNELS (Nazionali & Internazionali) ────────
IPTV_CATALOG = [
    # ─── ITALIA (Nazionali & DTT) 🇮🇹 ───
    {
        "id": "rai-1", "name": "Rai 1 HD", "country": "IT", "flag": "🇮🇹", "category": "general", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Rai_1_-_Logo_2016.svg/260px-Rai_1_-_Logo_2016.svg.png",
        "url": "https://dash2.antik.sk/live/test_rai_uno_tizen/playlist.m3u8",
        "backup_url": "https://d3k8wzt41aflvx.cloudfront.net/RAI1/Live.m3u8"
    },
    {
        "id": "rai-2", "name": "Rai 2 HD", "country": "IT", "flag": "🇮🇹", "category": "general", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Rai_2_-_Logo_2016.svg/260px-Rai_2_-_Logo_2016.svg.png",
        "url": "https://d3k8wzt41aflvx.cloudfront.net/RAI2/Live.m3u8",
        "backup_url": "https://dash2.antik.sk/live/test_rai_due_tizen/playlist.m3u8"
    },
    {
        "id": "rai-3", "name": "Rai 3 HD", "country": "IT", "flag": "🇮🇹", "category": "general", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Rai_3_-_Logo_2016.svg/260px-Rai_3_-_Logo_2016.svg.png",
        "url": "https://dash2.antik.sk/live/test_rai_tre_tizen/playlist.m3u8",
        "backup_url": "https://d3k8wzt41aflvx.cloudfront.net/RAI3/Live.m3u8"
    },
    {
        "id": "rai-news24", "name": "Rai News 24 HD", "country": "IT", "flag": "🇮🇹", "category": "news", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Rai_News_24_-_Logo_2016.svg/260px-Rai_News_24_-_Logo_2016.svg.png",
        "url": "https://rainews1-live.akamaized.net/hls/live/598326/rainews1/rainews1/playlist.m3u8",
        "backup_url": "https://d3k8wzt41aflvx.cloudfront.net/RAINews24/Live.m3u8"
    },
    {
        "id": "rai-scuola", "name": "Rai Scuola HD", "country": "IT", "flag": "🇮🇹", "category": "documentary", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Rai_Scuola_-_Logo_2017.svg/260px-Rai_Scuola_-_Logo_2017.svg.png",
        "url": "https://d3k8wzt41aflvx.cloudfront.net/RAIScuola/Live.m3u8",
        "backup_url": ""
    },
    {
        "id": "rai-storia", "name": "Rai Storia HD", "country": "IT", "flag": "🇮🇹", "category": "documentary", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f8/Rai_Storia_-_Logo_2017.svg/260px-Rai_Storia_-_Logo_2017.svg.png",
        "url": "https://d3k8wzt41aflvx.cloudfront.net/RAIStoria/Live.m3u8",
        "backup_url": ""
    },
    {
        "id": "rtl-1025", "name": "RTL 102.5 TV HD", "country": "IT", "flag": "🇮🇹", "category": "music", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/RTL_102.5_logo_2018.svg/260px-RTL_102.5_logo_2018.svg.png",
        "url": "https://dd782ed59e2a4e86aabf6fc508674b59.msvdn.net/live/S97044836/tbbP8T1ZRPBL/playlist_video.m3u8",
        "backup_url": ""
    },
    {
        "id": "radio-freccia-tv", "name": "Radiofreccia HD", "country": "IT", "flag": "🇮🇹", "category": "music", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Radiofreccia_logo.png/260px-Radiofreccia_logo.png",
        "url": "https://dd782ed59e2a4e86aabf6fc508674b59.msvdn.net/live/S3160845/0tuSetc8UFkF/playlist_video.m3u8",
        "backup_url": ""
    },
    {
        "id": "radio-zeta-tv", "name": "Radio Zeta HD", "country": "IT", "flag": "🇮🇹", "category": "music", "quality": "1080p",
        "logo": "https://i.imgur.com/K2xLMin.png",
        "url": "https://dd782ed59e2a4e86aabf6fc508674b59.msvdn.net/live/S9346184/XEx1LqlYbNic/playlist_video.m3u8",
        "backup_url": ""
    },
    {
        "id": "radio-deejay-tv", "name": "Deejay TV HD", "country": "IT", "flag": "🇮🇹", "category": "music", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Deejay_TV_logo_2018.png/260px-Deejay_TV_logo_2018.png",
        "url": "https://4c4b867c89244861ac216426883d1ad0.msvdn.net/live/S85984808/sMO0tz9Sr2Rk/playlist.m3u8",
        "backup_url": ""
    },
    {
        "id": "radio-capital-tv", "name": "Radio Capital TiVu HD", "country": "IT", "flag": "🇮🇹", "category": "music", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/it/3/38/Radio_Capital_logo_%282020%29.svg",
        "url": "https://4c4b867c89244861ac216426883d1ad0.msvdn.net/live/S35394734/Z6U2wGoDYANk/playlist.m3u8",
        "backup_url": ""
    },
    {
        "id": "rds-social-tv", "name": "RDS Social TV HD", "country": "IT", "flag": "🇮🇹", "category": "music", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/RDS_logo.svg/260px-RDS_logo.svg.png",
        "url": "https://stream.rdstv.radio/out/v1/ec85f72b87f04555aa41d616d5be41dc/index.m3u8",
        "backup_url": ""
    },
    {
        "id": "pluto-cinema-it", "name": "Pluto TV Cinema Italiano", "country": "IT", "flag": "🇮🇹", "category": "movies", "quality": "720p",
        "logo": "https://images.pluto.tv/channels/65253fdf3fd33c00080214a3/colorLogoPNG_1773147329671.png",
        "url": "https://jmp2.uk/plu-65253fdf3fd33c00080214a3.m3u8",
        "backup_url": ""
    },
    {
        "id": "pluto-toto", "name": "Pluto TV Totò", "country": "IT", "flag": "🇮🇹", "category": "movies", "quality": "720p",
        "logo": "https://images.pluto.tv/channels/65253f9881f942000833ccd5/colorLogoPNG_1774617972809.png",
        "url": "https://jmp2.uk/plu-65253f9881f942000833ccd5.m3u8",
        "backup_url": ""
    },
    {
        "id": "pluto-serie-it", "name": "Pluto TV Serie TV", "country": "IT", "flag": "🇮🇹", "category": "movies", "quality": "720p",
        "logo": "https://images.pluto.tv/channels/65cb78b83a116800079e2e35/colorLogoPNG.png",
        "url": "https://jmp2.uk/plu-65cb78b83a116800079e2e35.m3u8",
        "backup_url": ""
    },
    {
        "id": "pluto-sport-it", "name": "Pluto TV Sport HD", "country": "IT", "flag": "🇮🇹", "category": "sport", "quality": "720p",
        "logo": "https://images.pluto.tv/channels/608030eff4b6f70007e1684c/colorLogoPNG_1746816937164.png",
        "url": "https://jmp2.uk/plu-608030eff4b6f70007e1684c.m3u8",
        "backup_url": ""
    },
    {
        "id": "rakuten-action", "name": "Rakuten TV Action Movies", "country": "IT", "flag": "🇮🇹", "category": "movies", "quality": "1080p",
        "logo": "https://i.imgur.com/Meew6eX.png",
        "url": "https://87f2e2e5e7624e3bad85da1ca2ed31a7.mediatailor.eu-west-1.amazonaws.com/v1/master/0547f18649bd788bec7b67b746e47670f558b6b2/production-LiveChannel-6067/master.m3u8",
        "backup_url": ""
    },
    {
        "id": "rakuten-comedy", "name": "Rakuten TV Commedia", "country": "IT", "flag": "🇮🇹", "category": "movies", "quality": "1080p",
        "logo": "https://i.imgur.com/Meew6eX.png",
        "url": "https://b8bc6c4b9be64bd6aeb3b92aa8521ed4.mediatailor.eu-west-1.amazonaws.com/v1/master/0547f18649bd788bec7b67b746e47670f558b6b2/production-LiveChannel-6184/master.m3u8",
        "backup_url": ""
    },
    {
        "id": "sanmarino-rtv", "name": "San Marino RTV HD", "country": "IT", "flag": "🇮🇹", "category": "general", "quality": "720p",
        "logo": "https://i.imgur.com/ZJSWusT.png",
        "url": "https://d2hrvno5bw6tg2.cloudfront.net/smrtv-ch01/smil:ch-01.smil/chunklist.m3u8",
        "backup_url": ""
    },
    {
        "id": "sanmarino-sport", "name": "San Marino RTV Sport", "country": "IT", "flag": "🇮🇹", "category": "sport", "quality": "720p",
        "logo": "https://i.imgur.com/PGm944g.png",
        "url": "https://d2hrvno5bw6tg2.cloudfront.net/smrtv-ch02/smil:ch-02.smil/master.m3u8",
        "backup_url": ""
    },
    {
        "id": "cusano-tv", "name": "Cusano Italia TV HD", "country": "IT", "flag": "🇮🇹", "category": "general", "quality": "720p",
        "logo": "https://i.imgur.com/fOluzuE.png",
        "url": "https://router.xdevel.com/video0s975363-69/stream/playlist.m3u8",
        "backup_url": ""
    },
    {
        "id": "bergamo-tv", "name": "Bergamo TV HD", "country": "IT", "flag": "🇮🇹", "category": "general", "quality": "1080p",
        "logo": "https://i.imgur.com/Np3RaKv.png",
        "url": "https://db142859fd5541b09de25d6507f1f2d3.msvdn.net/live/S17501676/oIxAsgEEA46M/playlist_dvr.m3u8",
        "backup_url": ""
    },

    # ─── STATI UNITI 🇺🇸 ───
    {
        "id": "cbs-news-us", "name": "CBS News 24/7", "country": "US", "flag": "🇺🇸", "category": "news", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/19/CBS_News_2020.svg/260px-CBS_News_2020.svg.png",
        "url": "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562de701/master.m3u8",
        "backup_url": ""
    },
    {
        "id": "nasa-tv-us", "name": "NASA TV HD", "country": "US", "flag": "🇺🇸", "category": "documentary", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/NASA_logo.svg/260px-NASA_logo.svg.png",
        "url": "https://ntv1.akamaized.net/hls/live/2014075/NASA-NTV1-HLS/master.m3u8",
        "backup_url": ""
    },
    {
        "id": "redbull-tv", "name": "Red Bull TV", "country": "US", "flag": "🇺🇸", "category": "sport", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Red_Bull_TV_logo.svg/260px-Red_Bull_TV_logo.svg.png",
        "url": "https://rbmn-live.akamaized.net/hls/live/590964/BoRB-AT/master.m3u8",
        "backup_url": ""
    },

    # ─── REGNO UNITO 🇬🇧 ───
    {
        "id": "sky-news-uk", "name": "Sky News UK HD", "country": "GB", "flag": "🇬🇧", "category": "news", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/86/Sky_News_logo_2020.svg/260px-Sky_News_logo_2020.svg.png",
        "url": "https://skynews-live.akamaized.net/hls/live/2034907/skynews_en/master.m3u8",
        "backup_url": ""
    },
    {
        "id": "gb-news-uk", "name": "GB News HD", "country": "GB", "flag": "🇬🇧", "category": "news", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/GB_News_logo.svg/260px-GB_News_logo.svg.png",
        "url": "https://gbnews.akamaized.net/hls/live/2035002/gbnews/master.m3u8",
        "backup_url": ""
    },

    # ─── SPAGNA 🇪🇸 ───
    {
        "id": "realmadrid-tv-es", "name": "Real Madrid TV", "country": "ES", "flag": "🇪🇸", "category": "sport", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/98/Real_Madrid_TV_logo.svg/260px-Real_Madrid_TV_logo.svg.png",
        "url": "https://rmtv.akamaized.net/hls/live/2043153/rmtv-es/master.m3u8",
        "backup_url": ""
    },

    # ─── FRANCIA 🇫🇷 ───
    {
        "id": "france24-fr", "name": "France 24 Français", "country": "FR", "flag": "🇫🇷", "category": "news", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/France_24_logo.svg/260px-France_24_logo.svg.png",
        "url": "https://france24-live-hls.akamaized.net/hls/live/2034914/f24_fr/master.m3u8",
        "backup_url": ""
    },
    {
        "id": "bfmtv-fr", "name": "BFM TV HD", "country": "FR", "flag": "🇫🇷", "category": "news", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/BFM_TV_logo_2019.svg/260px-BFM_TV_logo_2019.svg.png",
        "url": "https://bfmtv-live.akamaized.net/hls/live/2035005/bfmtv/master.m3u8",
        "backup_url": ""
    },

    # ─── GERMANIA 🇩🇪 ───
    {
        "id": "dw-news-de", "name": "Deutsche Welle HD", "country": "DE", "flag": "🇩🇪", "category": "news", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/75/Deutsche_Welle_logo.svg/260px-Deutsche_Welle_logo.svg.png",
        "url": "https://dwamdstream102.akamaized.net/hls/live/2015525/dwstream102/master.m3u8",
        "backup_url": ""
    },
    {
        "id": "tagesschau24-de", "name": "Tagesschau 24 HD", "country": "DE", "flag": "🇩🇪", "category": "news", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Tagesschau24_logo_2022.svg/260px-Tagesschau24_logo_2022.svg.png",
        "url": "https://tagesschau.akamaized.net/hls/live/2020101/tagesschau/master.m3u8",
        "backup_url": ""
    },

    # ─── GIAPPONE 🇯🇵 ───
    {
        "id": "nhk-world-jp", "name": "NHK World Japan HD", "country": "JP", "flag": "🇯🇵", "category": "news", "quality": "1080p",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/NHK_World-Japan.svg/260px-NHK_World-Japan.svg.png",
        "url": "https://nhkworld.akamaized.net/hls/live/2003459/nhkworld-tv/master.m3u8",
        "backup_url": ""
    }
]

@app.route("/api/iptv/channels")
def api_iptv_channels():
    country = request.args.get("country", "all").upper()
    category = request.args.get("category", "all").lower()
    search = request.args.get("q", "").lower().strip()
    
    filtered = IPTV_CATALOG
    if country != "ALL":
        filtered = [c for c in filtered if c.get("country") == country]
    if category != "all":
        filtered = [c for c in filtered if c.get("category") == category]
    if search:
        filtered = [c for c in filtered if search in c.get("name", "").lower() or search in c.get("category", "").lower()]
        
    return jsonify({
        "status": "ok",
        "count": len(filtered),
        "channels": filtered
    })

@app.route("/api/iptv/stream")
def api_iptv_stream():
    stream_url = request.args.get("url")
    if not stream_url:
        return "Missing stream url", 400
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': stream_url
        }
        r = http_requests.get(stream_url, headers=headers, timeout=10, allow_redirects=True)
        content_type = r.headers.get('content-type', 'application/vnd.apple.mpegurl')
        
        # Check if content is an HLS playlist
        if 'application/vnd.apple.mpegurl' in content_type or stream_url.endswith('.m3u8') or '#EXTM3U' in r.text[:50]:
            base_url = stream_url.rsplit('/', 1)[0] + '/'
            lines = r.text.splitlines()
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    if not stripped.startswith('http'):
                        abs_url = urllib.parse.urljoin(base_url, stripped)
                        new_lines.append(f"/api/iptv/stream?url={urllib.parse.quote(abs_url)}")
                    else:
                        new_lines.append(f"/api/iptv/stream?url={urllib.parse.quote(stripped)}")
                elif stripped.startswith('#EXT-X-KEY:') and 'URI="' in stripped:
                    key_uri = stripped.split('URI="')[1].split('"')[0]
                    abs_key = urllib.parse.urljoin(base_url, key_uri) if not key_uri.startswith('http') else key_uri
                    new_lines.append(stripped.replace(key_uri, f"/api/iptv/stream?url={urllib.parse.quote(abs_key)}"))
                else:
                    new_lines.append(line)
            
            resp = Response("\n".join(new_lines), mimetype='application/vnd.apple.mpegurl')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp
        else:
            resp = Response(r.content, mimetype=content_type)
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── Health Check ───────────────────────────────────────────────
@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "ok",
        "version": "3.6",
        "app": "Tortuga Music & Tortuga TV",
        "animeunity": "online" if getattr(au_session, 'initialized', False) else "standby",
        "streamingcommunity": "online" if getattr(sc_session, 'initialized', False) else "standby",
        "iptv_channels": len(IPTV_CATALOG)
    })

def run_server():
    app.run(host="0.0.0.0", port=5000, threaded=True, use_reloader=False)

if __name__ == "__main__":
    run_server()
