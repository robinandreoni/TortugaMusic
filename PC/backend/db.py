"""
Tortuga Web / PC Edition - Database & Persistent Caching Engine
Gestisce SQLite con supporto WAL per alte prestazioni multi-thread.
"""
import os
import sqlite3
import time
import json
from config import DB_PATH, DATA_DIR

def get_db_conn():
    """Restituisce una connessione SQLite ottimizzata con journal WAL."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass
    return conn

def init_db():
    """Inizializza tutte le tabelle essenziali per cache, impostazioni, cronologia e download."""
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            # Cache degli stream estratti (HLS, MP4, Audio)
            c.execute('''
                CREATE TABLE IF NOT EXISTS stream_cache (
                    cache_key TEXT PRIMARY KEY,
                    data_json TEXT,
                    expires_at REAL,
                    created_at REAL
                )
            ''')
            # Cache delle ricerche (YouTube, Film, Serie, Anime)
            c.execute('''
                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key TEXT PRIMARY KEY,
                    data_json TEXT,
                    expires_at REAL,
                    created_at REAL
                )
            ''')
            # Impostazioni generali
            c.execute('''
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            # Backup sincronizzato dati utente (playlist, preferiti)
            c.execute('''
                CREATE TABLE IF NOT EXISTS user_data_backup (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at REAL
                )
            ''')
            # Catalogo tracce musicali salvate localmente
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
            # Cronologia di visione video / ripresa ("Continua a guardare")
            c.execute('''
                CREATE TABLE IF NOT EXISTS watch_history (
                    media_id TEXT,
                    episode_id TEXT,
                    title TEXT,
                    progress REAL,
                    duration REAL,
                    updated_at REAL,
                    PRIMARY KEY(media_id, episode_id)
                )
            ''')
            # Watch progress: traccia il progresso esatto per ogni titolo/episodio
            c.execute('''
                CREATE TABLE IF NOT EXISTS watch_progress (
                    media_id TEXT NOT NULL,
                    episode_id TEXT NOT NULL DEFAULT '',
                    title TEXT,
                    image TEXT,
                    media_type TEXT DEFAULT 'movie',
                    provider TEXT DEFAULT 'streamingcommunity',
                    slug TEXT DEFAULT '',
                    season_num INTEGER DEFAULT 0,
                    episode_num INTEGER DEFAULT 0,
                    episode_name TEXT DEFAULT '',
                    progress_seconds REAL DEFAULT 0,
                    duration_seconds REAL DEFAULT 0,
                    completed INTEGER DEFAULT 0,
                    updated_at REAL,
                    PRIMARY KEY(media_id, episode_id)
                )
            ''')
            # Auth lockout: blocco progressivo tentativi password
            c.execute('''
                CREATE TABLE IF NOT EXISTS auth_lockout (
                    client_id TEXT PRIMARY KEY,
                    attempts INTEGER DEFAULT 0,
                    lockout_until REAL DEFAULT 0,
                    lockout_level INTEGER DEFAULT 0,
                    last_attempt_at REAL DEFAULT 0
                )
            ''')
            conn.commit()
            seed_user_data_from_file()
    except Exception as e:
        print(f"[Cache DB Init Error] {e}")

def seed_user_data_from_file():
    """Se il database è vuoto (es. nuovo server su telefono), ripristina cronologia, playlist e avanzamenti da user_sync_seed.json."""
    seed_file = os.path.join(DATA_DIR, 'user_sync_seed.json')
    if not os.path.exists(seed_file):
        return
    try:
        with open(seed_file, 'r', encoding='utf-8') as f:
            seed_data = json.load(f)
        
        with get_db_conn() as conn:
            c = conn.cursor()
            # 1. user_data_backup
            c.execute("SELECT COUNT(*) FROM user_data_backup")
            if c.fetchone()[0] == 0:
                backups = seed_data.get('user_data_backup', {})
                for k, v in backups.items():
                    val_str = json.dumps(v) if not isinstance(v, str) else v
                    c.execute("INSERT OR REPLACE INTO user_data_backup (key, value, updated_at) VALUES (?, ?, ?)", (k, val_str, time.time()))
                print(f"[Seed] Ripristinati {len(backups)} elementi di backup utente")

            # 2. watch_progress
            c.execute("SELECT COUNT(*) FROM watch_progress")
            if c.fetchone()[0] == 0:
                progress_items = seed_data.get('watch_progress', [])
                for item in progress_items:
                    c.execute('''
                        INSERT OR REPLACE INTO watch_progress (
                            media_id, episode_id, title, image, media_type, provider,
                            slug, season_num, episode_num, episode_name, progress_seconds,
                            duration_seconds, completed, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        str(item.get('media_id', '')),
                        str(item.get('episode_id', '')),
                        item.get('title', ''),
                        item.get('image', ''),
                        item.get('media_type', 'movie'),
                        item.get('provider', 'streamingcommunity'),
                        item.get('slug', ''),
                        int(item.get('season_num', 0)),
                        int(item.get('episode_num', 0)),
                        item.get('episode_name', ''),
                        float(item.get('progress_seconds', 0.0)),
                        float(item.get('duration_seconds', 0.0)),
                        int(item.get('completed', 0)),
                        float(item.get('updated_at', time.time()))
                    ))
                print(f"[Seed] Ripristinati {len(progress_items)} avanzamenti di visione")
            conn.commit()
    except Exception as e:
        print(f"[Seed Error] {e}")

def update_seed_file():
    """Mantiene sincronizzato user_sync_seed.json per consentire il sync immediato con altri dispositivi."""
    seed_file = os.path.join(DATA_DIR, 'user_sync_seed.json')
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT key, value FROM user_data_backup")
            backups = {}
            for r in c.fetchall():
                key, val = r[0], r[1]
                if isinstance(val, str) and (val.startswith('[') or val.startswith('{')):
                    try:
                        backups[key] = json.loads(val)
                    except Exception:
                        backups[key] = val
                else:
                    backups[key] = val
            
            c.execute('''
                SELECT media_id, episode_id, title, image, media_type, provider, slug,
                       season_num, episode_num, episode_name, progress_seconds, duration_seconds,
                       completed, updated_at
                FROM watch_progress
            ''')
            cols = ['media_id', 'episode_id', 'title', 'image', 'media_type', 'provider', 'slug', 'season_num', 'episode_num', 'episode_name', 'progress_seconds', 'duration_seconds', 'completed', 'updated_at']
            progress = [dict(zip(cols, row)) for row in c.fetchall()]
            
            data = {
                'user_data_backup': backups,
                'watch_progress': progress
            }
            with open(seed_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Update Seed Error] {e}")

def get_cached_item(table: str, key: str):
    """Legge un elemento dalla cache SQLite verificando il TTL."""
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

def set_cached_item(table: str, key: str, data, ttl_seconds: int = 3600):
    """Salva o aggiorna un elemento nella cache con TTL specificato."""
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

def save_user_backup(key: str, value: str):
    """Salva una chiave di backup utente (es. preferiti, playlist)."""
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO user_data_backup (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, value, time.time()))
            conn.commit()
            update_seed_file()
            return True
    except Exception as e:
        print(f"[Backup Save Error] {e}")
        return False

def load_user_backup(key: str = None):
    """Carica un dato di backup utente o tutti i dati."""
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM user_data_backup")
            if c.fetchone()[0] == 0:
                seed_user_data_from_file()
            if key:
                c.execute("SELECT value FROM user_data_backup WHERE key = ?", (key,))
                row = c.fetchone()
                return row[0] if row else None
            else:
                c.execute("SELECT key, value FROM user_data_backup")
                return {r[0]: r[1] for r in c.fetchall()}
    except Exception as e:
        print(f"[Backup Load Error] {e}")
        return None

def get_cache_stats():
    """Restituisce le statistiche dell'uso della cache."""
    stats = {}
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            for table in ['stream_cache', 'search_cache', 'offline_tracks', 'watch_history']:
                c.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = c.fetchone()[0]
    except Exception as e:
        stats["error"] = str(e)
    return stats

