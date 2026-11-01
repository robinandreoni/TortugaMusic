"""
Tortuga Cloudflare Tunnel Auto-Sync
Avvia cloudflared, recupera l'URL pubblico trycloudflare.com e aggiorna
automaticamente il GitHub Gist collegato al Worker permanente:
https://tortuga.cybergrid.workers.dev
"""
import os
import sys
import re
import time
import subprocess
import requests

# Configura UTF-8 per la console Windows evitando UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GIST_ID = os.getenv("GIST_ID", "")
WORKER_URL = os.getenv("WORKER_URL", "https://your-worker-subdomain.workers.dev")

def update_gist(tunnel_url: str):
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "files": {
                "tortuga_tunnel.txt": {
                    "content": tunnel_url
                }
            }
        }
        res = requests.patch(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            print(f"[OK] Gist aggiornato con successo!")
            print(f"[DOMINIO FISSO] -> {WORKER_URL}")
            print(f"[TUNNEL DIRETTO] -> {tunnel_url}")
            return True
        else:
            print(f"[WARN] Aggiornamento Gist fallito: HTTP {res.status_code}")
    except Exception as e:
        print(f"[ERRORE GIST] {e}")
    return False

def get_cloudflared_bin():
    import shutil
    p = shutil.which("cloudflared")
    if p:
        return p
    default_paths = [
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\cloudflared\cloudflared.exe")
    ]
    for dp in default_paths:
        if os.path.exists(dp) and os.path.isfile(dp):
            return dp
    return "cloudflared"

def start_tunnel():
    bin_path = get_cloudflared_bin()
    print(f"[*] Avvio Cloudflare Tunnel con: {bin_path}")
    
    env = os.environ.copy()
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    possible_certs = [
        os.path.join(prefix, "etc", "tls", "cert.pem"),
        os.path.join(prefix, "etc", "ssl", "certs", "ca-certificates.crt"),
        "/etc/ssl/certs/ca-certificates.crt"
    ]
    for cp in possible_certs:
        if os.path.exists(cp):
            env["SSL_CERT_FILE"] = cp
            env["REQUESTS_CA_BUNDLE"] = cp
            break

    cmd = [bin_path, "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:5000"]
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env
        )
    except FileNotFoundError:
        print(f"\n[ERRORE] cloudflared non trovato nel sistema!")
        print("Su Android (Termux) installalo con il comando: pkg install -y cloudflared\n")
        return None
    except Exception as e:
        print(f"\n[ERRORE AVVIO TUNNEL] {e}\n")
        return None
    
    tunnel_url = None
    gist_updated = False
    
    try:
        for line in iter(proc.stdout.readline, ""):
            print(line, end="")
            match = re.search(r"https://([a-zA-Z0-9\-]+)\.trycloudflare\.com", line)
            if match:
                sub = match.group(1).lower()
                if sub != "api":
                    found_url = match.group(0)
                    if found_url != tunnel_url:
                        tunnel_url = found_url
                        print("\n" + "=" * 60)
                        print(f" [*] TORTUGA ONLINE: {tunnel_url}")
                        print(f" [*] INDIRIZZO FISSO: {WORKER_URL}")
                        print("=" * 60 + "\n")
                        update_gist(tunnel_url)
                        gist_updated = True
    except KeyboardInterrupt:
        print("\n[*] Arresto tunnel in corso...")
        proc.terminate()
        
    return proc

if __name__ == "__main__":
    start_tunnel()
