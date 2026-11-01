"""
Tortuga Web / PC Edition - IPTV Live Channels Engine (Nazionali & DTT)
Fornisce i canali live italiani con fallback e stream firmati HMAC.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security import generate_signed_stream_token

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
    }
]

import json
from urllib.parse import quote

CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "iptv_catalog.json")

def load_verified_catalog():
    """Carica il catalogo canali mondiali verificati da file JSON."""
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"[IPTV] Errore caricamento catalogo verificato: {e}")
    return IPTV_CATALOG

def get_channels_list(country=None, category=None, search=None):
    """
    Restituisce la libreria canali verificati per paese, categoria e ricerca
    con stream proxy /api/iptv/stream e URL diretti garantiti.
    """
    raw_channels = load_verified_catalog()
    safe_channels = []
    
    for ch in raw_channels:
        ch_country = ch.get("country", "IT")
        ch_category = ch.get("category", "general")
        ch_name = ch.get("name", "")
        
        if country and country != "all" and ch_country.upper() != country.upper():
            continue
        if category and category != "all" and ch_category.lower() != category.lower():
            continue
        if search:
            q = search.lower().strip()
            if q not in ch_name.lower() and q not in ch_category.lower():
                continue

        raw_url = ch.get("url", "")
        if not raw_url:
            continue

        signed_token = generate_signed_stream_token(ch["id"], "iptv", {
            "raw_url": raw_url,
            "backup_url": ch.get("backup_url", "")
        })
        
        safe_channels.append({
            "id": ch["id"],
            "name": ch_name,
            "country": ch_country,
            "flag": ch.get("flag") or "📺",
            "category": ch_category,
            "quality": ch.get("quality", "1080p"),
            "logo": ch.get("logo") or "/static/icona_app.jpg",
            "stream_url": f"/api/iptv/stream?url={quote(raw_url, safe='')}",
            "direct_url": raw_url,
            "backup_url": ch.get("backup_url", ""),
            "token_url": f"/api/playlist?token={signed_token}",
            "latency_ms": ch.get("latency_ms", 0)
        })
        
    return safe_channels
