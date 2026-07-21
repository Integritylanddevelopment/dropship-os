import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""Category rotation driver — runs the Mission Control pipeline across many
product categories back to back, logging results. Two full cycles, then stops."""
import json
import time
from datetime import datetime
from pathlib import Path

import requests

ENGINE = "http://127.0.0.1:8889"
ROOT = Path(__file__).parent
OUT_JSONL = ROOT / "logs" / "rotation_results.jsonl"
OUT_TXT = ROOT / "logs" / "rotation_report.txt"

CATEGORIES = [
    "health and wellness",
    "pet accessories",
    "home decor",
    "yard and garden",
    "camping and outdoor",
    "kitchen gadgets",
    "fitness gear",
    "car accessories",
]

CYCLES = 2


def wait_idle(timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            st = requests.get(f"{ENGINE}/api/pipeline/status", timeout=5).json()
            if not st.get("running"):
                return st
        except Exception:
            pass
        time.sleep(5)
    return None


def run_category(cat):
    r = requests.post(f"{ENGINE}/api/pipeline/start", json={
        "query": cat, "platforms": ["pinterest"], "limit": 5,
    }, timeout=10)
    if not r.ok:
        return {"category": cat, "error": f"start failed: {r.text[:200]}"}
    # wait for completion
    time.sleep(15)
    st = wait_idle(timeout=420)
    if st is None:
        return {"category": cat, "error": "timed out waiting for completion"}
    return {
        "category": cat,
        "at": datetime.now().isoformat(),
        "summary": st.get("summary"),
        "error": st.get("error"),
        "stages": {k: v.get("detail") for k, v in (st.get("stages") or {}).items()},
        "products": [
            {"title": p.get("title"), "score": p.get("score"),
             "margin_pct": p.get("margin_pct"), "rec": p.get("recommendation"),
             "hooks": p.get("hooks"), "card_url": p.get("card_url")}
            for p in (st.get("products") or [])
        ],
        "posts": [
            {"platform": x.get("platform"), "product": x.get("product"),
             "status": x.get("status"), "detail": (x.get("detail") or "")[:120]}
            for x in (st.get("posts") or [])
        ],
    }


def main():
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    all_results = []
    for cycle in range(1, CYCLES + 1):
        for cat in CATEGORIES:
            # make sure engine is idle first
            wait_idle(timeout=420)
            res = run_category(cat)
            res["cycle"] = cycle
            all_results.append(res)
            with open(OUT_JSONL, "a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            time.sleep(10)  # breathe between categories

    # Readable report
    lines = [f"ROTATION REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
             "=" * 60]
    for r in all_results:
        lines.append(f"\n[cycle {r.get('cycle')}] {r['category'].upper()}")
        if r.get("error"):
            lines.append(f"  ERROR: {r['error']}")
            continue
        lines.append(f"  {r.get('summary', '')}")
        for p in r.get("products", []):
            lines.append(f"  - {p['title']}  score={p['score']:.2f}  margin={p['margin_pct']*100:.0f}%  rec={p['rec']}")
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("rotation complete")


if __name__ == "__main__":
    main()