def clear_cache():
    """Svuota le tabelle di cache transitorie."""
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM stream_cache")
            c.execute("DELETE FROM search_cache")
            conn.commit()
        return True
    except Exception as e:
        print(f"[Cache Clear Error] {e}")
        return False

def save_watch_progress(item: dict):
    """Salva o aggiorna lo stato di avanzamento di un titolo/episodio."""
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO watch_progress (
                    media_id, episode_id, title, image, media_type, provider, slug,
                    season_num, episode_num, episode_name, progress_seconds, duration_seconds,
                    completed, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(item.get("media_id", "") or item.get("id", "")),
                str(item.get("episode_id", "") or ""),
                item.get("title", ""),
                item.get("image", ""),
                item.get("media_type", "movie") or item.get("type", "movie"),
                item.get("provider", "streamingcommunity"),
                item.get("slug", ""),
                int(item.get("season_num", 0) or 0),
                int(item.get("episode_num", 0) or 0),
                item.get("episode_name", ""),
                float(item.get("progress_seconds", 0) or 0),
                float(item.get("duration_seconds", 0) or 0),
                1 if item.get("completed") else 0,
                time.time()
            ))
            conn.commit()
            update_seed_file()
            return True
    except Exception as e:
        print(f"[Watch Progress Save Error] {e}")
        return False

