"""
Tortuga Web / PC Edition - Unified Server (Flask Standalone)
Architettura Enterprise: Zero Client Leakage, Token HMAC, Smart Proxy HLS,
e compatibilitÃ  al 100% con tutte le logiche di Tortuga Music e Tortuga TV.
"""
import os
import sys
import json
import time
import re
import urllib.parse
from urllib.parse import urljoin, quote
import requests
from flask import Flask, request, jsonify, send_from_directory, Response, send_file
from flask_cors import CORS

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    FRONTEND_DIR, STATIC_DIR, DATA_DIR, TV_DOWNLOADS_DIR, MUSIC_DOWNLOADS_DIR,
    SERVER_HOST, SERVER_PORT, DEBUG_MODE, SITE_PASSWORD
)
from security import apply_security_headers, sanitize_error
from db import (
    get_cached_item, set_cached_item, save_user_backup, load_user_backup,
    get_cache_stats, clear_cache,
    save_watch_progress, get_watch_progress_list, delete_watch_progress,
    check_auth_lockout, record_auth_attempt
)
from scrapers.youtube_engine import search_youtube, extract_stream_url, get_trending
from scrapers.streaming_community import sc_session
from scrapers.anime_unity import au_session
from scrapers.iptv import get_channels_list
from smart_proxy import handle_smart_playlist, serve_local_file_with_range
from download_manager import (
    tv_download_mgr, start_music_download, get_music_downloads, music_download_tasks
)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.config['JSON_AS_ASCII'] = False
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.after_request
def after_request_handler(response):
    return apply_security_headers(response)

# â”€â”€â”€ Static Web Interface â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/")
def route_index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/tv")
@app.route("/tv.html")
def route_tv():
    # Se presente nella cartella frontend, serve tv.html
    tv_file = os.path.join(FRONTEND_DIR, "tv.html")
    if os.path.exists(tv_file):
        return send_from_directory(FRONTEND_DIR, "tv.html")
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route('/<path:filename>')
def serve_root_files(filename):
    if filename.startswith('api/'):
        return jsonify({"error": "Endpoint API non trovato"}), 404
    # Controlla in frontend/ e poi in static/
    fpath = os.path.join(FRONTEND_DIR, filename)
    if os.path.exists(fpath) and os.path.isfile(fpath):
        return send_from_directory(FRONTEND_DIR, filename)
    fpath_static = os.path.join(STATIC_DIR, filename)
    if os.path.exists(fpath_static) and os.path.isfile(fpath_static):
        return send_from_directory(STATIC_DIR, filename)
    return jsonify({"error": "File non trovato"}), 404

# â”€â”€â”€ Search Dispatcher (Musica, Film, Serie TV, Anime) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/search")
def api_search():
    provider = request.args.get("provider")
    query = request.args.get("q", "").strip()
    
    if not query:
        return jsonify({"results": [], "tracks": []})
        
    if provider:
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

    # Default: YouTube Music & Video
    mode = request.args.get('mode', 'music')
    limit = int(request.args.get('limit', 20))
    tracks = search_youtube(query, mode=mode, limit=limit)
    return jsonify({"tracks": tracks})

def get_client_ip():
    """Identifica l'indirizzo IP del client rispettando i reverse proxy (Cloudflare/Nginx)."""
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"

