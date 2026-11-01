"""
Tortuga Web / PC Edition - Smart HLS Manifest & Stream Proxy
Implementa:
1. Zero Client Leakage: I token firmati HMAC nascondono completamente gli URL sorgente.
2. Zero Bandwidth Overload: I manifest m3u8 (2KB) vengono elaborati al volo;
3. Supporto Range Requests (HTTP 206) per seeking istantaneo avanti/indietro.
"""
import os
import sys
import re
import urllib.parse
from flask import Response, request, send_file
import requests
import cloudscraper

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import USER_AGENT, TV_DOWNLOADS_DIR, MUSIC_DOWNLOADS_DIR
from security import verify_signed_stream_token, generate_signed_stream_token
from scrapers.streaming_community import vix_strategy

_scraper_instance = None
def get_scraper():
    global _scraper_instance
    if _scraper_instance is None:
        try:
            _scraper_instance = cloudscraper.create_scraper()
        except Exception:
            _scraper_instance = requests.Session()
            _scraper_instance.headers.update({'User-Agent': USER_AGENT})
    return _scraper_instance

def handle_smart_playlist(token: str, direct_url: str = None, direct_ref: str = None):
    """
    Elabora i manifest HLS (.m3u8) o i segmenti video (.ts).
    Verifica il token firmato HMAC, estrae la sorgente protetta,
    applica le strategie VixCloud e maschera i link interni.
    """
    raw_url = None
    ref = "https://vixcloud.co/"
    
    if token:
        payload = verify_signed_stream_token(token)
        if not payload:
            return Response("Token di streaming non valido o scaduto", status=403)
        ext = payload.get("ext", {})
        raw_url = ext.get("raw_url")
        ref = ext.get("ref", "https://vixcloud.co/")
        
    elif direct_url:
        raw_url = direct_url
        ref = direct_ref or "https://vixcloud.co/"

    if not raw_url:
        return Response("URL sorgente mancante", status=400)

    headers = {
        'Origin': 'https://vixcloud.co',
        'Referer': ref,
        'Accept': '*/*',
        'User-Agent': USER_AGENT
    }

    is_master = ('playlist/' in raw_url and 'type=' not in raw_url and '.ts' not in raw_url and not raw_url.endswith('.key'))
    s = get_scraper()

    try:
        if is_master:
            base_url = vix_strategy.strip_strategy_params(raw_url)
            r = None
            used_url = base_url
            for st_idx in vix_strategy.get_ordered_strategies():
                try_url = vix_strategy.apply_strategy(base_url, st_idx)
                try:
                    r_try = s.get(try_url, headers=headers, stream=True, timeout=10)
                    if r_try.status_code == 200 and ("#EXTM3U" in r_try.text[:200] or 'mpegurl' in r_try.headers.get('content-type', '').lower()):
                        vix_strategy.report_success(st_idx)
                        r = r_try
                        used_url = try_url
                        break
                except Exception:
                    pass
            if not r or r.status_code != 200:
                return Response("Impossibile recuperare la playlist master", status=502)
        else:
            r = s.get(raw_url, headers=headers, stream=True, timeout=10)
            if r.status_code == 403:
                s = cloudscraper.create_scraper()
                r = s.get(raw_url, headers=headers, stream=True, timeout=10)

            if r.status_code != 200:
                return Response(r.content, status=r.status_code)
        effective_url = getattr(r, 'url', None) or used_url

        content_type = r.headers.get('content-type', '')
        # Un manifest M3U8 inizia sempre con #EXTM3U e non è un file .ts o una chiave .key
        is_binary = (
            '.ts' in raw_url or 
            raw_url.endswith('.key') or 
            'type=key' in raw_url or 
            len(r.content) == 16 or
            'video/mp2t' in content_type.lower() or
            'octet-stream' in content_type.lower()
        )
        is_playlist = not is_binary and (r.content.strip().startswith(b'#EXTM3U') or 'mpegurl' in content_type.lower() or raw_url.endswith('.m3u8'))

        if is_playlist:
            text = r.content.decode('utf-8', errors='ignore')
            rewritten = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith('#EXT-X-KEY:'):
                    def repl_key(m):
                        u = m.group(1)
                        if not u.startswith('http'):
                            u = urllib.parse.urljoin(effective_url, u)
                        t = generate_signed_stream_token("key", "hls_key", {"raw_url": u, "ref": ref})
                        return f'URI="/api/playlist/enc.key?token={t}"'
                    line = re.sub(r'URI=[\'"](.*?)[\'"]', repl_key, line)
                    rewritten.append(line)
                elif line.startswith('#EXT-X-MEDIA:'):
                    def repl_media(m):
                        u = m.group(1)
                        if not u.startswith('http'):
                            u = urllib.parse.urljoin(effective_url, u)
                        t = generate_signed_stream_token("seg", "hls_seg", {"raw_url": u, "ref": ref})
                        if 'SUBTITLE' in line or '.vtt' in u:
                            return f'URI="/api/playlist/sub.vtt?token={t}"'
                        else:
                            return f'URI="/api/playlist/sub.m3u8?token={t}"'
                    line = re.sub(r'URI=[\'"](.*?)[\'"]', repl_media, line)
                    rewritten.append(line)
                elif not line.startswith('#'):
                    if not line.startswith('http'):
                        line = urllib.parse.urljoin(effective_url, line)
                    token_line = generate_signed_stream_token("seg", "hls_seg", {"raw_url": line, "ref": ref})
                    if '.vtt' in line or 'subtitle' in line:
                        rewritten.append(f"/api/playlist/sub.vtt?token={token_line}")
                    elif '.m3u8' in line or 'type=' in line or 'rendition=' in line:
                        rewritten.append(f"/api/playlist/sub.m3u8?token={token_line}")
                    else:
                        rewritten.append(f"/api/playlist/seg.ts?token={token_line}")
                else:
                    rewritten.append(line)
                    
            resp = Response("\n".join(rewritten), mimetype="application/vnd.apple.mpegurl")
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Cache-Control'] = 'no-cache, no-store'
            return resp
            
        else:
            # Segmento video (.ts), chiave AES (.key), sottotitolo (.vtt) o altro file binario
            seg_ct = content_type
            if '.vtt' in raw_url or 'vtt' in seg_ct.lower():
                seg_ct = 'text/vtt; charset=utf-8'
            elif not seg_ct or 'mpegurl' in seg_ct.lower() or 'text' in seg_ct.lower():
                seg_ct = 'application/octet-stream' if (raw_url.endswith('.key') or len(r.content) == 16) else 'video/mp2t'
            resp_headers = {
                'Content-Type': seg_ct,
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'public, max-age=3600'
            }
            if 'Content-Length' in r.headers:
                resp_headers['Content-Length'] = r.headers['Content-Length']
            return Response(r.content, headers=resp_headers)

    except Exception as e:
        return Response(f"Errore proxy: {str(e)[:80]}", status=500)

def serve_local_file_with_range(file_path: str, mimetype: str):
    """
    Gestione avanzata delle richieste HTTP 206 Partial Content
    per permettere lo scrub / seeking avanti e indietro istantaneo nel player.
    """
    if not os.path.exists(file_path):
        return Response("File non trovato", status=404)
        
    return send_file(file_path, mimetype=mimetype, conditional=True)
