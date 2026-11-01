"""
Tortuga Web / PC Edition - AnimeUnity Scraper Engine
Gestione sicura della sessione e token HLS mascherati con HMAC.
"""
import re
import html
import json
import urllib.parse
import requests
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_AU_DOMAIN, USER_AGENT
from security import generate_signed_stream_token

class AnimeUnitySession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        self.csrf_token = None
        self.initialized = False
        self.domain = DEFAULT_AU_DOMAIN

    def init_session(self, force=False):
        if self.initialized and not force:
            return True
        try:
            r = self.session.get(f"{self.domain}/", timeout=8)
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
            return {"error": "Inizializzazione sessione Anime fallita"}
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
                return {"error": "Inizializzazione sessione Anime fallita"}
            headers = {'X-CSRF-TOKEN': self.csrf_token} if self.csrf_token else {}
            r = self.session.get(f"{self.domain}/anime/{anime_id}-dummy", headers=headers, timeout=8)
            match = re.search(r'<video-player\s+[^>]*?:?anime=["\']({.*?})["\']', r.text)
            if not match:
                return {"error": "Informazioni anime non trovate"}
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
            return {"error": "Inizializzazione sessione Anime fallita"}
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
                    signed_token = generate_signed_stream_token(f"au_{anime_id}_{episode_id}", "anime", {
                        "raw_url": stream_url,
                        "ref": embed_url
                    })
                    return {
                        "stream_url": f"/api/playlist?token={signed_token}",
                        "download_url": download_url
                    }
                
                if download_url:
                    return {"stream_url": download_url, "iframe_url": embed_url}
                    
                return {"iframe_url": embed_url}
            return {"error": "Embed URL non trovato nella pagina anime"}
        except Exception as e:
            return {"error": str(e)}

au_session = AnimeUnitySession()