# â”€â”€â”€ YouTube Music & Video Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/audio_proxy")
def api_audio_proxy():
    raw_url = request.args.get("url")
    if not raw_url:
        return jsonify({"error": "Parametro URL mancante"}), 400
    
    ua = request.args.get("ua")
    if not ua:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        
    headers = {
        'User-Agent': ua,
        'Accept': '*/*',
        'Accept-Encoding': 'identity;q=1, *;q=0',
    }
    range_header = request.headers.get('Range')
    if range_header:
        headers['Range'] = range_header
        
    import requests
    upstream = None
    try:
        upstream = requests.get(raw_url, headers=headers, stream=True, timeout=12)
        
        # Self-Healing: Se YouTube risponde con errore (403, 410, 404, 500), auto-recupero immediato
        if upstream.status_code >= 400:
            vid = request.args.get("vid")
            if not vid:
                # Prova ad estrarre l'id dal parametro raw_url
                m = re.search(r"[?&]id=([a-zA-Z0-9_-]{11})", raw_url) or re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", raw_url)
                if m:
                    vid = m.group(1)
            
            if vid:
                mode = request.args.get("mode", "music")
                quality = request.args.get("quality", "high")
                target_url = f"https://www.youtube.com/watch?v={vid}"
                fresh = extract_stream_url(target_url, mode=mode, quality=quality, force_refresh=True)
                if fresh and fresh.get("stream_url"):
                    if fresh.get("user_agent"):
                        headers['User-Agent'] = fresh['user_agent']
                    try:
                        upstream.close()
                    except Exception:
                        pass
                    upstream = requests.get(fresh["stream_url"], headers=headers, stream=True, timeout=12)

        resp_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Expose-Headers': 'Content-Range, Content-Length, Accept-Ranges',
            'Accept-Ranges': 'bytes'
        }
        for h in ['Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges']:
            if upstream and h in upstream.headers:
                resp_headers[h] = upstream.headers[h]

        # Generator protetto per evitare errori BrokenPipe o ERR_HTTP2_PROTOCOL_ERROR quando l'utente cambia canzone
        def generate_audio():
            try:
                for chunk in upstream.iter_content(chunk_size=65536):
                    if chunk:
                        yield chunk
            except BaseException:
                pass
            finally:
                try:
                    upstream.close()
                except BaseException:
                    pass

        status_code = upstream.status_code if upstream else 500
        return Response(
            generate_audio(),
            status=status_code,
            headers=resp_headers
        )
    except Exception as e:
        if upstream:
            try:
                upstream.close()
            except Exception:
                pass
        return jsonify({"error": "Errore streaming audio", "details": str(e)[:100]}), 502

@app.route("/api/stream")
def api_stream():
    url = request.args.get('url', '')
    vid_id = request.args.get('id', '')
    mode = request.args.get('mode', 'music')
    quality = request.args.get('quality', 'high')
    force_refresh = request.args.get('refresh') in ['1', 'true', 'True']
    
    if not url and vid_id:
        url = f"https://www.youtube.com/watch?v={vid_id}"
        
    if not url:
        return jsonify({"error": "Parametro URL o ID mancante"}), 400
        
    data = extract_stream_url(url, mode=mode, quality=quality, force_refresh=force_refresh)
    if not data or not data.get("stream_url"):
        return jsonify({"error": "Impossibile estrarre lo stream audio/video"}), 500
        
    # Proxy audio sicuro per evitare blocchi 403 IP-bound di Google Video
    ua_val = urllib.parse.quote(data.get("user_agent", ""), safe="")
    proxy_url = f"/api/audio_proxy?url={urllib.parse.quote(data['stream_url'], safe='')}&ua={ua_val}&vid={urllib.parse.quote(vid_id, safe='')}&mode={mode}&quality={quality}"
    data["audio_url"] = proxy_url
    data["direct_url"] = data["stream_url"]
    return jsonify(data)

