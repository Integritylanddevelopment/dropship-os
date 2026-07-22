import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\integ\Documents\Claude\Projects\ShipStack')
from discovery_engine.suppliers import cj_dropshipping
for q in ['Mini Walk-in Greenhouse With', 'greenhouse', 'walk-in greenhouse']:
    r = cj_dropshipping.search(q, limit=5)
    print(f'QUERY: {q} -> {len(r)} results')
    for l in r:
        print(f'  id={bool(l.get("id"))} img={bool(l.get("image"))} | {(l.get("title") or "")[:70]}')