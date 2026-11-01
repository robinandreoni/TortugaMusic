"""
Tortuga Web / PC Edition - YouTube & Music Engine (yt-dlp)
Estrazione flussi audio/video con protezione anti-403 e cache persistente.
"""
import re
import threading
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_cached_item, set_cached_item

_ytdlp_module = None
_ytdlp_lock = threading.Lock()

def get_ytdlp():
    """Caricamento sicuro e thread-safe del modulo yt_dlp."""
    global _ytdlp_module
    if _ytdlp_module is None:
        with _ytdlp_lock:
            if _ytdlp_module is None:
                import yt_dlp
                _ytdlp_module = yt_dlp
    return _ytdlp_module

def _clean_title(raw_title: str) -> str:
    """Rimuove parentesi e parole chiave pubblicitarie o ridondanti dai titoli dei brani."""
    t = re.sub(r'[\(\[\{].*?[\)\]\}]', '', raw_title)
    for kw in ['Official Video', 'Official Audio', 'Lyric Video', 'Visualizer',
               'Video Ufficiale', 'Audio Ufficiale', 'Testo', 'Lyrics', '4K', 'HD',
               'Remastered', r'ft\.', r'feat\.', 'HQ']:
        t = re.sub(kw, '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+', ' ', t).strip(' -_')
    return t or raw_title

def _split_artist_title(clean_title: str, uploader: str):
    """Separa artista e titolo da stringhe 'Artista - Titolo'."""
    parts = re.split(r'\s*[-–—:]\s*', clean_title, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return uploader or "Artista Sconosciuto", clean_title

def _get_best_thumbnail(entry: dict) -> str:
    """Seleziona l'immagine di copertina alla massima risoluzione disponibile."""
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

def _format_entry(entry: dict) -> dict:
    """Formatta l'oggetto traccia/video per il frontend."""
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

def search_youtube(query: str, mode: str = "music", limit: int = 20):
    """
    Esegue la ricerca su YouTube con cache persistente.
    Filtra i risultati per restituire brani puliti.
    """
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
        # Se modalità music, aggiunge termine mirato per evitare video irrilevanti
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

def extract_stream_url(url: str, mode: str = "music", quality: str = "high", force_refresh: bool = False):
    """
    Estrae l'URL di streaming diretto con strategia anti-403,
    supporto JS runtime (Node) e forwarding degli header ottimali.
    """
    cache_key = f"{mode}_{quality}_{url}"
    if not force_refresh:
        cached = get_cached_item('stream_cache', cache_key)
        if cached:
            return cached

    yt_dlp = get_ytdlp()
    
    if mode == "video":
        fmt = "18/22/best[ext=mp4][height<=720]/best[ext=mp4]/best" if quality == "high" else "18/best[ext=mp4][height<=480]/best[ext=mp4]/best"
    else:
        # Formato audio stabile: 140 (AAC 128k m4a) o 251 (Opus webm) con fallback
        fmt = "140/251/ba[ext=m4a]/ba/b/18/best"

    ydl_opts = {
        'format': fmt,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 15,
        'js_runtimes': {'node': {}},
        'extractor_args': {'youtube': {'player_client': ['web', 'android']}},
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            stream_url = info.get('url', '')
            selected_headers = info.get('http_headers', {})
            if not stream_url:
                fmts = info.get('formats', [])
                for f in reversed(fmts):
                    if f.get('url') and (f.get('acodec') != 'none' or mode == 'video'):
                        stream_url = f['url']
                        if f.get('http_headers'):
                            selected_headers = f['http_headers']
                        break
            
            result = {
                "stream_url": stream_url,
                "title": info.get('title', ''),
                "artist": info.get('uploader', ''),
                "thumbnail": _get_best_thumbnail(info),
                "duration": info.get('duration', 0),
                "ext": info.get('ext', 'm4a' if mode == 'music' else 'mp4'),
                "user_agent": selected_headers.get('User-Agent', ''),
                "http_headers": selected_headers
            }
            if stream_url:
                set_cached_item('stream_cache', cache_key, result, 7200) # 2 ore TTL
            return result
    except Exception as e:
        print(f"[Extract Stream Primary Error] {e}")
        try:
            fallback_opts = {
                'format': '140/ba/b/18/best' if mode == 'music' else '18/best',
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 15,
                'js_runtimes': {'node': {}},
            }
            with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_url = info.get('url', '')
                selected_headers = info.get('http_headers', {})
                if not stream_url and info.get('formats'):
                    for f in reversed(info['formats']):
                        if f.get('url') and (f.get('acodec') != 'none' or mode == 'video'):
                            stream_url = f['url']
                            if f.get('http_headers'):
                                selected_headers = f['http_headers']
                            break
                if stream_url:
                    result = {
                        "stream_url": stream_url,
                        "title": info.get('title', ''),
                        "artist": info.get('uploader', ''),
                        "thumbnail": _get_best_thumbnail(info),
                        "duration": info.get('duration', 0),
                        "ext": info.get('ext', 'mp4'),
                        "user_agent": selected_headers.get('User-Agent', ''),
                        "http_headers": selected_headers
                    }
                    set_cached_item('stream_cache', cache_key, result, 7200)
                    return result
        except Exception as e2:
            print(f"[Extract Stream Fallback Error] {e2}")
        return None

def get_trending(mode: str = "music", limit: int = 25):
    """Recupera le tendenze musicali / video in Italia."""
    query = "Classifica Musica Italia 2026 Novita" if mode == "music" else "Trending Video Italia 2026"
    return search_youtube(query, mode=mode, limit=limit)
