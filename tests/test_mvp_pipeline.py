import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""
ShipStack MVP Pipeline Smoke Test
==================================
Tests the full pipeline: discover -> score -> generate content -> post to social.

Run:  python tests/test_mvp_pipeline.py
"""

import json
import os
import re
import time
import subprocess

try:
    import requests
except ImportError:
    print("[FAIL] 'requests' package not installed. Run: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_ENGINE = "http://localhost:8889"
BASE_SOCIAL = "http://localhost:8867"
BASE_PROMETHEUS = "http://localhost:8766"
TIMEOUT = 30

# Track results
results = []  # list of (name, status, message)


def record(name, status, message):
    results.append((name, status, message))
    tag = {"pass": "[PASS]", "fail": "[FAIL]", "skip": "[SKIP]"}[status]
    print(f"  {tag} {name} -- {message}")


# ---------------------------------------------------------------------------
# 1. Service Health Checks
# ---------------------------------------------------------------------------

def test_health_checks():
    print("\n--- 1. Service Health Checks ---")
    services = [
        ("ShipStack Engine :8889", f"{BASE_ENGINE}/health"),
        ("Social AI Agent :8867", f"{BASE_SOCIAL}/health"),
        ("Prometheus Engine :8766", f"{BASE_PROMETHEUS}/health"),
    ]
    for name, url in services:
        try:
            r = requests.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                record(name, "pass", f"HTTP 200 -- {r.json().get('status', r.json().get('ok', 'unknown'))}")
            else:
                record(name, "fail", f"HTTP {r.status_code}")
        except requests.ConnectionError:
            record(name, "fail", f"Connection refused at {url}")
        except Exception as e:
            record(name, "fail", str(e))


# ---------------------------------------------------------------------------
# 2. Platform Credential Check
# ---------------------------------------------------------------------------

def test_platform_credentials():
    print("\n--- 2. Platform Credential Check ---")
    try:
        r = requests.get(f"{BASE_SOCIAL}/platforms", timeout=TIMEOUT)
        if r.status_code != 200:
            record("Platform credentials", "fail", f"HTTP {r.status_code}")
            return
        data = r.json()
        configured = []
        not_configured = []
        for platform, info in data.items():
            if isinstance(info, dict) and info.get("configured"):
                configured.append(platform)
            else:
                not_configured.append(platform)
        summary = f"Configured: {configured or 'none'}  |  Not configured: {not_configured or 'none'}"
        record("Platform credentials", "pass", summary)
    except requests.ConnectionError:
        record("Platform credentials", "skip", "Social AI Agent not reachable at :8867")
    except Exception as e:
        record("Platform credentials", "fail", str(e))


# ---------------------------------------------------------------------------
# 3. Product Discovery
# ---------------------------------------------------------------------------

def test_product_discovery():
    print("\n--- 3. Product Discovery ---")
    try:
        payload = {"query": "portable blender", "sources": ["trends"]}
        r = requests.post(f"{BASE_ENGINE}/api/discover", json=payload, timeout=TIMEOUT)
        if r.status_code == 503:
            record("Product discovery", "skip", "Discovery pipeline not loaded (503)")
            return
        if r.status_code != 200:
            record("Product discovery", "fail", f"HTTP {r.status_code} -- {r.text[:200]}")
            return
        data = r.json()
        if data.get("status") == "ok":
            count = data.get("total_signals", data.get("n_reports", 0))
            record("Product discovery", "pass", f"Returned {count} signals / {data.get('n_reports', '?')} reports")
        else:
            record("Product discovery", "fail", f"Unexpected status: {data.get('status')}")
    except requests.ConnectionError:
        record("Product discovery", "fail", "Engine not reachable at :8889")
    except Exception as e:
        record("Product discovery", "fail", str(e))


# ---------------------------------------------------------------------------
# 4. Product Scoring
# ---------------------------------------------------------------------------

def test_product_scoring():
    print("\n--- 4. Product Scoring ---")
    sample_product = {
        "product": {
            "id": "test-001",
            "title": "Portable Blender USB Rechargeable",
            "price": 12.99,
            "supplier": "AliExpress",
            "reviews": 4500,
            "rating": 4.6,
            "niche": "kitchen gadgets",
            "description": "Personal size blender for smoothies and shakes"
        }
    }
    try:
        r = requests.post(f"{BASE_ENGINE}/api/score", json=sample_product, timeout=TIMEOUT)
        if r.status_code == 503:
            record("Product scoring", "skip", "Decision engine not loaded (503)")
            return
        if r.status_code != 200:
            record("Product scoring", "fail", f"HTTP {r.status_code} -- {r.text[:200]}")
            return
        data = r.json()
        if data.get("status") == "ok" and "decision" in data:
            score = data["decision"].get("score", "?")
            record("Product scoring", "pass", f"Score: {score}")
        else:
            record("Product scoring", "fail", f"Unexpected response: {json.dumps(data)[:200]}")
    except requests.ConnectionError:
        record("Product scoring", "fail", "Engine not reachable at :8889")
    except Exception as e:
        record("Product scoring", "fail", str(e))


# ---------------------------------------------------------------------------
# 5. Full Recommendation Pipeline
# ---------------------------------------------------------------------------

def test_recommendation_pipeline():
    print("\n--- 5. Full Recommendation Pipeline ---")
    try:
        payload = {"query": "portable blender", "limit": 3}
        r = requests.post(f"{BASE_ENGINE}/api/recommend", json=payload, timeout=TIMEOUT)
        if r.status_code == 503:
            record("Recommendation pipeline", "skip", "Discovery or decision engine not loaded (503)")
            return
        if r.status_code != 200:
            record("Recommendation pipeline", "fail", f"HTTP {r.status_code} -- {r.text[:200]}")
            return
        data = r.json()
        if data.get("status") == "ok":
            recs = data.get("recommendations", [])
            has_channels = any("channels" in rec for rec in recs)
            record("Recommendation pipeline", "pass",
                   f"{len(recs)} recommendations, channels present: {has_channels}")
        else:
            record("Recommendation pipeline", "fail", f"Unexpected status: {data.get('status')}")
    except requests.ConnectionError:
        record("Recommendation pipeline", "fail", "Engine not reachable at :8889")
    except Exception as e:
        record("Recommendation pipeline", "fail", str(e))


# ---------------------------------------------------------------------------
# 6. Product Card Generation
# ---------------------------------------------------------------------------

def test_card_generation():
    print("\n--- 6. Product Card Generation ---")
    try:
        payload = {
            "product": "Portable Blender USB Rechargeable",
            "niche": "kitchen gadgets",
            "margin": 65,
            "score": 8.2,
        }
        r = requests.post(f"{BASE_SOCIAL}/generate-card", json=payload, timeout=TIMEOUT)
        if r.status_code == 503:
            record("Card generation", "skip", "Pillow not installed or service unavailable (503)")
            return
        if r.status_code != 200:
            record("Card generation", "fail", f"HTTP {r.status_code} -- {r.text[:200]}")
            return
        data = r.json()
        if data.get("status") == "generated":
            card_path = data.get("card_path", "unknown")
            record("Card generation", "pass", f"Card created at {card_path}")
        else:
            record("Card generation", "fail", f"Unexpected status: {data.get('status')}")
    except requests.ConnectionError:
        record("Card generation", "skip", "Social AI Agent not reachable at :8867")
    except Exception as e:
        record("Card generation", "fail", str(e))


# ---------------------------------------------------------------------------
# 7. Pinterest Post (Dry Run)
# ---------------------------------------------------------------------------

def test_pinterest_post():
    print("\n--- 7. Pinterest Post (Dry Run) ---")
    pinterest_token = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
    if not pinterest_token:
        record("Pinterest post", "skip", "PINTEREST_ACCESS_TOKEN not set -- skipping real post")
        return
    try:
        payload = {
            "title": "[SMOKE TEST] Portable Blender",
            "description": "Smoke test pin -- safe to delete",
            "image_url": "https://via.placeholder.com/600x600.png?text=ShipStack+Test",
        }
        r = requests.post(f"{BASE_SOCIAL}/post/pinterest", json=payload, timeout=TIMEOUT)
        if r.status_code == 503:
            record("Pinterest post", "skip", "Pinterest poster not configured (503)")
            return
        if r.status_code == 200 and r.json().get("status") == "posted":
            record("Pinterest post", "pass", "Pin posted successfully")
        else:
            record("Pinterest post", "fail", f"HTTP {r.status_code} -- {r.text[:200]}")
    except requests.ConnectionError:
        record("Pinterest post", "skip", "Social AI Agent not reachable at :8867")
    except Exception as e:
        record("Pinterest post", "fail", str(e))


# ---------------------------------------------------------------------------
# 8. YouTube Post Check
# ---------------------------------------------------------------------------

def test_youtube_check():
    print("\n--- 8. YouTube Post Check ---")
    try:
        r = requests.get(f"{BASE_SOCIAL}/platforms", timeout=TIMEOUT)
        if r.status_code != 200:
            record("YouTube check", "fail", f"HTTP {r.status_code} from /platforms")
            return
        data = r.json()
        yt = data.get("youtube", {})
        if isinstance(yt, dict):
            configured = yt.get("configured", False)
            if configured:
                record("YouTube check", "pass", "YouTubePoster available and configured")
            else:
                record("YouTube check", "skip",
                       f"YouTubePoster listed but not configured (env vars: {yt.get('env_vars', '?')})")
        else:
            record("YouTube check", "skip", "YouTube platform not listed in /platforms response")
    except requests.ConnectionError:
        record("YouTube check", "skip", "Social AI Agent not reachable at :8867")
    except Exception as e:
        record("YouTube check", "fail", str(e))


# ---------------------------------------------------------------------------
# 9. Pipeline Glue Test
# ---------------------------------------------------------------------------

def test_pipeline_glue():
    print("\n--- 9. Pipeline Glue Test ---")
    # Determine project root (tests/ is one level below)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    glue_path = os.path.join(project_root, "engines", "pipeline_glue.py")
    if not os.path.exists(glue_path):
        # Also check project root
        glue_path = os.path.join(project_root, "pipeline_glue.py")
        if not os.path.exists(glue_path):
            record("Pipeline glue", "skip", "pipeline_glue.py not found")
            return

    # Add project root and engines dir to sys.path for import resolution
    for p in [project_root, os.path.join(project_root, "engines")]:
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        if "pipeline_glue" in sys.modules:
            del sys.modules["pipeline_glue"]
        from pipeline_glue import run_full_pipeline
        manifest = run_full_pipeline(limit=2)
        if not isinstance(manifest, dict):
            record("Pipeline glue", "fail", f"Expected dict, got {type(manifest).__name__}")
            return
        status = manifest.get("status", "unknown")
        products = manifest.get("products", [])
        cards = manifest.get("cards", [])
        errors = manifest.get("errors", [])
        record("Pipeline glue", "pass" if status in ("ok", "partial") else "fail",
               f"status={status}, products={len(products)}, cards={len(cards)}, errors={len(errors)}")
    except ImportError as e:
        record("Pipeline glue", "skip", f"Import failed: {e}")
    except requests.ConnectionError:
        record("Pipeline glue", "fail", "Pipeline failed -- services not reachable")
    except Exception as e:
        record("Pipeline glue", "fail", f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 10. Anthropic Leak Audit
# ---------------------------------------------------------------------------

def test_anthropic_leak():
    print("\n--- 10. Anthropic Leak Audit ---")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    patterns = [
        r"api\.anthropic\.com",
        r"ANTHROPIC_API_KEY",
        r"sk-ant-",
        r"from anthropic",
        r"import anthropic",
    ]
    exclude_dirs = {".git", "node_modules", ".env", ".env.local", "__pycache__",
                    ".venv", "venv", "env", ".next"}
    exclude_files = {".env", ".env.local", ".env.example"}
    violations = []

    for dirpath, dirnames, filenames in os.walk(project_root):
        # Prune excluded directories
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        rel_dir = os.path.relpath(dirpath, project_root)

        for fname in filenames:
            if fname in exclude_files:
                continue
            # Only scan text-like files
            if not fname.endswith(('.py', '.js', '.ts', '.jsx', '.tsx', '.json',
                                   '.yaml', '.yml', '.toml', '.cfg', '.ini',
                                   '.sh', '.ps1', '.md', '.html', '.css')):
                continue
            # Allow this test file itself
            fpath = os.path.join(dirpath, fname)
            if os.path.abspath(fpath) == os.path.abspath(__file__):
                continue

            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                for pat in patterns:
                    matches = re.findall(pat, content)
                    if matches:
                        rel_path = os.path.relpath(fpath, project_root)
                        violations.append(f"{rel_path}: matched '{pat}' ({len(matches)}x)")
            except Exception:
                pass  # skip unreadable files

    if violations:
        for v in violations[:10]:
            print(f"    !! {v}")
        if len(violations) > 10:
            print(f"    ... and {len(violations) - 10} more")
        record("Anthropic leak audit", "fail", f"{len(violations)} violation(s) found")
    else:
        record("Anthropic leak audit", "pass", "No direct Anthropic references in source")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary():
    total = len(results)
    passed = sum(1 for _, s, _ in results if s == "pass")
    failed = sum(1 for _, s, _ in results if s == "fail")
    skipped = sum(1 for _, s, _ in results if s == "skip")

    print("\n" + "=" * 60)
    print(f"  MVP SMOKE TEST SUMMARY")
    print(f"  Total: {total}  |  Passed: {passed}  |  Failed: {failed}  |  Skipped: {skipped}")
    print("=" * 60)

    if failed > 0:
        print("\n  Failed tests:")
        for name, status, msg in results:
            if status == "fail":
                print(f"    - {name}: {msg}")

    if skipped > 0:
        print("\n  Skipped tests:")
        for name, status, msg in results:
            if status == "skip":
                print(f"    - {name}: {msg}")

    print()
    return failed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  ShipStack MVP Pipeline Smoke Test")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    test_health_checks()
    test_platform_credentials()
    test_product_discovery()
    test_product_scoring()
    test_recommendation_pipeline()
    test_card_generation()
    test_pinterest_post()
    test_youtube_check()
    test_pipeline_glue()
    test_anthropic_leak()

    failed = print_summary()
    sys.exit(1 if failed > 0 else 0)
