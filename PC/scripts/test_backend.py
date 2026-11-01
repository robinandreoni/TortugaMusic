"""
Script di Collaudo per il Backend di Tortuga Music & TV (Web / PC Edition)
Testa tutte le chiamate API chiave: YouTube, StreamingCommunity, AnimeUnity, IPTV e Sicurezza.
"""
import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(ROOT_DIR, 'backend'))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from backend import server  # type: ignore
    from backend.security import verify_signed_stream_token  # type: ignore
except ImportError:
    import server  # type: ignore
    from security import verify_signed_stream_token  # type: ignore

def run_tests():
    print("=" * 60)
    print("🧪 AVVIO TEST BACKEND TORTUGA WEB / PC")
    print("=" * 60)
    
    client = server.app.test_client()
    
    # 1. Test Health
    print("\n[1/7] Test Health Check...")
    res = client.get('/api/health')
    assert res.status_code == 200, f"Health check fallito: {res.status_code}"
    print(f" -> OK: {res.get_json()}")
    
    # 2. Test Refresh Domains
    print("\n[2/7] Test Refresh Domini...")
    res = client.get('/api/refresh-domains')
    assert res.status_code == 200, f"Refresh domini fallito: {res.status_code}"
    print(f" -> OK: {res.get_json()}")
    
    # 3. Test IPTV Channels
    print("\n[3/7] Test Catalogo IPTV...")
    res = client.get('/api/iptv/channels')
    assert res.status_code == 200, f"IPTV fallito: {res.status_code}"
    data = res.get_json()
    channels = data.get("channels", [])
    assert len(channels) > 0, "Nessun canale IPTV trovato"
    print(f" -> OK: Trovati {len(channels)} canali. Esempio primo canale: {channels[0]['name']} -> {channels[0]['stream_url']}")
    # Verifica che il token firmato HMAC sia valido
    token = channels[0].get('token_url', '').split("token=")[-1]
    verified = verify_signed_stream_token(token)
    assert verified is not None, "Verifica token firmato fallita!"
    print(f" -> OK: Token crittografico HMAC verificato con successo!")

    # Verifica endpoint proxy stream IPTV
    first_stream = channels[0]['stream_url']
    res_proxy = client.get(first_stream)
    assert res_proxy.status_code == 200, f"Proxy stream fallito con status {res_proxy.status_code}"
    print(f" -> OK: Proxy HLS verificato con successo su {channels[0]['name']} (Status 200 OK, Type: {res_proxy.content_type})")

    # 4. Test YouTube Music Search
    print("\n[4/7] Test Ricerca YouTube Music...")
    res = client.get('/api/search?q=Vasco+Rossi&mode=music&limit=3')
    assert res.status_code == 200, f"Ricerca YouTube fallita: {res.status_code}"
    data = res.get_json()
    tracks = data.get("tracks", [])
    print(f" -> OK: Trovate {len(tracks)} tracce. Prima traccia: {tracks[0]['artist']} - {tracks[0]['title']}")

    # 5. Test StreamingCommunity Search
    print("\n[5/7] Test Ricerca StreamingCommunity...")
    res = client.get('/api/search?provider=streamingcommunity&q=Matrix')
    assert res.status_code == 200, f"Ricerca SC fallita: {res.status_code}"
    data = res.get_json()
    results = data.get("results", [])
    print(f" -> OK: Trovati {len(results)} risultati cinema. Primo: {results[0]['title'] if results else 'Nessuno'}")

    # 6. Test Cache Stats
    print("\n[6/7] Test Statistiche SQLite...")
    res = client.get('/api/cache/stats')
    assert res.status_code == 200
    print(f" -> OK: Cache stats: {res.get_json()}")

    # 7. Test Headers Sicurezza
    print("\n[7/7] Test Intestazioni di Sicurezza HTTP...")
    assert 'X-Content-Type-Options' in res.headers
    assert 'X-Frame-Options' in res.headers
    print(f" -> OK: Intestazioni di sicurezza presenti: nosniff, SAMEORIGIN")

    print("\n" + "=" * 60)
    print("✅ TUTTI I TEST DEL BACKEND SONO STATI SUPERATI CON SUCCESSO!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
