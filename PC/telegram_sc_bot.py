import os
import sys
import re
import time
import asyncio
import requests
from telethon import TelegramClient, events

# ==============================================================
# CONFIGURAZIONE (Imposta tramite variabili d'ambiente o file .env)
# ==============================================================

# Ottieni le tue credenziali API Telegram gratuite da https://my.telegram.org -> API development tools
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
GROUP_INVITE_LINK = os.getenv("TELEGRAM_GROUP_LINK", "")

# Token GitHub e ID Gist per la sincronizzazione dinamica dei domini
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GIST_ID = os.getenv("GIST_ID", "")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "username")

# Domini conosciuti da monitorare per redirect
KNOWN_DOMAINS = [
    "https://streamingcommunityz.build",
    "https://streamingcommunity.top",
    "https://streamingcommunityz.space",
    "https://streamingcommunityz.day",
    "https://streamingcommunityz.buzz",
]

# Intervallo controllo redirect (in secondi) - ogni 30 minuti
CHECK_INTERVAL = 1800

# ==============================================================

import urllib3
urllib3.disable_warnings()
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_session")
client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

# Tiene traccia del dominio attualmente salvato
current_domain = None


def get_current_gist_domain():
    """Legge il dominio attualmente nel Gist"""
    try:
        r = requests.get(
            f"https://gist.githubusercontent.com/{GITHUB_USERNAME}/{GIST_ID}/raw",
            timeout=10
        )
        if r.status_code == 200:
            return r.text.strip()
    except:
        pass
    return None


def update_gist(new_domain):
    """Aggiorna il Gist su GitHub con il nuovo dominio"""
    global current_domain
    
    # Non aggiornare se è lo stesso dominio
    if new_domain == current_domain:
        print(f"[=] Il Gist contiene già {new_domain}, nessun aggiornamento necessario.")
        return True
    
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            print(f"[!] Errore lettura Gist: {r.status_code}")
            return False
            
        filename = list(r.json()["files"].keys())[0]
        payload = {"files": {filename: {"content": new_domain}}}
        r_update = requests.patch(url, headers=headers, json=payload)
        
        if r_update.status_code == 200:
            current_domain = new_domain
            print(f"[+] *** GIST AGGIORNATO CON SUCCESSO: {new_domain} ***")
            return True
        else:
            print(f"[!] Errore aggiornamento Gist: {r_update.status_code} - {r_update.text[:200]}")
            return False
    except Exception as e:
        print(f"[!] Errore rete GitHub: {e}")
        return False


def verify_domain(domain_url):
    """
    Verifica se un dominio è il VERO StreamingCommunity.
    Ritorna il dominio finale (seguendo redirect) o None se non valido.
    """
    try:
        r = requests.get(domain_url, timeout=8, verify=False, allow_redirects=True)
        final_url = r.url.rstrip('/')
        
        # Il vero SC usa Inertia.js - questo è il check più affidabile
        has_inertia = 'data-page=' in r.text
        
        if has_inertia:
            print(f"[+] Dominio VERIFICATO (Inertia): {final_url}")
            return final_url
            
    except Exception as e:
        pass
    
    return None


def check_redirects():
    """
    Controlla tutti i domini conosciuti per vedere se qualcuno
    reindirizza a un nuovo dominio. QUESTA È LA CHIAVE!
    """
    # 1. Controlla prima gli Hub Ufficiali (es. streaming-community.day)
    for hub in ["https://www.streaming-community.day", "https://streaming-community.farm"]:
        try:
            r_hub = requests.get(hub, timeout=8, verify=False)
            if r_hub.status_code == 200:
                matches = re.findall(r'href=["\'](https://streamingcommunity[a-zA-Z0-9\-\.]+)["\']', r_hub.text)
                for cand in matches:
                    verified = verify_domain(cand)
                    if verified:
                        update_gist(verified)
                        return verified
        except Exception:
            pass

    print(f"[*] Controllo redirect su {len(KNOWN_DOMAINS)} domini conosciuti...")
    
    for domain in KNOWN_DOMAINS:
        try:
            # Segui i redirect
            r = requests.get(domain, timeout=8, verify=False, allow_redirects=True)
            final_url = r.url.rstrip('/')
            
            # Se il dominio finale è diverso da quello di partenza, è un REDIRECT!
            if final_url.rstrip('/') != domain.rstrip('/'):
                print(f"[!] REDIRECT TROVATO: {domain} -> {final_url}")
                
                # Verifica che il dominio finale sia il vero SC
                verified = verify_domain(final_url)
                if verified:
                    update_gist(verified)
                    # Aggiungi il nuovo dominio alla lista se non c'è
                    if verified not in KNOWN_DOMAINS:
                        KNOWN_DOMAINS.append(verified)
                    return verified
            else:
                # Anche se non c'è redirect, verifica che il dominio attuale funzioni
                has_inertia = 'data-page=' in r.text
                if has_inertia:
                    update_gist(domain)
                    return domain
                    
        except Exception as e:
            print(f"[-] {domain} non raggiungibile: {type(e).__name__}")
    
    return None


