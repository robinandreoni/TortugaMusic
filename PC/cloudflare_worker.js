/**
 * Cloudflare Worker: Dynamic Gateway Redirector
 * Reindirizza istantaneamente verso il tunnel Cloudflare attivo del PC locale
 * leggendo l'URL sempre aggiornato in tempo reale dal GitHub Gist API.
 */

const DEFAULT_GIST_API_URL = "https://api.github.com/gists/YOUR_GIST_ID_HERE";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const GIST_API_URL = env.GIST_API_URL || DEFAULT_GIST_API_URL;

    try {
      // Lettura in tempo reale senza cache per reattività immediata a ogni cambio tunnel
      const res = await fetch(GIST_API_URL, {
        headers: {
          "User-Agent": "Tortuga-Worker-Gateway",
          "Accept": "application/vnd.github.v3+json"
        },
        cf: { cacheTtl: 5, cacheEverything: false }
      });

      if (!res.ok) {
        throw new Error("Impossibile recuperare l'indirizzo del tunnel da GitHub API");
      }

      const gistData = await res.json();
      const targetTunnel = gistData.files && gistData.files["tortuga_tunnel.txt"] ? gistData.files["tortuga_tunnel.txt"].content.trim() : null;

      if (!targetTunnel || !targetTunnel.startsWith("http") || targetTunnel.includes("api.trycloudflare.com")) {
        throw new Error("Nessun tunnel attivo configurato");
      }

      // Costruisce l'URL di destinazione mantenendo percorso e parametri
      const targetUrl = targetTunnel.replace(/\/$/, "") + url.pathname + url.search;
      
      // Reindirizzamento 307 Temporary Redirect
      return Response.redirect(targetUrl, 307);

    } catch (err) {
      // Pagina di cortesia se il server di casa è spento o offline
      const html = `<!DOCTYPE html>
      <html lang="it">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Tortuga Web - Server In Pausa</title>
        <style>
          body {
            background: #0f172a;
            color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
            text-align: center;
          }
          .card {
            background: #1e293b;
            padding: 2.5rem;
            border-radius: 1.25rem;
            box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
            max-width: 440px;
            border: 1px solid #334155;
          }
          h1 { margin: 0 0 1rem; font-size: 2rem; color: #38bdf8; }
          p { color: #94a3b8; line-height: 1.6; margin-bottom: 1.5rem; }
          .badge {
            display: inline-block;
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
          }
        </style>
      </head>
      <body>
        <div class="card">
          <div style="font-size: 3.5rem; margin-bottom: 1rem;">🏴‍☠️</div>
          <h1>Tortuga Web</h1>
          <p>Il server locale sul PC è attualmente in pausa o disconnesso.</p>
          <div class="badge">Avvia il file sul PC per ricollegarlo</div>
        </div>
      </body>
      </html>`;
      return new Response(html, {
        status: 503,
        headers: { "Content-Type": "text/html; charset=utf-8" }
      });
    }
  }
};
