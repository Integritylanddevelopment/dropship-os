import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import urllib.request, json, time

now = int(time.time())
after = now - (30 * 86400)

# Test 1: subreddit with sort=created_utc + order=desc + after
url1 = f'https://api.pullpush.io/reddit/search/submission/?subreddit=shutupandtakemymoney&sort=created_utc&order=desc&size=5&after={after}'
print(f'Test 1 URL: {url1}')
try:
    req = urllib.request.Request(url1, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        items = data.get('data', [])
        print(f'Test 1 results: {len(items)}')
        for p in items[:3]:
            age_days = (now - (p.get('created_utc') or 0)) / 86400
            print(f'  [{age_days:.0f}d ago] score={p.get("score",0)} {(p.get("title",""))[:60]}')
except Exception as e:
    print(f'Test 1 FAIL: {e}')

# Test 2: keyword search
url2 = f'https://api.pullpush.io/reddit/search/submission/?q=pet+gadget&sort=created_utc&order=desc&size=5&after={after}'
print(f'\nTest 2 URL: {url2}')
try:
    req = urllib.request.Request(url2, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        items = data.get('data', [])
        print(f'Test 2 results: {len(items)}')
        for p in items[:3]:
            age_days = (now - (p.get('created_utc') or 0)) / 86400
            print(f'  [{age_days:.0f}d ago] r/{p.get("subreddit","")} {(p.get("title",""))[:50]}')
except Exception as e:
    print(f'Test 2 FAIL: {e}')

# Test 3: original format that worked (sort=score, no after)
url3 = 'https://api.pullpush.io/reddit/search/submission/?subreddit=shutupandtakemymoney&sort=score&size=5'
print(f'\nTest 3 (original): {url3}')
try:
    req = urllib.request.Request(url3, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        items = data.get('data', [])
        print(f'Test 3 results: {len(items)}')
        for p in items[:3]:
            age_days = (now - (p.get('created_utc') or 0)) / 86400
            print(f'  [{age_days:.0f}d ago] score={p.get("score",0)} {(p.get("title",""))[:60]}')
except Exception as e:
    print(f'Test 3 FAIL: {e}')