async def health_check_video():
    """Simula l'estrazione video di VixCloud per assicurarsi che funzioni"""
    global current_domain
    if not current_domain:
        return True
        
    print(f"[*] Eseguo Health Check Video su {current_domain}...")
    try:
        import html
        import json
        session = requests.Session()
        session.verify = False
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        })
        
        # 1. Cerca Matrix
        r = session.get(f'{current_domain}/it/search?q=matrix', timeout=10)
        inertia = re.search(r'data-page=["\']([^"\']+)["\']', r.text)
        if not inertia:
            raise Exception("Impossibile trovare i dati Inertia nella ricerca (struttura HTML cambiata?)")
            
        data = json.loads(html.unescape(inertia.group(1)))
        titles = data.get('props', {}).get('titles', [])
        if not titles:
            raise Exception("Nessun risultato di ricerca trovato per 'matrix'")
            
        media_id = titles[0].get('id')
        
        # 2. Ottieni iframe
        r_if = session.get(f'{current_domain}/it/iframe/{media_id}', timeout=10)
        vixcloud = re.search(r'src=["\']((https://vixcloud|https://vix)[^"\']+)["\']', r_if.text)
        if not vixcloud:
            raise Exception("Impossibile trovare l'URL di VixCloud nell'iframe")
            
        embed_url = html.unescape(vixcloud.group(1))
        
        # 3. Ottieni pagina embed
        r_embed = session.get(embed_url, headers={'Referer': current_domain}, timeout=10)
        if r_embed.status_code == 410:
            raise Exception("VixCloud ha restituito errore 410 Gone")
        if r_embed.status_code == 403:
            raise Exception("Cloudflare ha bloccato la richiesta Python (403 Forbidden)")
            
        url_match = re.search(r"url:\s*['\"]([^'\"]+)['\"]", r_embed.text)
        token_match = re.search(r"['\"]token['\"]:\s*['\"]([^'\"]+)['\"]", r_embed.text)
        
        if not url_match or not token_match:
            raise Exception("Impossibile estrarre URL playlist o token dalla pagina Embed")
            
        print("[+] Health Check Video: PASSATO (VixCloud ok)")
        return True
        
    except Exception as e:
        error_msg = f"🚨 ALLARME TORTUGA TV 🚨\n\nL'estrazione video da StreamingCommunity sta fallendo!\n\nMotivo: {str(e)}\nDominio: {current_domain}"
        print(error_msg)
        try:
            await client.send_message("me", error_msg)
        except Exception as msg_err:
            print(f"[-] Impossibile inviare notifica Telegram: {msg_err}")
        return False


async def periodic_check():
    """Task asincrono che controlla i redirect ogni CHECK_INTERVAL secondi"""
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        print(f"\n[*] === CONTROLLO PERIODICO ({time.strftime('%H:%M:%S')}) ===")
        result = check_redirects()
        if result:
            print(f"[+] Dominio attivo trovato: {result}")
        else:
            print("[-] Nessun dominio funzionante trovato nei redirect.")
            
        # Esegui il test video di StreamingCommunity
        await health_check_video()


