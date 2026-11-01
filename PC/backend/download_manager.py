"""
Tortuga Web / PC Edition - Download Manager
Gestione dei download locali su PC per Film, Serie TV, Anime e Brani Musicali.
"""
import os
import sys
import re
import json
import time
import threading
import urllib.parse
import requests
import subprocess

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import TV_DOWNLOADS_DIR, MUSIC_DOWNLOADS_DIR, USER_AGENT
from db import get_db_conn
from scrapers.youtube_engine import get_ytdlp, _clean_title, _split_artist_title
from scrapers.streaming_community import sc_session, vix_strategy
from scrapers.anime_unity import au_session

class TVDownloadManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.tasks = {}
        self._load_saved_catalog()

    def _get_catalog_file(self):
        return os.path.join(TV_DOWNLOADS_DIR, "catalog.json")

    def _load_saved_catalog(self):
        try:
            cf = self._get_catalog_file()
            if os.path.exists(cf):
                with open(cf, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for item in saved:
                        file_path = os.path.join(TV_DOWNLOADS_DIR, item.get("fileName", ""))
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
                if v.get("status") == "completed" and os.path.exists(os.path.join(TV_DOWNLOADS_DIR, v.get("fileName", "")))
            ]
            with open(cf, "w", encoding="utf-8") as f:
                json.dump(completed_items, f, indent=2, ensure_ascii=False)
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

        out_path = os.path.join(TV_DOWNLOADS_DIR, task["fileName"])
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
                r = requests.get(direct_url, headers={'Referer': 'https://vixcloud.co/', 'User-Agent': USER_AGENT}, stream=True, timeout=15)
                total_len = int(r.headers.get('content-length', 0))
                dl = 0
                start_time = time.time()
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=256*1024):
                        if task.get("cancelled"):
                            raise Exception("Download annullato dall'utente")
                        if chunk:
                            f.write(chunk)
                            dl += len(chunk)
                            task["downloaded_bytes"] = dl
                            if total_len > 0:
                                task["progress"] = round((dl / total_len) * 100, 1)
                            elapsed = max(0.1, time.time() - start_time)
                            task["speed"] = f"{dl / (1024*1024*elapsed):.1f} MB/s"
            
            elif stream_url:
                full_stream_url = f"http://127.0.0.1:5000{stream_url}"
                cmd = [
                    'ffmpeg', '-y',
                    '-allowed_extensions', 'ALL',
                    '-i', full_stream_url,
                    '-map', '0:v:0',
                    '-map', '0:a:0?',
                    '-c', 'copy',
                    '-bsf:a', 'aac_adtstoasc',
                    tmp_path
                ]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                start_time = time.time()
                while proc.poll() is None:
                    if task.get("cancelled"):
                        proc.kill()
                        raise Exception("Download annullato dall'utente")
                    time.sleep(1)
                    if os.path.exists(tmp_path):
                        sz = os.path.getsize(tmp_path)
                        task["downloaded_bytes"] = sz
                        elapsed = max(0.1, time.time() - start_time)
                        task["speed"] = f"{sz / (1024*1024*elapsed):.1f} MB/s"
                        task["progress"] = min(99, int(elapsed * 2))
                if proc.returncode != 0:
                    err = proc.stderr.read().decode('utf-8', errors='ignore')
                    raise Exception(f"Errore download ffmpeg: {err[-200:]}")
            else:
                raise Exception("Nessun link di streaming valido")
                
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
                except Exception: pass

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
                
        file_path = os.path.join(TV_DOWNLOADS_DIR, file_name)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
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
                    fpath = os.path.join(TV_DOWNLOADS_DIR, fname)
                    if os.path.exists(fpath) and os.path.getsize(fpath) > 1024:
                        t["size"] = os.path.getsize(fpath)
                        completed.append(t)
                        seen_files.add(fname)
            
            if os.path.exists(TV_DOWNLOADS_DIR):
                for fname in os.listdir(TV_DOWNLOADS_DIR):
                    if fname.endswith(".mp4") and fname not in seen_files:
                        fpath = os.path.join(TV_DOWNLOADS_DIR, fname)
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

tv_download_mgr = TVDownloadManager()

# ─── Music Download Helpers ─────────────────────────────────────
music_download_tasks = {}