# â”€â”€â”€ Auth Gate (Simpson Pre-preloader) Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/auth/verify", methods=["GET", "POST", "OPTIONS"])
def api_auth_verify():
    if request.method == "OPTIONS":
        return "", 204
    client_id = get_client_ip()
    is_locked, rem_secs, level, attempts = check_auth_lockout(client_id)
    if is_locked:
        mins = int(rem_secs // 60)
        secs = int(rem_secs % 60)
        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        return jsonify({
            "success": False,
            "locked": True,
            "lockout_seconds": rem_secs,
            "error": f"Troppi tentativi errati! Accesso bloccato per altri {time_str}."
        }), 429
        
    data = request.get_json(silent=True) or request.form or {}
    pwd = (data.get("password") or request.args.get("password") or "").strip()
    
    if pwd.strip().lower() == SITE_PASSWORD.strip().lower():
        record_auth_attempt(client_id, success=True)
        return jsonify({
            "success": True,
            "message": "Benvenuto in Tortuga Music!"
        })
    else:
        res = record_auth_attempt(client_id, success=False)
        if res.get("locked"):
            dur_mins = int(res.get("remaining_seconds", 0) // 60)
            return jsonify({
                "success": False,
                "locked": True,
                "lockout_seconds": res.get("remaining_seconds"),
                "error": f"Password errata! Blocco di sicurezza attivo per {dur_mins} minuti."
            }), 429
        else:
            left = res.get("attempts_left", 0)
            return jsonify({
                "success": False,
                "locked": False,
                "attempts_left": left,
                "error": f"Password errata! Tentativi rimasti prima del blocco: {left}"
            }), 401

@app.route("/api/auth/status")
def api_auth_status():
    client_id = get_client_ip()
    is_locked, rem_secs, level, attempts = check_auth_lockout(client_id)
    return jsonify({
        "locked": is_locked,
        "lockout_seconds": rem_secs,
        "attempts_used": attempts,
        "attempts_left": max(0, 3 - attempts) if not is_locked else 0
    })

# â”€â”€â”€ Watch Progress ("Continua a guardare") Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/watch_progress/save", methods=["GET", "POST", "OPTIONS"])
def api_watch_progress_save():
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(silent=True) or request.form
    if not data:
        return jsonify({"error": "Dati mancanti"}), 400
    success = save_watch_progress(data)
    return jsonify({"success": success})

@app.route("/api/watch_progress/list")
def api_watch_progress_list():
    limit = request.args.get("limit", 50, type=int)
    items = get_watch_progress_list(limit=limit)
    return jsonify({"items": items})

@app.route("/api/watch_progress/delete", methods=["GET", "POST", "OPTIONS"])
def api_watch_progress_delete():
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(silent=True) or request.form or {}
    media_id = data.get("media_id") or data.get("id") or request.args.get("media_id") or request.args.get("id")
    episode_id = data.get("episode_id") or request.args.get("episode_id")
    if not media_id:
        return jsonify({"error": "media_id mancante"}), 400
    success = delete_watch_progress(str(media_id), str(episode_id) if episode_id else None)
    return jsonify({"success": success})

@app.route("/api/trending")
def api_trending():
    mode = request.args.get('mode', 'music')
    limit = int(request.args.get('limit', 25))
    suggested = request.args.get('q', '').strip()
    tracks = get_trending(mode=mode, limit=limit)
    return jsonify({"tracks": tracks})

# â”€â”€â”€ Film, Serie TV & Anime Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/homepage")
def api_homepage():
    try:
        return jsonify(sc_session.get_homepage())
    except Exception as e:
        return jsonify(sanitize_error(e)), 500

@app.route("/api/new-releases")
def api_new_releases():
    try:
        return jsonify(sc_session.get_new_releases())
    except Exception as e:
        return jsonify(sanitize_error(e)), 500

@app.route("/api/explore")
def api_explore():
    filter_type = request.args.get("type", "movie")
    page = request.args.get("page", 1, type=int)
    try:
        return jsonify(sc_session.get_explore(filter_type, page))
    except Exception as e:
        return jsonify(sanitize_error(e)), 500

@app.route("/api/genre")
def api_genre():
    genre_name = request.args.get("name", "") or request.args.get("id", "")
    if not genre_name:
        return jsonify({"error": "Parametro genere mancante"}), 400
    try:
        return jsonify(sc_session.get_genre_titles(genre_name))
    except Exception as e:
        return jsonify(sanitize_error(e)), 500

@app.route("/api/media")
def api_media():
    provider = request.args.get("provider", "streamingcommunity")
    media_id = request.args.get("id")
    slug = request.args.get("slug", "")
    if not media_id:
        return jsonify({"error": "Parametro ID mancante"}), 400
    try:
        if provider == "animeunity":
            return jsonify(au_session.get_details(media_id))
        return jsonify(sc_session.get_details(media_id, slug))
    except Exception as e:
        return jsonify(sanitize_error(e)), 500

@app.route("/api/season")
def api_season():
    media_id = request.args.get("id")
    slug = request.args.get("slug", "")
    season_num = request.args.get("season_num")
    if not media_id or not season_num:
        return jsonify({"error": "Parametri stagione mancanti"}), 400
    try:
        return jsonify(sc_session.get_season(media_id, slug, season_num))
    except Exception as e:
        return jsonify(sanitize_error(e)), 500

@app.route("/api/episode")
def api_episode():
    provider = request.args.get("provider", "streamingcommunity")
    media_id = request.args.get("id")
    episode_id = request.args.get("episode_id")
    if not media_id:
        return jsonify({"error": "Parametro ID mancante"}), 400
    try:
        if provider == "animeunity":
            return jsonify(au_session.get_video_url(media_id, episode_id))
        ua = request.headers.get("User-Agent")
        return jsonify(sc_session.get_video_url(media_id, episode_id, ua))
    except Exception as e:
        return jsonify(sanitize_error(e)), 500

# â”€â”€â”€ Smart HLS Playlist & Video Stream Proxy â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/playlist")
@app.route("/api/playlist/<path:subpath>")
def api_playlist(subpath=None):
    token = request.args.get("token")
    raw_url = request.args.get("url")
    ref = request.args.get("ref")
    return handle_smart_playlist(token=token, direct_url=raw_url, direct_ref=ref)

# â”€â”€â”€ IPTV Live Channels â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/iptv/channels")
def api_iptv_channels():
    try:
        country = request.args.get("country")
        category = request.args.get("category")
        search = request.args.get("search")
        channels = get_channels_list(country=country, category=category, search=search)
        return jsonify({"channels": channels, "total": len(channels)})
    except Exception as e:
        return jsonify(sanitize_error(e)), 500

@app.route("/api/iptv/stream", methods=["GET", "OPTIONS"])
def api_iptv_stream():
    if request.method == "OPTIONS":
        resp = Response("", status=200)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "*"
        return resp

    target_url = request.args.get("url")
    ch_id = request.args.get("id")
    
    if not target_url and ch_id:
        channels = get_channels_list()
        target = next((c for c in channels if c["id"] == ch_id), None)
        if target:
            target_url = target.get("direct_url") or target.get("url")
            
    if not target_url:
        return jsonify({"error": "Parametro url o id mancante"}), 400

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': '*/*'
    }

    try:
        r = requests.get(target_url, headers=headers, stream=True, timeout=8, allow_redirects=True)
        if r.status_code not in (200, 206):
            return Response(f"Stream upstream error: {r.status_code}", status=r.status_code)

        content_type = r.headers.get("content-type", "").lower()
        first_chunk = next(r.iter_content(chunk_size=4096), b"")
        text_probe = first_chunk.decode("utf-8", errors="ignore")

        if "#EXTM3U" in text_probe or "mpegurl" in content_type:
            chunks = [first_chunk]
            for chk in r.iter_content(chunk_size=65536):
                if chk:
                    chunks.append(chk)
            full_text = (b"".join(chunks)).decode("utf-8", errors="ignore")
            
            rewritten_lines = []
            for line in full_text.splitlines():
                sline = line.strip()
                if not sline:
                    rewritten_lines.append("")
                elif 'URI=' in sline:
                    def rewrite_uri(m):
                        abs_u = urljoin(r.url, m.group(1))
                        return f'URI="/api/iptv/stream?url={quote(abs_u, safe="")}"'
                    rewritten_lines.append(re.sub(r'URI=["\']?([^"\'\s,>]+)["\']?', rewrite_uri, sline))
                elif sline.startswith("#"):
                    rewritten_lines.append(sline)
                else:
                    abs_u = urljoin(r.url, sline)
                    rewritten_lines.append(f"/api/iptv/stream?url={quote(abs_u, safe='')}")

            body = "\n".join(rewritten_lines)
            resp = Response(body, mimetype="application/vnd.apple.mpegurl")
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return resp
        else:
            def generate_media():
                try:
                    yield first_chunk
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            yield chunk
                except BaseException:
                    pass

            resp = Response(generate_media(), content_type=r.headers.get("content-type", "video/mp2t"))
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
            return resp
    except Exception as e:
        return Response(f"Proxy stream error: {str(e)}", status=502)

# â”€â”€â”€ Download Manager Video / TV â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/tv/download/start")
def api_tv_download_start():
    media_id = request.args.get("id")
    slug = request.args.get("slug", "")
    episode_id = request.args.get("episode_id")
    provider = request.args.get("provider", "streamingcommunity")
    title = request.args.get("title", "")
    image = request.args.get("image", "")
    file_name = request.args.get("fileName", "") or request.args.get("filename", "")
    
    if not media_id:
        return jsonify({"error": "Missing media id"}), 400
        
    res = tv_download_mgr.start_download(media_id, slug, episode_id, provider, title, image, file_name)
    return jsonify(res)

@app.route("/api/tv/download/status")
def api_tv_download_status():
    return jsonify(tv_download_mgr.get_all_status())

@app.route("/api/tv/download/cancel")
def api_tv_download_cancel():
    task_id = request.args.get("id")
    if not task_id:
        return jsonify({"error": "Missing id"}), 400
    success = tv_download_mgr.cancel_download(task_id)
    return jsonify({"success": success})

@app.route("/api/tv/download/delete")
def api_tv_download_delete():
    file_name = request.args.get("fileName") or request.args.get("filename")
    if not file_name:
        return jsonify({"error": "Missing fileName"}), 400
    success = tv_download_mgr.delete_download(file_name)
    return jsonify({"success": success})

@app.route('/api/local_file')
def api_local_file():
    fname = request.args.get('name')
    if not fname:
        return "Missing file name", 400
    clean_fname = os.path.basename(fname)
    fpath = os.path.join(TV_DOWNLOADS_DIR, clean_fname)
    return serve_local_file_with_range(fpath, "video/mp4")

# â”€â”€â”€ Download Manager Musica â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/download", methods=["POST"])
def api_download_music():
    data = request.json or {}
    track_id = data.get("id") or data.get("track_id")
    title = data.get("title", "Brano")
    artist = data.get("artist", "Artista")
    mode = data.get("mode", "music")
    thumbnail = data.get("thumbnail")
    
    if not track_id:
        return jsonify({"error": "ID brano mancante"}), 400
        
    task = start_music_download(track_id, title, artist, mode, thumbnail=thumbnail)
    return jsonify({"status": "started", "task": task})

@app.route("/api/offline_thumb/<path:filename>")
def api_offline_thumb(filename):
    clean_fname = os.path.basename(urllib.parse.unquote(filename))
    base_name = os.path.splitext(clean_fname)[0]
    
    # Cerca il file .jpg corrispondente nella cartella music o tv
    for d in [MUSIC_DOWNLOADS_DIR, TV_DOWNLOADS_DIR]:
        thumb_candidate = os.path.join(d, f"{base_name}.jpg")
        if os.path.exists(thumb_candidate):
            return send_file(thumb_candidate, mimetype="image/jpeg")
        exact_candidate = os.path.join(d, clean_fname)
        if os.path.exists(exact_candidate) and exact_candidate.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            return send_file(exact_candidate)

    # Se Ã¨ un file video (.mp4/.webm), prova a estrarre un fotogramma al volo con ffmpeg
    for d in [MUSIC_DOWNLOADS_DIR, TV_DOWNLOADS_DIR]:
        for ext in ['.mp4', '.webm', '.mkv']:
            vid_path = os.path.join(d, f"{base_name}{ext}")
            if os.path.exists(vid_path):
                out_jpg = os.path.join(d, f"{base_name}.jpg")
                try:
                    import subprocess
                    res = subprocess.run([
                        'ffmpeg', '-y', '-ss', '00:00:03', '-i', vid_path,
                        '-vframes', '1', '-q:v', '2', out_jpg
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                    if res.returncode == 0 and os.path.exists(out_jpg):
                        return send_file(out_jpg, mimetype="image/jpeg")
                except Exception:
                    pass

    return send_from_directory(STATIC_DIR, "icona_app.jpg")

@app.route("/api/download/status")
def api_download_status():
    task_id = request.args.get("id")
    if task_id:
        if task_id in music_download_tasks:
            return jsonify(music_download_tasks[task_id])
        alt_id = f"m_{task_id}"
        if alt_id in music_download_tasks:
            return jsonify(music_download_tasks[alt_id])
        clean_id = task_id[2:] if task_id.startswith("m_") else task_id
        if clean_id in music_download_tasks:
            return jsonify(music_download_tasks[clean_id])
    return jsonify({"tasks": list(music_download_tasks.values())})

@app.route("/api/offline")
def api_offline():
    tracks = get_music_downloads()
    return jsonify({"tracks": tracks, "files": tracks})

@app.route("/api/offline/delete", methods=["POST"])
def api_offline_delete():
    data = request.json or {}
    track_id = data.get("id")
    if not track_id:
        return jsonify({"error": "ID mancante"}), 400
    fname = os.path.basename(track_id)
    fpath = os.path.join(MUSIC_DOWNLOADS_DIR, fname)
    if os.path.exists(fpath):
        try: os.remove(fpath)
        except Exception: pass
    return jsonify({"success": True})

@app.route("/api/offline_file/<path:filename>")
def api_offline_file(filename):
    fname = os.path.basename(urllib.parse.unquote(filename))
    fpath = os.path.join(MUSIC_DOWNLOADS_DIR, fname)
    mimetype = "video/mp4" if fname.lower().endswith(".mp4") else "audio/mpeg"
    return serve_local_file_with_range(fpath, mimetype)

# â”€â”€â”€ Cache, Backup & Domain Refresh â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/cache/stats")
def api_cache_stats():
    return jsonify(get_cache_stats())

@app.route("/api/cache/clear", methods=["POST"])
def api_cache_clear():
    return jsonify({"success": clear_cache()})

@app.route("/api/backup/save", methods=["POST"])
def api_backup_save():
    data = request.json or {}
    key = data.get("key")
    value = data.get("value")
    if not key:
        return jsonify({"error": "Chiave mancante"}), 400
    success = save_user_backup(key, json.dumps(value) if not isinstance(value, str) else value)
    return jsonify({"success": success})

@app.route("/api/backup/load")
def api_backup_load():
    backup_data = load_user_backup()
    return jsonify({"backup": backup_data})

@app.route("/api/refresh-domains")
def api_refresh_domains():
    sc_ok = sc_session.init_session(force=True)
    au_ok = au_session.init_session(force=True)
    return jsonify({
        "status": "ok",
        "sc_domain": sc_session.domain,
        "au_domain": au_session.domain,
        "sc_initialized": sc_ok,
        "au_initialized": au_ok
    })

@app.route("/api/debug/sc_raw")
def api_debug_sc_raw():
    url = sc_session.domain
    try:
        r = sc_session.session.get(url, timeout=10)
        return jsonify({
            "url": r.url,
            "status": r.status_code,
            "headers": dict(r.headers),
            "has_inertia": 'data-page=' in r.text,
            "snippet": r.text[:1500]
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/debug/sc_search")
def api_debug_sc_search():
    q = request.args.get("q", "gladiatore")
    try:
        r = sc_session.session.get(f"{sc_session.domain}/it/search", params={"q": q}, timeout=10)
        return jsonify({
            "url": r.url,
            "status": r.status_code,
            "has_inertia": 'data-page=' in r.text,
            "snippet": r.text[:1500]
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/debug/ytdlp")
def api_debug_ytdlp():
    vid_id = request.args.get("id", "PTcc1CmEnxw")
    url = f"https://www.youtube.com/watch?v={vid_id}"
    import traceback
    try:
        from scrapers.youtube_engine import get_ytdlp
        yt_dlp = get_ytdlp()
        ydl_opts = {
            'format': '18/140/251/ba/b/best',
            'skip_download': True,
            'quiet': False,
            'extractor_args': {'youtube': {'player_client': ['android_vr', 'tv_embedded', 'ios', 'android', 'web']}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                "status": "success",
                "title": info.get("title"),
                "url": info.get("url")[:100] if info.get("url") else None,
                "formats_count": len(info.get("formats", []))
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        })

# â”€â”€â”€ Community Feedback & Suggestions System â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FEEDBACK_FILE = os.path.join(DATA_DIR, 'feedback.json')
DEFAULT_FEEDBACK = []

def load_feedback_data():
    if not os.path.exists(FEEDBACK_FILE):
        return []
    try:
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_feedback_data(data):
    try:
        with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

@app.route("/api/feedback", methods=["GET"])
def api_get_feedback():
    data = load_feedback_data()
    return jsonify({"status": "success", "feedback": data})

@app.route("/api/feedback", methods=["POST"])
def api_add_feedback():
    try:
        req = request.get_json(force=True, silent=True) or {}
        author = str(req.get("author", "")).strip()[:35] or "Anonimo"
        text = str(req.get("text", "")).strip()[:500]
        if not text or len(text) < 2:
            return jsonify({"status": "error", "error": "Il messaggio Ã¨ troppo breve."}), 400

        now = time.time()
        import datetime
        now_dt = datetime.datetime.fromtimestamp(now)
        date_str = f"{now_dt.strftime('%d/%m')} ore {now_dt.strftime('%H:%M')}"

        new_item = {
            "id": f"fb_{int(now * 1000)}",
            "author": author,
            "text": text,
            "likes": 0,
            "timestamp": now,
            "date_str": date_str
        }

        feed = load_feedback_data()
        feed.insert(0, new_item)
        save_feedback_data(feed)
        return jsonify({"status": "success", "item": new_item, "feedback": feed})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/feedback/like", methods=["POST"])
def api_like_feedback():
    try:
        req = request.get_json(force=True, silent=True) or {}
        item_id = str(req.get("id", "")).strip()
        if not item_id:
            return jsonify({"status": "error", "error": "ID mancante"}), 400
        
        feed = load_feedback_data()
        updated_likes = 0
        found = False
        for item in feed:
            if item.get("id") == item_id:
                item["likes"] = item.get("likes", 0) + 1
                updated_likes = item["likes"]
                found = True
                break
        
        if found:
            save_feedback_data(feed)
            return jsonify({"status": "success", "id": item_id, "likes": updated_likes})
        return jsonify({"status": "error", "error": "Messaggio non trovato"}), 404
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "online",
        "app": "Tortuga Music & TV (Web / PC Edition)",
        "version": "3.6-web",
        "timestamp": time.time()
    })

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    print(f"[Tortuga] Avvio Tortuga Music & TV Server su http://{SERVER_HOST}:{SERVER_PORT}")
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=DEBUG_MODE)
