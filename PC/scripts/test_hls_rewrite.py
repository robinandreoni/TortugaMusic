import requests
import re
from urllib.parse import urljoin, quote

test_urls = [
    "https://d3k8wzt41aflvx.cloudfront.net/RAIScuola/Live.m3u8",
    "https://dash2.antik.sk/live/test_rai_uno_tizen/playlist.m3u8"
]

def rewrite_manifest(text, base_url):
    rewritten_lines = []
    for line in text.splitlines():
        sline = line.strip()
        if not sline:
            rewritten_lines.append("")
        elif 'URI=' in sline:
            # Handle URI="..." or URI='...' or URI=... inside any tag (e.g. #EXT-X-MEDIA, #EXT-X-KEY, #EXT-X-MAP)
            def _replace_uri(m):
                raw_uri = m.group(1)
                abs_uri = urljoin(base_url, raw_uri)
                return f'URI="/api/iptv/stream?url={quote(abs_uri, safe="")}"'
            rewritten_line = re.sub(r'URI=["\']?([^"\'\s,>]+)["\']?', _replace_uri, sline)
            rewritten_lines.append(rewritten_line)
        elif sline.startswith("#"):
            rewritten_lines.append(sline)
        else:
            abs_url = urljoin(base_url, sline)
            rewritten_lines.append(f"/api/iptv/stream?url={quote(abs_url, safe='')}")
    return "\n".join(rewritten_lines)

for u in test_urls:
    print(f"\n--- Testing: {u} ---")
    r = requests.get(u, timeout=5)
    res = rewrite_manifest(r.text, r.url)
    print("Rewritten output (first 8 lines):")
    for l in res.splitlines()[:8]:
        print("  ", l)
