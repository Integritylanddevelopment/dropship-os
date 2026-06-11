"""CLI entry point. Run with: python -m discovery_engine.cli [subcommand]"""
import argparse, json, sys, os, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except: pass

from discovery_engine.pipeline import run, collect_all_signals, find_suppliers
from discovery_engine.signals import reddit_signals, google_trends, youtube_signals, amazon_movers, etsy_trending, pinterest_signals
from discovery_engine.suppliers import cj_dropshipping, spocket

def main():
    p = argparse.ArgumentParser(description="ShipStack Discovery Engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Full discovery pass")
    p_run.add_argument("--out", default=None)
    p_run.add_argument("--quiet", action="store_true")
    p_run.add_argument("--max", type=int, default=20)

    p_sup = sub.add_parser("suppliers", help="Search suppliers for one keyword")
    p_sup.add_argument("keyword")

    p_verify = sub.add_parser("verify", help="Smoke test every source")

    args = p.parse_args()

    if args.cmd == "run":
        out = args.out or os.path.join(os.path.dirname(__file__), "runs", f"run_{int(time.time())}.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        r = run(verbose=not args.quiet, out_path=out)
        top = r["reports"][:args.max]
        print(f"\n=== TOP {len(top)} OPPORTUNITIES ===")
        for i, rpt in enumerate(top, 1):
            print(f"{i:>2}. [{rpt['recommendation'].upper():<6}] {rpt['product_keyword']:<30} overall={rpt['scores']['overall']:.2f} signals={rpt['n_signals']} suppliers={rpt['n_suppliers']}")
        print(f"\nFull JSON: {out}")
        return

    if args.cmd == "suppliers":
        sup = find_suppliers(args.keyword)
        print(json.dumps(sup, indent=2, ensure_ascii=False)[:8000])
        print(f"\n{len(sup)} suppliers found for '{args.keyword}'")
        return

    if args.cmd == "verify":
        print("Smoke testing each source...")
        tests = [
            ("reddit Pullpush",       lambda: reddit_signals.collect_subreddit("dropshipping", limit=5)),
            ("google trends daily",   lambda: google_trends.collect_daily()),
            ("youtube search",        lambda: youtube_signals.collect_keyword("kitchen gadget", limit=5)),
            ("amazon movers",         lambda: amazon_movers.collect_category("pet-supplies", limit=5)),
            ("etsy /trending",        lambda: etsy_trending.collect_trending(limit=5)),
            ("etsy keyword",          lambda: etsy_trending.collect_keyword("pet collar", limit=5)),
            ("pinterest keyword",     lambda: pinterest_signals.collect_keyword("kitchen gadget", limit=5)),
            ("CJdropshipping",        lambda: cj_dropshipping.search("pet collar", limit=5)),
            ("Spocket",               lambda: spocket.search("pet collar", limit=5)),
        ]
        results = []
        for name, fn in tests:
            t = time.time()
            try:
                r = fn()
                results.append((name, len(r), round(time.time()-t,2), None))
            except Exception as e:
                results.append((name, 0, round(time.time()-t,2), str(e)[:80]))
        print(f"\n{'SOURCE':<28} {'ITEMS':>6} {'SEC':>6}  ERROR")
        for n, k, s, e in results:
            print(f"{n:<28} {k:>6} {s:>6.2f}  {e or ''}")
        return

if __name__ == "__main__":
    main()