def get_watch_progress_list(limit: int = 50):
    """Restituisce la lista dei contenuti visti di recente ordinati per ultimo aggiornamento."""
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM watch_progress")
            if c.fetchone()[0] == 0:
                seed_user_data_from_file()
            c.execute('''
                SELECT media_id, episode_id, title, image, media_type, provider, slug,
                       season_num, episode_num, episode_name, progress_seconds, duration_seconds,
                       completed, updated_at
                FROM watch_progress
                ORDER BY updated_at DESC
                LIMIT ?
            ''', (limit,))
            rows = c.fetchall()
            results = []
            for r in rows:
                results.append({
                    "id": r[0],
                    "media_id": r[0],
                    "episode_id": r[1],
                    "title": r[2],
                    "image": r[3],
                    "type": r[4],
                    "media_type": r[4],
                    "provider": r[5],
                    "slug": r[6],
                    "season_num": r[7],
                    "episode_num": r[8],
                    "episode_name": r[9],
                    "progress_seconds": r[10],
                    "duration_seconds": r[11],
                    "completed": bool(r[12]),
                    "updated_at": r[13]
                })
            return results
    except Exception as e:
        print(f"[Watch Progress Get Error] {e}")
        return []

def delete_watch_progress(media_id: str, episode_id: str = None):
    """Elimina un titolo o episodio dalla cronologia visti di recente."""
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            if episode_id:
                c.execute("DELETE FROM watch_progress WHERE media_id = ? AND episode_id = ?", (str(media_id), str(episode_id)))
            else:
                c.execute("DELETE FROM watch_progress WHERE media_id = ?", (str(media_id),))
            conn.commit()
            update_seed_file()
            return True
    except Exception as e:
        print(f"[Watch Progress Delete Error] {e}")
        return False

def check_auth_lockout(client_id: str):
    """
    Verifica se il client è attualmente bloccato.
    Restituisce (is_locked, remaining_seconds, lockout_level, attempts).
    """
    now = time.time()
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT attempts, lockout_until, lockout_level FROM auth_lockout WHERE client_id = ?", (client_id,))
            row = c.fetchone()
            if not row:
                return False, 0, 0, 0
            attempts, lockout_until, lockout_level = row
            if lockout_until and now < lockout_until:
                return True, int(lockout_until - now), lockout_level, attempts
            return False, 0, lockout_level, attempts
    except Exception as e:
        print(f"[Auth Lockout Check Error] {e}")
        return False, 0, 0, 0

def record_auth_attempt(client_id: str, success: bool):
    """
    Registra un tentativo di autenticazione.
    In caso di successo resetta i tentativi. In caso di fallimento aumenta i tentativi
    e fa scattare il blocco progressivo al terzo errore (15m, 30m, 1h, 24h).
    """
    now = time.time()
    try:
        with get_db_conn() as conn:
            c = conn.cursor()
            if success:
                c.execute("DELETE FROM auth_lockout WHERE client_id = ?", (client_id,))
                conn.commit()
                return {"locked": False, "attempts": 0}
            
            c.execute("SELECT attempts, lockout_until, lockout_level FROM auth_lockout WHERE client_id = ?", (client_id,))
            row = c.fetchone()
            
            lockout_durations = [15 * 60, 30 * 60, 60 * 60, 24 * 3600] # 15m, 30m, 1h, 24h
            
            if not row:
                attempts = 1
                lockout_level = 0
                lockout_until = 0
            else:
                attempts = row[0] + 1
                lockout_until = row[1]
                lockout_level = row[2]
            
            is_locked = False
            remaining = 0
            if attempts >= 3:
                duration = lockout_durations[min(lockout_level, len(lockout_durations) - 1)]
                lockout_until = now + duration
                lockout_level = min(lockout_level + 1, len(lockout_durations) - 1)
                attempts = 0 # reset tentativi per il prossimo ciclo
                is_locked = True
                remaining = int(duration)
            
            c.execute('''
                INSERT OR REPLACE INTO auth_lockout (client_id, attempts, lockout_until, lockout_level, last_attempt_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (client_id, attempts, lockout_until, lockout_level, now))
            conn.commit()
            
            return {
                "locked": is_locked,
                "remaining_seconds": remaining,
                "attempts_used": attempts,
                "attempts_left": max(0, 3 - attempts) if not is_locked else 0,
                "lockout_level": lockout_level
            }
    except Exception as e:
        print(f"[Auth Record Error] {e}")
        return {"locked": False, "attempts_left": 3}

# Inizializzazione automatica all'import
init_db()

