"""
Tortuga Music & TV - Launcher Cross-Platform (Windows, macOS, Linux)
"""
import os
import sys
import webbrowser
import threading
import time

# Aggiunge backend al PYTHONPATH
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, 'backend')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend import config
from backend.server import app

def open_browser(url):
    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception:
        pass

# Configura UTF-8 per console Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

if __name__ == "__main__":
    host = os.environ.get("TORTUGA_HOST", "0.0.0.0" if "--no-browser" in sys.argv else "127.0.0.1")
    port = int(os.environ.get("PORT") or os.environ.get("TORTUGA_PORT", "5000"))
    url = f"http://{host}:{port}"
    
    print("=" * 60)
    print("   [TORTUGA] MUSIC & TV -- WEB / PC EDITION")
    print(f"   Server attivo su: {url}")
    print("   Premi CTRL+C per arrestare il server")
    print("=" * 60)

    if "--no-browser" not in sys.argv:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    app.run(host=host, port=port, debug=False)