@client.on(events.NewMessage)
async def handler(event):
    """Ascolta nuovi messaggi nel gruppo per link SC"""
    text = event.raw_text
    if not text:
        return
    
    # Cerca link streamingcommunity nel messaggio
    match = re.search(r'(https?://(?:www\.)?streaming[-]?communit(?:y|yz)[^/"\'\s<>]+)', text)
    if match:
        found_url = match.group(1)
        chat = await event.get_chat()
        chat_name = getattr(chat, 'title', str(chat.id))
        print(f"\n[*] Link SC trovato in '{chat_name}': {found_url}")
        
        # SEGUI IL REDIRECT - questa è la parte che mancava!
        verified = verify_domain(found_url)
        if verified:
            update_gist(verified)
            # Aggiungi alla lista dei domini conosciuti
            if found_url not in KNOWN_DOMAINS:
                KNOWN_DOMAINS.append(found_url)
            if verified not in KNOWN_DOMAINS:
                KNOWN_DOMAINS.append(verified)


async def main():
    global current_domain
    
    print("[*] ====================================")
    print("[*]  TORTUGA TV - Bot SC Intelligente")
    print("[*] ====================================")
    print()
    
    # Login
    await client.connect()
    if not await client.is_user_authorized():
        from typing import Any, cast
        await cast(Any, client.start())
    me = await client.get_me()
    print(f"[+] Login Telegram effettuato come {me.first_name}!")
    
    # Unisciti al gruppo
    try:
        from telethon.tl.functions.messages import ImportChatInviteRequest
        invite_hash = GROUP_INVITE_LINK.split("/")[-1].replace("+", "")
        await client(ImportChatInviteRequest(invite_hash))
        print("[+] Unito al gruppo!")
    except Exception as e:
        print(f"[*] Gruppo: {e}")

    # Leggi il dominio attuale dal Gist
    current_domain = get_current_gist_domain()
    print(f"[*] Dominio attuale nel Gist: {current_domain}")
    
    # STEP 1: Controlla subito i redirect dei vecchi domini
    print()
    print("[*] === CONTROLLO INIZIALE REDIRECT ===")
    result = check_redirects()
    if result:
        print(f"[+] Dominio attivo: {result}")
    else:
        print("[-] Nessun redirect trovato, i domini sembrano tutti offline.")
    
    # STEP 2: Controlla gli ultimi 50 messaggi nel gruppo Telegram
    print()
    print("[*] === CONTROLLO CRONOLOGIA MESSAGGI ===")
    try:
        chat = await client.get_entity(GROUP_INVITE_LINK)
        async for message in client.iter_messages(chat, limit=100):
            if message.text:
                match = re.search(r'(https?://(?:www\.)?streaming[-]?communit(?:y|yz)[^/"\'\s<>]+)', message.text)
                if match:
                    found_url = match.group(1)
                    print(f"[*] Link nella cronologia: {found_url}")
                    verified = verify_domain(found_url)
                    if verified:
                        update_gist(verified)
                        if found_url not in KNOWN_DOMAINS:
                            KNOWN_DOMAINS.append(found_url)
                        if verified not in KNOWN_DOMAINS:
                            KNOWN_DOMAINS.append(verified)
                        break
    except Exception as e:
        print(f"[-] Errore cronologia: {e}")

    # STEP 3: Controllo Video VixCloud Iniziale
    print()
    print("[*] === CONTROLLO VIDEO VIXCLOUD ===")
    await health_check_video()

    # STEP 4: Avvia il controllo periodico in background
    asyncio.ensure_future(periodic_check())
    
    print()
    print("[*] ====================================")
    print(f"[*] Bot attivo! Dominio corrente: {current_domain}")
    print(f"[*] Controllo redirect ogni {CHECK_INTERVAL//60} minuti")
    print("[*] In ascolto messaggi in tempo reale...")
    print("[*] Premi CTRL+C per fermare.")
    print("[*] ====================================")
    
    while True:
        try:
            await client.run_until_disconnected()
        except Exception as e:
            print(f"[!] Eccezione loop Telegram ({type(e).__name__}): {e}. Riconnessione tra 15s...")
            await asyncio.sleep(15)
            try:
                await client.connect()
            except Exception:
                pass


if __name__ == "__main__":
    client.loop.run_until_complete(main())
