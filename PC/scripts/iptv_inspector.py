import requests
import re
from urllib.parse import urlparse

sources = [
    ("TVITALIA", "https://raw.githubusercontent.com/maginetweb-arch/TVITALIA/refs/heads/main/iptvit.m3u"),
    ("Free-TV Italy", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_italy.m3u8"),
    ("IPTV-org IT", "https://iptv-org.github.io/iptv/countries/it.m3u")
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.google.com/'
}

for src_name, src_url in sources:
    print(f"\n=== Analisi sorgente: {src_name} ===")
    try:
        r = requests.get(src_url, timeout=10)
        lines = r.text.splitlines()
        found = 0
        working = 0
        curr_name = ""
        for line in lines:
            line = line.strip()
            if line.startswith("#EXTINF:"):
                m = re.search(r',([^,]+)$', line)
                curr_name = m.group(1).strip() if m else "Unknown"
            elif line and not line.startswith("#") and curr_name:
                found += 1
                stream_url = line
                # Only test first 15 per source to see what works
                if found <= 15:
                    try:
                        sr = requests.get(stream_url, headers=headers, timeout=4, allow_redirects=True, stream=True)
                        is_ok = sr.status_code in (200, 206) and any(kw in sr.headers.get('content-type', '').lower() + sr.text[:100].lower() for kw in ['mpegurl', 'extm3u', 'video'])
                        if is_ok:
                            working += 1
                            print(f"  [OK 200] {curr_name} -> {stream_url[:65]}")
                        else:
                            print(f"  [FAIL {sr.status_code}] {curr_name} -> {stream_url[:65]}")
                    except Exception as ex:
                        print(f"  [ERR] {curr_name} -> {ex}")
                curr_name = ""
        print(f"Campione {src_name}: {working}/{min(found, 15)} canali funzionanti")
    except Exception as e:
        print(f"Errore caricamento {src_name}: {e}")
