import requests
import json
import re
import html

session = requests.Session()
r = session.get("https://www.streaming-community.school/")
domain = "https://streamingcommunityz.tech"
match = re.search(r'https://streamingcommunity[^/"\'\s]+', r.text)
if match:
    domain = match.group(0)

# get a movie
print(f"Domain: {domain}")
r = session.get(f"{domain}/it/search?q=avatar")
inertia = re.search(r'data-page=["\']([^"\']+)["\']', r.text)
if inertia:
    data = json.loads(html.unescape(inertia.group(1)))
    records = data.get("props", {}).get("titles", [])
    if records:
        print("Images array for the first result:")
        print(json.dumps(records[0].get("images", []), indent=2))
        
        # let's try getting detail page
        movie_id = records[0]["id"]
        slug = records[0]["slug"]
        r2 = session.get(f"{domain}/it/titles/{movie_id}-{slug}")
        inertia2 = re.search(r'data-page=["\']([^"\']+)["\']', r2.text)
        if inertia2:
            data2 = json.loads(html.unescape(inertia2.group(1)))
            print("Images array in detail page:")
            print(json.dumps(data2.get("props", {}).get("title", {}).get("images", []), indent=2))
