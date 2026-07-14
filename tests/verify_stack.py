"""verify_stack.py - ShipStack stack verification (Docker-on-ALIEN edition, 2026-07-12).

Checks every ShipStack container endpoint on ALIEN, the Quinn bridge, and the
GRUNT Qdrant collections. Exits 0 only when all required checks pass.
"""
import sys
import urllib.request
import json

ALIEN = "100.66.135.31"
GRUNT = "100.124.162.86"

REQUIRED = [
    ("ShipStack Engine",    f"http://{ALIEN}:8889/health"),
    ("Prometheus Engine",   f"http://{ALIEN}:8766/health"),
    ("Social AI Agent",     f"http://{ALIEN}:8867/health"),
    ("ShipStack Dashboard", f"http://{ALIEN}:8890/"),
    ("Pipeline Dashboard",  f"http://{ALIEN}:8891/"),
    ("Quinn Bridge",        f"http://{ALIEN}:8765/health"),
]

OPTIONAL = [
    ("Context Injector (PRIME)", "http://127.0.0.1:4001/health"),
]

QDRANT_COLLECTIONS = ["dropship_intel", "strategy_books", "general_knowledge"]

def fetch(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": "verify"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()

def main():
    print("=== ShipStack Stack Verify (Docker on ALIEN) ===")
    failures = 0
    for name, url in REQUIRED:
        try:
            status, _ = fetch(url)
            print(f"[OK] {name}: {status} {url}")
        except Exception as e:
            print(f"[FAIL] {name}: {e} {url}")
            failures += 1
    for name, url in OPTIONAL:
        try:
            status, _ = fetch(url)
            print(f"[OK] {name}: {status}")
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    for col in QDRANT_COLLECTIONS:
        try:
            status, body = fetch(f"http://{GRUNT}:6333/collections/{col}")
            pts = json.loads(body)["result"].get("points_count", 0)
            tag = "[OK]" if pts and pts > 0 else "[WARN]"
            print(f"{tag} Qdrant {col}: {pts} vectors")
        except Exception as e:
            print(f"[WARN] Qdrant {col}: {e}")
    print("RESULT: " + ("PASS" if failures == 0 else f"FAIL ({failures} required checks failed)"))
    return 0 if failures == 0 else 1

if __name__ == "__main__":
    sys.exit(main())