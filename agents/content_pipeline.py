"""
content_pipeline.py — Full Content Pipeline for ShipStack
==========================================================
Combines ContentSpinner + ContentQA into one command:
  1. Spin Quinn output → 430 unique pieces
  2. QA every piece (parallel) → score, auto-fix failures
  3. Sort into pass/review/fail buckets
  4. Save only PASS+REVIEW pieces to calendar
  5. Dump FAIL pieces with rewrite suggestions

Run:
  python content_pipeline.py <product_slug> [profile_count] [--taste-test-only]
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def run_pipeline(
    product_slug: str,
    profile_count: int = 1,
    taste_test_only: bool = False,
    qa_workers: int = 6,
    auto_fix: bool = True,
) -> dict:
    from agents.content_spinner import ContentSpinner
    from agents.content_qa import ContentQA

    # ── Load Quinn output ────────────────────────────────────────────────────
    quinn_path = BASE_DIR / "data" / "product_collateral" / product_slug / "quinn_output.json"
    if not quinn_path.exists():
        return {"error": f"quinn_output.json not found for slug: {product_slug}"}

    quinn_output = json.loads(quinn_path.read_text())
    product_name = quinn_output.get("product_name", product_slug.replace("_", " ").title())
    niche        = quinn_output.get("niche", "default")

    print(f"\n{'='*60}")
    print(f"  ShipStack Content Pipeline")
    print(f"  Product : {product_name}")
    print(f"  Niche   : {niche}")
    print(f"  Profiles: {profile_count}")
    print(f"{'='*60}\n")

    # ── Spin ─────────────────────────────────────────────────────────────────
    t0 = time.time()
    spinner = ContentSpinner()
    print("[1/3] Spinning content variations…")
    spin_results = spinner.spin_product(quinn_output, product_name, niche, profile_count)

    if taste_test_only:
        print("\n[TASTE TEST MODE] Sampling 5 from each platform…")
        qa = ContentQA(auto_fix=auto_fix)
        report = qa.taste_test(spin_results, sample_size=5)
        _print_taste_test(report)
        return report

    spin_time = time.time() - t0
    print(f"  Spin complete: {spin_results['totals']['unique_pieces']} pieces in {spin_time:.1f}s\n")

    # ── QA ───────────────────────────────────────────────────────────────────
    print("[2/3] Running Quality Assurance on all content…")
    qa = ContentQA(auto_fix=auto_fix)
    qa_results = {}

    platform_map = {
        "tiktok":    ("tiktok_script",       "tiktok"),
        "instagram": ("instagram_caption",    "instagram"),
        "youtube":   ("youtube_description",  "youtube"),
        "ad_hooks":  ("ad_hook",             "ad_hook"),
    }

    total_pass = 0
    total_fail = 0
    total_review = 0

    for key, (content_type, platform) in platform_map.items():
        variations = spin_results["spins"].get(key, [])
        if not variations:
            continue
        print(f"  QA: {platform} ({len(variations)} pieces)…")
        result = qa.qa_batch(variations, content_type, platform, product_name, niche, workers=qa_workers)
        qa_results[key] = result
        total_pass   += result["stats"]["pass"]
        total_review += result["stats"]["review"]
        total_fail   += result["stats"]["fail"]

    qa_time = time.time() - t0 - spin_time
    print(f"  QA complete in {qa_time:.1f}s\n")

    # ── Save results ─────────────────────────────────────────────────────────
    print("[3/3] Saving approved content…")
    out_dir = BASE_DIR / "data" / "product_collateral" / product_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save all QA results
    qa_out = out_dir / "qa_results.json"
    qa_out.write_text(json.dumps(qa_results, indent=2))

    # Save only PASS + REVIEW pieces as "approved_content.json"
    approved = {}
    rejected = {}
    for key, result in qa_results.items():
        approved[key] = result["pass"] + result["review"]
        rejected[key] = result["fail"]

    approved_out = out_dir / "approved_content.json"
    approved_out.write_text(json.dumps({
        "product": product_name,
        "niche": niche,
        "profile_count": profile_count,
        "content": approved,
        "totals": {
            k: len(v) for k, v in approved.items()
        },
    }, indent=2))

    rejected_out = out_dir / "rejected_content.json"
    rejected_out.write_text(json.dumps({
        "product": product_name,
        "rejected": rejected,
        "note": "These pieces failed QA 3x. Review weak_areas in each item for rewrite hints.",
    }, indent=2))

    # ── Index approved content into ChromaDB for semantic search ─────────────
    try:
        from agents.db import ContentDB
        cdb = ContentDB()
        indexed = cdb.store_approved_batch(str(approved_out), product_slug, niche)
        print(f"  [DB] Indexed {indexed} pieces into ChromaDB ✓")
    except Exception as e:
        print(f"  [DB] ChromaDB indexing skipped: {e}")

    total_approved = total_pass + total_review
    total_pieces   = total_pass + total_review + total_fail

    # ── Print summary ─────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE  ({elapsed:.0f}s)")
    print(f"{'='*60}")
    print(f"  Total spun    : {total_pieces:,}")
    print(f"  ✅ Approved   : {total_approved:,} ({round(total_approved/total_pieces*100)}%)")
    print(f"     Pass       : {total_pass:,}")
    print(f"     Review     : {total_review:,}  ← needs your eyes before posting")
    print(f"  ❌ Rejected   : {total_fail:,}  (saved to rejected_content.json with fix hints)")
    print(f"\n  With {profile_count} profiles:")
    tt_approved = len(approved.get("tiktok", [])) * profile_count
    ig_approved = len(approved.get("instagram", [])) * profile_count
    yt_approved = len(approved.get("youtube", [])) * profile_count
    print(f"    TikTok   posts: {tt_approved:,}")
    print(f"    Instagram posts: {ig_approved:,}")
    print(f"    YouTube  posts: {yt_approved:,}")
    print(f"    Total approved posts: {tt_approved+ig_approved+yt_approved:,}")
    print(f"\n  Files saved:")
    print(f"    {approved_out}")
    print(f"    {rejected_out}")
    print(f"    {qa_out}")
    print(f"{'='*60}\n")

    return {
        "product": product_name,
        "profile_count": profile_count,
        "totals": {
            "spun": total_pieces,
            "approved": total_approved,
            "pass": total_pass,
            "review": total_review,
            "rejected": total_fail,
            "pass_rate": round(total_approved / total_pieces * 100, 1) if total_pieces else 0,
        },
        "posts_with_profiles": {
            "tiktok": tt_approved,
            "instagram": ig_approved,
            "youtube": yt_approved,
            "total": tt_approved + ig_approved + yt_approved,
        },
        "files": {
            "approved": str(approved_out),
            "rejected": str(rejected_out),
            "qa_results": str(qa_out),
        },
        "elapsed_seconds": round(elapsed, 1),
    }


def _print_taste_test(report: dict):
    print(f"\n{'='*60}")
    print(f"  TASTE TEST — {report.get('product')}")
    print(f"{'='*60}")
    for sample in report.get("samples", []):
        stats = sample["stats"]
        print(f"\n  {sample['platform'].upper()} (n={sample['sample_size']})")
        print(f"    Pass: {stats['pass']} | Review: {stats['review']} | Fail: {stats['fail']}")
        print(f"    Pass rate: {stats['pass_rate']}%  |  Avg score: {stats['avg_score']}/50")
        top = sample.get("top_3", [])
        if top:
            print(f"    Top piece ({top[0].get('qa_score')}/50):")
            preview = top[0].get("final_text", "")[:100]
            print(f"      \"{preview}…\"")
    summary = report.get("summary", {})
    print(f"\n  Overall pass rate : {summary.get('overall_pass_rate')}%")
    print(f"  Recommendation    : {summary.get('recommendation')}")
    print(f"{'='*60}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python content_pipeline.py <product_slug> [profile_count] [--taste-test]")
        print("")
        print("Examples:")
        print("  python content_pipeline.py glow_serum 10")
        print("  python content_pipeline.py glow_serum 1 --taste-test")
        sys.exit(0)

    slug          = sys.argv[1]
    profile_count = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 1
    taste_test    = "--taste-test" in sys.argv

    result = run_pipeline(slug, profile_count, taste_test_only=taste_test)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
