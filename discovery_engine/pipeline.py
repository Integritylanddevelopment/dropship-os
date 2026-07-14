"""Discovery engine pipeline orchestrator.

Workflow per the spec:
1. Scan downstream signals.
2. Extract candidates.
3. Cluster.
4. Trend velocity.
5. Buyer intent.
6. Saturation check (heuristic for now).
7. Upstream supplier search.
8. Match.
9. Margin.
10. Score.
11. Rank.
12. Recommend content focus.
"""
import json, time, os, sys, random

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from discovery_engine.signals import reddit_signals, google_trends, youtube_signals, amazon_movers, etsy_trending, pinterest_signals
    from discovery_engine.suppliers import cj_dropshipping, spocket, aliexpress
    from discovery_engine.scoring import clusterer, opportunity_report
else:
    from .signals import reddit_signals, google_trends, youtube_signals, amazon_movers, etsy_trending, pinterest_signals
    from .suppliers import cj_dropshipping, spocket, aliexpress
    from .scoring import clusterer, opportunity_report


DEFAULT_SUBREDDITS = ["BuyItForLife", "shutupandtakemymoney", "INEEEEDIT", "dropshipping", "ofcoursethatsathing"]
DEFAULT_KEYWORDS = ["pet accessories", "kitchen gadget", "fitness", "home decor", "led lights"]
DEFAULT_AMAZON_CATS = ["pet-supplies", "home-garden", "kitchen", "beauty", "health-personal-care"]


def collect_all_signals(subreddits=None, keywords=None, amazon_cats=None, verbose=True) -> list:
    subreddits = subreddits if subreddits is not None else DEFAULT_SUBREDDITS
    keywords = keywords if keywords is not None else DEFAULT_KEYWORDS
    amazon_cats = amazon_cats if amazon_cats is not None else DEFAULT_AMAZON_CATS
    out = []
    # randomize batch order so we don't always hit hosts in the same sequence
    subreddits = list(subreddits); random.shuffle(subreddits)
    keywords = list(keywords); random.shuffle(keywords)
    amazon_cats = list(amazon_cats); random.shuffle(amazon_cats)
    def _log(msg):
        if verbose: print(f"[signals] {msg}", flush=True)

    for sub in subreddits:
        try:
            sigs = reddit_signals.collect_subreddit(sub, limit=50, sort="score")
            out.extend(sigs); _log(f"reddit r/{sub}: {len(sigs)}")
        except Exception as e: _log(f"reddit r/{sub} FAIL: {e}")

    for kw in keywords:
        try:
            sigs = reddit_signals.collect_keyword(kw, limit=25)
            out.extend(sigs); _log(f"reddit kw '{kw}': {len(sigs)}")
        except Exception as e: _log(f"reddit kw '{kw}' FAIL: {e}")

        try:
            sigs = youtube_signals.collect_keyword(kw, limit=15)
            out.extend(sigs); _log(f"youtube '{kw}': {len(sigs)}")
        except Exception as e: _log(f"youtube '{kw}' FAIL: {e}")

        try:
            sigs = etsy_trending.collect_keyword(kw, limit=15)
            out.extend(sigs); _log(f"etsy '{kw}': {len(sigs)}")
        except Exception as e: _log(f"etsy '{kw}' FAIL: {e}")

        try:
            sigs = pinterest_signals.collect_keyword(kw, limit=15)
            out.extend(sigs); _log(f"pinterest '{kw}': {len(sigs)}")
        except Exception as e: _log(f"pinterest '{kw}' FAIL: {e}")

    for cat in amazon_cats:
        try:
            sigs = amazon_movers.collect_category(cat, limit=15)
            out.extend(sigs); _log(f"amazon-movers {cat}: {len(sigs)}")
        except Exception as e: _log(f"amazon-movers {cat} FAIL: {e}")

    try:
        sigs = etsy_trending.collect_trending(limit=20)
        out.extend(sigs); _log(f"etsy /trending: {len(sigs)}")
    except Exception as e: _log(f"etsy /trending FAIL: {e}")

    try:
        sigs = google_trends.collect_daily(geo="US")
        out.extend(sigs); _log(f"google trends US: {len(sigs)}")
    except Exception as e: _log(f"google trends FAIL: {e}")

    return out


def find_suppliers(keyword: str, verbose=True) -> list:
    out = []
    def _log(msg):
        if verbose: print(f"[suppliers] {msg}", flush=True)
    try:
        sup = cj_dropshipping.search(keyword, limit=15)
        out.extend(sup); _log(f"CJ '{keyword}': {len(sup)}")
    except Exception as e: _log(f"CJ '{keyword}' FAIL: {e}")
    try:
        sup = spocket.search(keyword, limit=15)
        out.extend(sup); _log(f"Spocket '{keyword}': {len(sup)}")
    except Exception as e: _log(f"Spocket '{keyword}' FAIL: {e}")
    try:
        sup = aliexpress.search(keyword, limit=15)
        out.extend(sup); _log(f"AliExpress '{keyword}': {len(sup)}")
    except Exception as e: _log(f"AliExpress '{keyword}' FAIL: {e}")

    return out


def run(subreddits=None, keywords=None, amazon_cats=None, max_clusters=30,
        min_cluster_size=2, verbose=True, out_path=None) -> dict:
    t0 = time.time()
    signals = collect_all_signals(subreddits, keywords, amazon_cats, verbose=verbose)
    if verbose: print(f"[pipeline] {len(signals)} total signals collected", flush=True)

    clusters = clusterer.cluster(signals, min_similarity=0.35)
    clusters = [c for c in clusters if len(c) >= min_cluster_size]
    clusters.sort(key=len, reverse=True)
    clusters = clusters[:max_clusters]
    if verbose: print(f"[pipeline] {len(clusters)} clusters >= {min_cluster_size} signals", flush=True)

    reports = []
    for c in clusters:
        kw = clusterer.cluster_keyword(c)
        if not kw: continue
        suppliers = find_suppliers(kw, verbose=verbose)
        rpt = opportunity_report.build(kw, c, suppliers)
        reports.append(rpt)

    reports.sort(key=lambda r: r["scores"]["overall"], reverse=True)

    result = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_sec": round(time.time() - t0, 2),
        "total_signals": len(signals),
        "n_clusters": len(clusters),
        "n_reports": len(reports),
        "reports": reports,
    }

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        if verbose: print(f"[pipeline] saved to {out_path}", flush=True)

    return result