"""Quick discovery test — minimal version to avoid timeouts."""
import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, time, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from discovery_engine.signals import reddit_signals, google_trends
from discovery_engine.scoring import clusterer, opportunity_report

def dedup(signals):
    seen = set()
    out = []
    for s in signals:
        sid = s.get("id") or id(s)
        if sid not in seen:
            seen.add(sid)
            out.append(s)
    return out

def main():
    t0 = time.time()
    signals = []

    # Google Trends
    try:
        sigs = google_trends.collect_daily(geo="US")
        signals.extend(sigs)
        print(f"[+] Google Trends: {len(sigs)}")
    except Exception as e:
        print(f"[!] Trends: {e}")

    # Just 2 subreddits, small limits
    for sub in ["shutupandtakemymoney", "INEEEEDIT"]:
        try:
            sigs = reddit_signals.collect_subreddit(sub, limit=15)
            signals.extend(sigs)
            print(f"[+] r/{sub}: {len(sigs)}")
        except Exception as e:
            print(f"[!] r/{sub}: {e}")

    # Just 3 keywords
    for kw in ["kitchen gadget", "pet accessory", "led lights"]:
        try:
            sigs = reddit_signals.collect_keyword(kw, limit=10)
            signals.extend(sigs)
            print(f"[+] kw '{kw}': {len(sigs)}")
        except Exception as e:
            print(f"[!] kw '{kw}': {e}")

    before = len(signals)
    signals = dedup(signals)
    elapsed = time.time() - t0
    print(f"\n{before} raw -> {len(signals)} unique in {elapsed:.0f}s\n")

    if not signals:
        print("No signals. Check network.")
        return

    # Check timestamps
    now = time.time()
    ages = []
    for s in signals:
        ts = s.get("created_utc")
        if ts:
            ages.append((now - float(ts)) / 86400)
    if ages:
        print(f"Signal ages: min={min(ages):.0f}d, max={max(ages):.0f}d, median={sorted(ages)[len(ages)//2]:.0f}d")

    clusters = clusterer.cluster(signals, min_similarity=0.35)
    clusters = [c for c in clusters if len(c) >= 2]
    clusters.sort(key=len, reverse=True)
    clusters = clusters[:15]
    print(f"{len(clusters)} clusters\n")

    reports = []
    for c in clusters:
        kw = clusterer.cluster_keyword(c)
        if not kw: continue
        rpt = opportunity_report.build(kw, c, suppliers=[])
        reports.append(rpt)

    reports.sort(key=lambda r: r["scores"]["overall"], reverse=True)

    hdr = f"{'#':<3} {'Keyword':<22} {'Score':>6} {'Vel':>5} {'Int':>5} {'Cnt':>5} {'Mrg':>5} {'Rec':<7} {'N':>3}"
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(reports[:10], 1):
        s = r["scores"]
        print(f"{i:<3} {r['product_keyword']:<22} {s['overall']:>6.3f} {s['demand_velocity']:>5.3f} {s['buyer_intent']:>5.3f} {s['content_potential']:>5.3f} {s['margin']:>5.3f} {r['recommendation']:<7} {r['n_signals']:>3}")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_discovery_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2, ensure_ascii=False)
    print(f"\nSaved. Total: {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
