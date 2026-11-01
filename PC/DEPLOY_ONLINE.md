# 🚀 Guida al Deployment Online di Tortuga (Music, Video & TV)

Questa guida spiega le migliori soluzioni per mettere online Tortuga su Internet, sia mantenendolo sul proprio PC sia trasferendolo su un server cloud 24/7.

---

## ⚡ Opzione 1: Cloudflare Tunnel (Gratis, Immediata, da PC Casa)
Se vuoi rendere accessibile Tortuga dal tuo computer di casa a chiunque nel mondo (o su smartphone/tablet da remoto) **senza pagare un centesimo** e **senza toccare le porte del router**:

1. Scarica **cloudflared** per Windows da [Cloudflare](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
2. Apri PowerShell e digita:
   ```powershell
   cloudflared tunnel --url http://localhost:5000
   ```
3. Cloudflare ti restituirà all'istante un URL HTTPS sicuro (es. `https://random-nome.trycloudflare.com`).
4. Aprendo quell'URL da qualsiasi dispositivo, Tortuga sarà online con certificato SSL e streaming funzionante.

---

## 🌐 Opzione 2: VPS Linux a Basso Costo (Consigliata per 24/7)
Un piccolo server VPS Linux (Hetzner, Contabo, OVH o Netcup a partire da 3€-4€/mese) garantisce uptime continuo 24 ore su 24 con banda illimitata.

### 1. Requisiti sul server
```bash
sudo apt update && sudo apt install -y docker.io docker-compose git ffmpeg
```

### 2. Copia dei file sul server
Puoi clonare la cartella via Git o caricarla via SCP / FileZilla nella directory `/home/tortuga`.

### 3. Avvio con Docker Compose (Metodo 1-Click)
All'interno della cartella `PC/`:
```bash
docker-compose up -d --build
```
Il container compilerà l'ambiente con Python, ffmpeg e le dipendenze, esponendo la porta `5000`.

### 4. Nginx Reverse Proxy & HTTPS (Opzionale con dominio)
```nginx
server {
    server_name tortuga.tuodominio.it;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
Poi attiva il certificato SSL gratuito:
```bash
sudo certbot --nginx -d tortuga.tuodominio.it
```

---

## ☁️ Opzione 3: Piattaforme Cloud (Render, Railway, Fly.io)
Se preferisci non gestire un server Linux:
1. Collega il repository su **Render.com** o **Railway.app**.
2. Scegli **Deploy with Dockerfile**.
3. La piattaforma rileverà automaticamente il [Dockerfile](Dockerfile) di Tortuga, installerà ffmpeg e assegnerà un URL HTTPS pubblico.

---

## 📁 Struttura Pulita dei File del Progetto

```text
TortugaMusic/
├── PC/
│   ├── run.py                 # Script di avvio rapido (--no-browser / --port)
│   ├── AVVIA_TORTUGA_PC.bat   # Launcher con 1 doppio clic su Windows
│   ├── requirements.txt       # Tutte le dipendenze Python
│   ├── Dockerfile             # Container per deploy cloud
│   ├── docker-compose.yml     # Configurazione 1-click Docker
│   ├── DEPLOY_ONLINE.md       # Questa guida
│   ├── backend/               # Server Flask, scraper, database, smart proxy
│   ├── frontend/              # Web UI, TV UI, stili CSS e asset
│   ├── data/                  # Database SQLite (history, playlist, preferiti)
│   └── downloads/             # File scaricati (audio, video, copertine)
```