def start_music_download(track_id, title, artist, mode="music", thumbnail=None):
    task_id = f"m_{track_id}"
    task_info = {
        "id": task_id,
        "track_id": track_id,
        "title": title,
        "artist": artist,
        "mode": mode,
        "status": "downloading",
        "progress": "5%",
        "percent": 5,
        "eta": "Inizio download...",
        "speed": ""
    }
    music_download_tasks[task_id] = task_info
    music_download_tasks[track_id] = task_info
    
    def _music_worker():
        task = music_download_tasks[task_id]
        is_video = (mode == "video")
        target_dir = TV_DOWNLOADS_DIR if is_video else MUSIC_DOWNLOADS_DIR
        clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', f"{artist} - {title}")
        
        def ytdl_progress_hook(d):
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                if total > 0:
                    pct = round((downloaded / total) * 100, 1)
                    task["progress"] = f"{pct}%"
                    task["percent"] = pct
                spd = d.get('speed')
                if spd:
                    task["speed"] = f"{spd / (1024*1024):.1f} MB/s"
                eta = d.get('eta')
                if eta:
                    task["eta"] = f"{eta}s rimanenti"
                task["status"] = "downloading"
            elif d.get('status') == 'finished':
                task["progress"] = "100%"
                task["percent"] = 100
                task["status"] = "finished"

        try:
            yt_dlp = get_ytdlp()
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if is_video else 'bestaudio/best',
                'outtmpl': os.path.join(target_dir, f"{clean_name}.%(ext)s"),
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [ytdl_progress_hook]
            }
            url = f"https://www.youtube.com/watch?v={track_id}" if len(track_id) == 11 else track_id
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                ext = info.get('ext', 'mp4' if is_video else 'mp3')
                final_fname = f"{clean_name}.{ext}"
                
            # Salva copertina/screenshot video locale .jpg
            thumb_url = thumbnail or info.get('thumbnail')
            if (not thumb_url or 'icona_app' in thumb_url) and len(track_id) == 11 and not '.' in track_id:
                thumb_url = f"https://i.ytimg.com/vi/{track_id}/hqdefault.jpg"
                
            thumb_file = f"{clean_name}.jpg"
            thumb_path = os.path.join(target_dir, thumb_file)
            if thumb_url and not os.path.exists(thumb_path):
                try:
                    import urllib.request
                    urllib.request.urlretrieve(thumb_url, thumb_path)
                except Exception:
                    pass
                    
            final_thumb = f"/api/offline_thumb/{urllib.parse.quote(thumb_file)}" if os.path.exists(thumb_path) else (thumb_url or f"https://i.ytimg.com/vi/{track_id}/hqdefault.jpg")

            # Registra su SQLite
            with get_db_conn() as conn:
                conn.cursor().execute('''
                    INSERT OR REPLACE INTO offline_tracks (id, title, artist, mode, filename, thumbnail, duration, downloaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (track_id, title, artist, mode, final_fname, final_thumb, info.get('duration', 0), time.time()))
                conn.commit()
                
            task["status"] = "finished"
            task["progress"] = "100%"
            task["percent"] = 100
            task["fileName"] = final_fname
        except Exception as e:
            task["status"] = "error"
            task["error"] = str(e)
            
    threading.Thread(target=_music_worker, daemon=True).start()
    return task_info

def get_music_downloads():
    tracks = []
    seen = set()
    try:
        with get_db_conn() as conn:
            rows = conn.cursor().execute("SELECT id, title, artist, mode, filename, thumbnail, duration FROM offline_tracks").fetchall()
            for r in rows:
                t_id, title, artist, mode, fname, thumb, dur = r
                target_dir = TV_DOWNLOADS_DIR if mode == "video" else MUSIC_DOWNLOADS_DIR
                fpath = os.path.join(target_dir, fname)
                if not os.path.exists(fpath):
                    alt_dir = MUSIC_DOWNLOADS_DIR if mode == "video" else TV_DOWNLOADS_DIR
                    if os.path.exists(os.path.join(alt_dir, fname)):
                        fpath = os.path.join(alt_dir, fname)
                if os.path.exists(fpath):
                    base_name = os.path.splitext(fname)[0]
                    local_jpg = os.path.join(os.path.dirname(fpath), f"{base_name}.jpg")
                    if os.path.exists(local_jpg):
                        resolved_thumb = f"/api/offline_thumb/{urllib.parse.quote(os.path.basename(local_jpg))}"
                    elif thumb and not "icona_app" in thumb and not "tartuga" in thumb:
                        resolved_thumb = thumb
                    elif len(t_id) == 11 and not "." in t_id:
                        resolved_thumb = f"https://i.ytimg.com/vi/{t_id}/hqdefault.jpg"
                    else:
                        resolved_thumb = f"/api/offline_thumb/{urllib.parse.quote(fname)}"

                    tracks.append({
                        "id": t_id,
                        "title": title,
                        "artist": artist,
                        "mode": mode,
                        "filename": fname,
                        "thumbnail": resolved_thumb,
                        "duration": dur,
                        "url": f"/api/offline_file/{urllib.parse.quote(fname)}"
                    })
                    seen.add(fname)
    except Exception:
        pass
        
    for scan_dir, default_mode in [(MUSIC_DOWNLOADS_DIR, "music"), (TV_DOWNLOADS_DIR, "video")]:
        if os.path.exists(scan_dir):
            for fname in os.listdir(scan_dir):
                if fname not in seen and (fname.endswith('.mp3') or fname.endswith('.m4a') or fname.endswith('.webm') or fname.endswith('.mp4')):
                    base_name = os.path.splitext(fname)[0]
                    local_jpg = os.path.join(scan_dir, f"{base_name}.jpg")
                    if os.path.exists(local_jpg):
                        resolved_thumb = f"/api/offline_thumb/{urllib.parse.quote(os.path.basename(local_jpg))}"
                    else:
                        resolved_thumb = f"/api/offline_thumb/{urllib.parse.quote(fname)}"

                    raw_title = base_name
                    art, tit = _split_artist_title(raw_title, "Offline")
                    is_vid = fname.endswith('.mp4') or fname.endswith('.webm')
                    tracks.append({
                        "id": fname,
                        "title": tit,
                        "artist": art,
                        "mode": "video" if is_vid else default_mode,
                        "filename": fname,
                        "thumbnail": resolved_thumb,
                        "duration": 0,
                        "url": f"/api/offline_file/{urllib.parse.quote(fname)}"
                    })
                    seen.add(fname)
    return tracks
