import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import urllib.request, json
url = 'https://www.reddit.com/r/shutupandtakemymoney/hot.json?limit=3&raw_json=1'
headers = {'User-Agent': 'ShipStackBot/1.0 (product discovery)'}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        code = resp.getcode()
        ct = resp.headers.get('Content-Type', '')
        body = resp.read()[:2000].decode('utf-8', errors='replace')
        print(f'STATUS: {code}')
        print(f'CT: {ct}')
        print(f'BODY_LEN: {len(body)}')
        print(f'BODY: {body[:500]}')
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')