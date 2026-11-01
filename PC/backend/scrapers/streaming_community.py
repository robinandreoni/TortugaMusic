"""
Tortuga Web / PC Edition - StreamingCommunity Scraper & VixCloud Adaptive Strategy
Tutti gli scraper e i token rimangono strettamente lato backend (Zero Client Leakage).
Include sistema di auto-scoperta dinamica tramite Hub Ufficiali (es. streaming-community.day),
verifica rigorosa anti-fake, auto-aggiornamento Gist e auto-recupero trasparente su errore.
"""
import re
import html
import json
import time
import urllib.parse
import threading
import requests
import cloudscraper
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GIST_DOMAINS_URL, DEFAULT_SC_DOMAIN, USER_AGENT, SC_HUBS, GIST_ID, GITHUB_GIST_TOKEN
from security import generate_signed_stream_token

class VixCloudStrategy:
    """Strategia euristica a 7 fasi per il bypass adattivo dei blocchi CDN VixCloud."""
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

class StreamingCommunitySession:
    GIST_RAW_URL = GIST_DOMAINS_URL
    
    def __init__(self):
        try:
            self.session = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
            )
        except Exception:
            self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        self.domain = DEFAULT_SC_DOMAIN
        self.initialized = False
        self.last_init_time = 0
        self.last_error = None
        self._lock = threading.Lock()
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

    def verify_domain(self, domain_url):
        """
        Verifica rigorosa: il dominio deve rispondere con HTTP 200 E contenere
        un attributo data-page Inertia valido con titoli/slider reali.
        Ignora falsi positivi, domini scaduti o pagine redirect/pubblicitarie.
        """
        if not domain_url or not domain_url.startswith("http"):
            return None
        clean_url = domain_url.rstrip('/')
        try:
            r = self.session.get(f"{clean_url}/it/browse/trending?page=1", timeout=7, allow_redirects=True)
            if r.status_code == 200 and 'data-page=' in r.text:
                m = re.search(r'data-page=["\']([^"\']+)["\']', r.text)
                if m:
                    data = json.loads(html.unescape(m.group(1)))
                    props = data.get("props", {})
                    titles = props.get("titles")
                    if titles:
                        # Estrae il dominio base effettivo post-redirect
                        final_base = re.match(r'(https?://[^/]+)', r.url)
                        return final_base.group(1) if final_base else clean_url
        except Exception:
            pass
            
        # Fallback secondario su homepage se browse/trending fallisce
        try:
            r = self.session.get(clean_url, timeout=7, allow_redirects=True)
            if r.status_code == 200 and 'data-page=' in r.text:
                m = re.search(r'data-page=["\']([^"\']+)["\']', r.text)
                if m:
                    data = json.loads(html.unescape(m.group(1)))
                    props = data.get("props", {})
                    if props.get("sliders") or props.get("genres"):
                        final_base = re.match(r'(https?://[^/]+)', r.url)
                        return final_base.group(1) if final_base else clean_url
        except Exception:
            pass
        return None

    def _update_remote_gist(self, new_domain):
        """Aggiorna in background il Gist GitHub per sincronizzare tutti i nodi (Mobile, Worker, PC)."""
        def _bg_update():
            if not GITHUB_GIST_TOKEN or not GIST_ID:
                return
            try:
                url = f"https://api.github.com/gists/{GIST_ID}"
                headers = {
                    "Authorization": f"Bearer {GITHUB_GIST_TOKEN}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
                r = requests.get(url, headers=headers, timeout=6)
                if r.status_code == 200:
                    files = r.json().get("files", {})
                    if files:
                        filename = list(files.keys())[0]
                        current_val = files[filename].get("content", "").strip()
                        if current_val != new_domain:
                            payload = {"files": {filename: {"content": new_domain}}}
                            requests.patch(url, headers=headers, json=payload, timeout=6)
            except Exception:
                pass
        threading.Thread(target=_bg_update, daemon=True).start()

    def fetch_from_hubs(self):
        """
        Scansiona gli hub ufficiali di annunci (es. streaming-community.day)
        che pubblicano il link attivo ufficiale in tempo reale.
        """
        for hub in SC_HUBS:
            try:
                r = self.session.get(hub, timeout=8, allow_redirects=True)
                if r.status_code == 200:
                    matches = re.findall(r'href=["\'](https://streamingcommunity[a-zA-Z0-9\-\.]+)["\']', r.text)
                    for candidate in matches:
                        verified = self.verify_domain(candidate)
                        if verified:
                            self._update_remote_gist(verified)
                            return verified
            except Exception:
                pass
        return None

    def init_session(self, force=False):
        with self._lock:
            # Se già inizializzato e non forzato, esegui un veloce liveness check
            if self.initialized and not force:
                return True

            # 1. Priorità Massima: Hub Ufficiali (streaming-community.day / .farm)
            hub_domain = self.fetch_from_hubs()
            if hub_domain:
                self.domain = hub_domain
                self.initialized = True
                self.last_init_time = time.time()
                self.last_error = None
                self._start_auto_refresh()
                return True

            # 2. Priorità Secondaria: Gist GitHub dinamico
            try:
                r = self.session.get(f"{self.GIST_RAW_URL}?_={int(time.time())}", timeout=6)
                if r.status_code == 200:
                    gist_domain = r.text.strip()
                    verified = self.verify_domain(gist_domain)
                    if verified:
                        self.domain = verified
                        self.initialized = True
                        self.last_init_time = time.time()
                        self.last_error = None
                        self._start_auto_refresh()
                        return True
            except Exception:
                pass

            # 3. Priorità Terziaria: Dominio di default configurato
            verified_def = self.verify_domain(DEFAULT_SC_DOMAIN)
            if verified_def:
                self.domain = verified_def
                self.initialized = True
                self.last_init_time = time.time()
                self.last_error = None
                self._start_auto_refresh()
                return True

            # 4. Priorità Quaternaria: Lista nota di candidati specchio
            known_candidates = [
                "https://streamingcommunityz.build",
                "https://streamingcommunity.top",
                "https://streamingcommunityz.day",
                "https://streamingcommunityz.buzz",
                "https://streamingcommunityz.space",
            ]
            for cand in known_candidates:
                verified_cand = self.verify_domain(cand)
                if verified_cand:
                    self.domain = verified_cand
                    self.initialized = True
                    self.last_init_time = time.time()
                    self.last_error = None
                    self._start_auto_refresh()
                    self._update_remote_gist(verified_cand)
                    return True

            # Se nessun dominio è verificabile al momento, mantieni l'ultimo o default
            if not self.domain:
                self.domain = DEFAULT_SC_DOMAIN
            self.initialized = True
            self.last_init_time = time.time()
            self._start_auto_refresh()
            return True

    def _extract_inertia(self, html_text):
        """Estrae e deserializza in modo resiliente l'oggetto JSON Inertia."""
        if not html_text:
            return None
        m = re.search(r'data-page=["\']([^"\']+)["\']', html_text)
        if m:
            try:
                return json.loads(html.unescape(m.group(1)))
            except Exception:
                pass
        return None

    def search(self, query):
        for attempt in range(2):
            if not self.init_session(force=(attempt > 0)):
                if attempt == 1:
                    return {"error": "Failed to init SC session"}
                continue
            try:
                r = self.session.get(f"{self.domain}/it/search", params={'q': query}, timeout=8)
                data = self._extract_inertia(r.text)
                if not data:
                    self.initialized = False
                    continue
                props = data.get("props", {})
                cdn_url = props.get("cdn_url", self.domain.replace("https://", "https://cdn."))
                raw_records = props.get("titles", [])
                if isinstance(raw_records, dict):
                    records = raw_records.get("data", [])
                elif isinstance(raw_records, list):
                    records = raw_records
                else:
                    records = []
                
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
            except Exception as e:
                self.initialized = False
                if attempt == 1:
                    return {"error": str(e)}
        return {"error": "Ricerca fallita"}

    def get_details(self, media_id, slug=""):
        for attempt in range(2):
            if not self.init_session(force=(attempt > 0)):
                if attempt == 1:
                    return {"error": "Init failed"}
                continue
            try:
                r = self.session.get(f"{self.domain}/it/titles/{media_id}-{slug}", timeout=8)
                data = self._extract_inertia(r.text)
                if not data:
                    self.initialized = False
                    continue
                
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
                self.initialized = False
                if attempt == 1:
                    return {"error": str(e)}
        return {"error": "Recupero dettagli fallito"}

    def get_season(self, media_id, slug, season_num):
        for attempt in range(2):
            if not self.init_session(force=(attempt > 0)):
                if attempt == 1:
                    return {"error": "Init failed"}
                continue
            try:
                url = f"{self.domain}/it/titles/{media_id}-{slug}/season-{season_num}"
                r = self.session.get(url, timeout=8)
                data = self._extract_inertia(r.text)
                if not data:
                    self.initialized = False
                    continue
                
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
                self.initialized = False
                if attempt == 1:
                    return {"error": str(e)}
        return {"error": "Recupero stagione fallito"}

    def get_video_url(self, media_id, episode_id=None, ua=None):
        """
        Estrae il flusso video protetto e restituisce un endpoint firmato HMAC
        per impedire al browser o a terzi di leggere gli URL e i token VixCloud interni.
        """
        for attempt in range(2):
            if not self.init_session(force=(attempt > 0)):
                if attempt == 1:
                    return {"error": "Inizializzazione sessione fallita"}
                continue
            try:
                if ua:
                    self.session.headers.update({"User-Agent": ua})
                
                if episode_id and str(episode_id) != str(media_id) and str(episode_id) != "movie":
                    iframe_url = f"{self.domain}/it/iframe/{media_id}?episode_id={episode_id}"
                else:
                    iframe_url = f"{self.domain}/it/iframe/{media_id}"
                
                r = self.session.get(iframe_url, timeout=8)
                vixcloud = re.search(r'src=["\']((https://vixcloud|https://vix)[^"\']+)["\']', r.text)
                if not vixcloud:
                    self.initialized = False
                    continue
                
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
                    
                    # Genera token crittografato firmato dal server: l'URL VixCloud NON viene inviato al browser in chiaro!
                    signed_token = generate_signed_stream_token(f"{media_id}_{episode_id or 'movie'}", "tv", {
                        "raw_url": stream_url,
                        "ref": embed_url
                    })
                    return {"stream_url": f"/api/playlist?token={signed_token}"}
                
                self.initialized = False
                continue
            except Exception as e:
                self.initialized = False
                if attempt == 1:
                    return {"error": str(e)}
        return {"error": "Impossibile estrarre lo stream dall'embed"}

    def get_homepage(self):
        for attempt in range(2):
            if not self.init_session(force=(attempt > 0)):
                if attempt == 1:
                    return {"error": "Init failed"}
                continue
            try:
                r = self.session.get(self.domain, timeout=9)
                data = self._extract_inertia(r.text)
                if not data:
                    self.initialized = False
                    continue
                props = data.get("props", {})
                cdn_url = props.get("cdn_url", self.domain.replace("https://", "https://cdn."))

                def format_titles(titles):
                    out = []
                    if not titles:
                        return out
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
                for sl in props.get("sliders", []):
                    sl_titles = sl.get("titles", [])
                    if sl_titles:
                        sliders.append({
                            "label": sl.get("label", "Popolari"),
                            "titles": format_titles(sl_titles)
                        })

                # Se gli sliders della homepage non hanno titoli, recupera trending ed esplora
                if not sliders:
                    trending_data = self.get_explore("all", 1, endpoint="trending")
                    latest_data = self.get_explore("all", 1, endpoint="latest")
                    if trending_data.get("titles"):
                        sliders.append({"label": "Titoli del momento", "titles": trending_data["titles"]})
                    if latest_data.get("titles"):
                        sliders.append({"label": "Aggiunti di recente", "titles": latest_data["titles"]})

                genres = []
                for g in props.get("genres", []):
                    genres.append({
                        "id": g.get("id"),
                        "name": g.get("name")
                    })
                
                hero = sliders[0]["titles"][0] if sliders and sliders[0].get("titles") else None

                return {
                    "hero": hero,
                    "sliders": sliders,
                    "genres": genres,
                    "cdn_url": cdn_url
                }
            except Exception as e:
                self.initialized = False
                if attempt == 1:
                    return {"error": str(e)}
        return {"error": "Recupero homepage fallito"}

    def get_new_releases(self):
        data = self.get_homepage()
        return {"results": data.get("sliders", [{}])[0].get("titles", []) if data.get("sliders") else []}

    def get_genre_titles(self, genre_name):
        for attempt in range(2):
            if not self.init_session(force=(attempt > 0)):
                if attempt == 1:
                    return {"error": "Init failed"}
                continue
            try:
                genre_quoted = urllib.parse.quote(genre_name)
                r = self.session.get(f"{self.domain}/it/browse/genre?g={genre_quoted}", timeout=8)
                data = self._extract_inertia(r.text)
                if not data:
                    self.initialized = False
                    continue
                props = data.get("props", {})
                cdn_url = props.get("cdn_url", self.domain.replace("https://", "https://cdn."))
                raw_records = props.get("titles", [])
                if isinstance(raw_records, dict):
                    records = raw_records.get("data", [])
                elif isinstance(raw_records, list):
                    records = raw_records
                else:
                    records = []
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
                self.initialized = False
                if attempt == 1:
                    return {"error": str(e)}
        return {"titles": []}

    def get_explore(self, filter_type, page, endpoint="trending"):
        for attempt in range(2):
            if not self.init_session(force=(attempt > 0)):
                if attempt == 1:
                    return {"error": "Init failed"}
                continue
            try:
                r = self.session.get(f"{self.domain}/it/browse/{endpoint}?page={page}", timeout=8)
                data = self._extract_inertia(r.text)
                if not data:
                    self.initialized = False
                    continue
                props = data.get("props", {})
                cdn_url = props.get("cdn_url", self.domain.replace("https://", "https://cdn."))
                titles_data = props.get("titles", {})
                records = titles_data.get("data", []) if isinstance(titles_data, dict) else titles_data
                if not isinstance(records, list):
                    records = []
                
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
                elif isinstance(records, list) and len(records) >= 30:
                    has_more = True
                    
                return {"titles": results, "has_more": has_more}
            except Exception as e:
                self.initialized = False
                if attempt == 1:
                    return {"error": str(e)}
        return {"titles": [], "has_more": False}

sc_session = StreamingCommunitySession()
