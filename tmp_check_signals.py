import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json, time
with open(r'C:\Users\integ\Documents\Claude\Projects\ShipStack\tmp_discovery_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(f'Reports: {len(data)}')
now = time.time()
for r in data[:5]:
    kw = r['product_keyword']
    n = r['n_signals']
    vel = r['scores']['demand_velocity']
    bi = r['scores']['buyer_intent']
    margin_est = r['margin'].get('estimated', False)
    mc = r['margin'].get('gross_margin_pct', 0)
    print(f'\n--- {kw} ({n} sig, vel={vel}, bi={bi}, margin_est={margin_est}, gm={mc:.0%}) ---')
    for src in r.get('top_social_sources', []):
        print(f'  {src.get("platform","?")} : {(src.get("title","") or "")[:70]}')