import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\integ\Documents\Claude\Projects\ShipStack')
from dotenv import load_dotenv
load_dotenv(r'C:\Users\integ\Documents\Claude\Projects\ShipStack\.env')

from discovery_engine.signals import google_trends, reddit_signals, youtube_signals
from discovery_engine.scoring import clusterer, opportunity_report
from discovery_engine.suppliers import cj_dropshipping

t0 = time.time()
signals = []

# Google Trends - what's hot right now
try:
    sigs = google_trends.collect_daily(geo='US')
    signals.extend(sigs)
    print(f"Google Trends: {len(sigs)} signals")
except Exception as e:
    print(f"Google Trends FAIL: {e}")

# Reddit - multiple product-finding subs
for sub in ["shutupandtakemymoney", "INEEEEDIT", "BuyItForLife"]:
    try:
        sigs = reddit_signals.collect_subreddit(sub, limit=25, sort="score")
        signals.extend(sigs)
        print(f"Reddit r/{sub}: {len(sigs)} signals")
    except Exception as e:
        print(f"Reddit r/{sub} FAIL: {e}")

# Reddit keyword searches for target niches
for kw in ["pet accessories", "kitchen gadget", "fitness tool", "posture corrector", "led lights"]:
    try:
        sigs = reddit_signals.collect_keyword(kw, limit=10)
        signals.extend(sigs)
        print(f"Reddit kw '{kw}': {len(sigs)} signals")
    except Exception as e:
        print(f"Reddit kw '{kw}' FAIL: {e}")

print(f"\nTotal: {len(signals)} signals in {round(time.time()-t0,1)}s")

# Cluster
clusters = clusterer.cluster(signals, min_similarity=0.35)
clusters = [c for c in clusters if len(c) >= 2]
clusters.sort(key=len, reverse=True)
clusters = clusters[:20]
print(f"Clusters: {len(clusters)} (>=2 signals each)")

# Build opportunity reports with supplier lookup
reports = []
for c in clusters[:10]:  # top 10 clusters
    kw = clusterer.cluster_keyword(c)
    if not kw:
        continue
    rpt = opportunity_report.build(kw, c, [])  # skip supplier lookup for speed
    reports.append(rpt)

reports.sort(key=lambda r: r["scores"]["overall"], reverse=True)

print(f"\n{'='*60}")
print(f"TOP PRODUCT OPPORTUNITIES (scored)")
print(f"{'='*60}")
for i, r in enumerate(reports[:10], 1):
    s = r["scores"]
    pk = r.get('product_keyword', r.get('keyword', '?'))
    print(f"\n{i}. {pk.upper()}")
    print(f"   Overall Score: {round(s['overall']*100)}/100")
    print(f"   Signals: {r.get('n_signals', 0)}")
    print(f"   Demand: {round(s.get('demand_velocity',0)*100)} | Intent: {round(s.get('buyer_intent',0)*100)} | Content: {round(s.get('content_potential',0)*100)}")
    print(f"   Saturation: {round(s.get('low_saturation',0)*100)} | Shipping: {round(s.get('shipping_simplicity',0)*100)}")
    rec = r.get('recommendation', 'N/A')
    warnings = r.get('soft_warnings', [])
    print(f"   Recommendation: {rec.upper()}")
    if warnings:
        print(f"   Warnings: {', '.join(warnings[:2])}")

# Save full results
result = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "elapsed_sec": round(time.time() - t0, 2),
    "total_signals": len(signals),
    "n_clusters": len(clusters),
    "n_reports": len(reports),
    "reports": reports,
}
out_path = r'C:\Users\integ\Documents\Claude\Projects\ShipStack\discovery_results.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(f"\nFull results saved to discovery_results.json")
