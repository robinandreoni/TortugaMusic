"""
Tortuga Web / PC Edition - Central Configuration & Security Settings
"""
import os
import secrets

# Base directory paths
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PC_ROOT_DIR = os.path.dirname(BACKEND_DIR)
DATA_DIR = os.path.join(PC_ROOT_DIR, 'data')
DOWNLOADS_DIR = os.path.join(PC_ROOT_DIR, 'downloads')
MUSIC_DOWNLOADS_DIR = os.path.join(DOWNLOADS_DIR, 'music')
TV_DOWNLOADS_DIR = os.path.join(DOWNLOADS_DIR, 'tv')
FRONTEND_DIR = os.path.join(PC_ROOT_DIR, 'frontend')
STATIC_DIR = os.path.join(FRONTEND_DIR, 'static')

# Ensure required directories exist
for path in [DATA_DIR, DOWNLOADS_DIR, MUSIC_DOWNLOADS_DIR, TV_DOWNLOADS_DIR, FRONTEND_DIR, STATIC_DIR]:
    os.makedirs(path, exist_ok=True)

# Database path
DB_PATH = os.path.join(DATA_DIR, 'tortuga_cache.db')

# Cryptographic Secret Key for HMAC tokens and session signing
# Reads from environment variable or generates a persistent secret in data/
SECRET_KEY_FILE = os.path.join(DATA_DIR, '.secret_key')
if os.environ.get("TORTUGA_SECRET_KEY"):
    SECRET_KEY = os.environ.get("TORTUGA_SECRET_KEY").encode('utf-8')
elif os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, 'rb') as f:
        SECRET_KEY = f.read().strip()
else:
    SECRET_KEY = secrets.token_bytes(32)
    with open(SECRET_KEY_FILE, 'wb') as f:
        f.write(SECRET_KEY)

# Server network settings
SERVER_HOST = os.environ.get("TORTUGA_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("PORT") or os.environ.get("TORTUGA_PORT", "5000"))
DEBUG_MODE = os.environ.get("TORTUGA_DEBUG", "false").lower() == "true"

# Token validity (seconds)
STREAM_TOKEN_TTL = 1800  # 30 minuti di validitÃ  per i token di riproduzione firmati

# Dynamic scraping defaults
GIST_DOMAINS_URL = os.environ.get("GIST_DOMAINS_URL", "")
GIST_ID = os.environ.get("GIST_ID", "")
GITHUB_GIST_TOKEN = os.environ.get("GITHUB_GIST_TOKEN", "")
DEFAULT_SC_DOMAIN = os.environ.get("DEFAULT_SC_DOMAIN", "https://streamingcommunityz.build")
SC_HUBS = [
    "https://www.streaming-community.day",
    "https://streaming-community.day",
    "https://www.streaming-community.farm",
    "https://streaming-community.farm"
]
DEFAULT_AU_DOMAIN = "https://www.animeunity.so"

# Standard User-Agent for server requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# Site Gate Password (Simpson Pre-preloader)
SITE_PASSWORD = os.environ.get("TORTUGA_PASSWORD", "tortuga2026")

