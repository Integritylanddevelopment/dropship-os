import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\integ\Documents\Claude\Projects\ShipStack')
from dotenv import load_dotenv
load_dotenv(r'C:\Users\integ\Documents\Claude\Projects\ShipStack\.env')

results = {}

# Test each signal source individually
try:
    from discovery_engine.signals import google_trends
    sigs = google_trends.collect_daily(geo='US')
    results['google_trends'] = len(sigs)
except Exception as e:
    results['google_trends'] = f'FAIL: {e}'

try:
    from discovery_engine.signals import amazon_movers
    sigs = amazon_movers.collect_category('pet-supplies', limit=5)
    results['amazon_movers'] = len(sigs)
except Exception as e:
    results['amazon_movers'] = f'FAIL: {e}'

try:
    from discovery_engine.signals import reddit_signals
    sigs = reddit_signals.collect_keyword('posture corrector', limit=5)
    results['reddit'] = len(sigs)
except Exception as e:
    results['reddit'] = f'FAIL: {e}'

print(json.dumps(results, indent=2))
