"""
ab_testing.py — A/B Testing Engine for ShipStack
=================================================
Creates A/B (and A/B/C/D) test sets for every piece of content.
Tracks real performance metrics and declares winners.
Feeds results to the LearningEngine for continuous improvement.

Storage: SQLite via agents.db.ABTestDB (atomic increments, WAL mode)

Every post that goes out gets:
  Variant A — Control (base QA-approved content)
  Variant B — Tuned to primary avatar (e.g. Gen Z Female)
  Variant C — Tuned to secondary avatar (e.g. Budget Shopper)
  Variant D — Tuned to tertiary avatar (e.g. Busy Mom)
"""

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

from agents.db import ABTestDB, init_db

init_db()
_db = ABTestDB()


# ── Helper math ───────────────────────────────────────────────────────────────

def _calc_derived(imp: int, clicks: int, saves: int, shares: int, comments: int) -> tuple:
    imp = max(imp, 1)
    eng = clicks + saves + shares + comments
    ctr = round(clicks / imp * 100, 3)
    eng_rate = round(eng / imp * 100, 3)
    return ctr, eng_rate


# ── ABTest wrapper ────────────────────────────────────────────────────────────

class ABTest:
    """Thin wrapper around the DB row dict for backward compatibility."""

    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def create(
        cls,
        product_slug: str,
        platform: str,
        content_type: str,
        niche: str,
        variants: list,
        base_content: str = "",
    ) -> "ABTest":
        import uuid
        test_id = f"ab_{uuid.uuid4().hex[:10]}"
        # Label variants A, B, C, D if not already labeled
        labeled = []
        for i, v in enumerate(variants):
            lv = dict(v)
            lv["label"] = v.get("label", chr(65 + i))
            labeled.append(lv)
        data = _db.create(
            test_id=test_id,
            product_slug=product_slug,
            platform=platform,
            content_type=content_type,
            niche=niche,
            base_content=base_content,
            variants=labeled,
        )
        return cls(data)

    def to_dict(self) -> dict:
        return self._data

    def get_variant(self, label: str) -> Optional[dict]:
        for v in self._data.get("variants", []):
            if v["label"] == label:
                return v
        return None

    def update_metrics(self, label: str, **kwargs) -> dict:
        """Atomically increment metrics in DB."""
        result = _db.update_metrics(self._data["test_id"], label, **kwargs)
        # Refresh local data
        fresh = _db.get(self._data["test_id"])
        if fresh:
            self._data = fresh
        return result

    def calculate_winner(self, primary_metric: str = "ctr") -> Optional[dict]:
        """
        Statistical significance test (Z-test for proportions).
        Returns winner dict or None if no significant difference yet.
        Min 100 impressions per variant required.
        """
        variants = self._data.get("variants", [])
        if len(variants) < 2:
            return None

        min_impressions = min(v.get("impressions", 0) for v in variants)
        if min_impressions < 100:
            return None

        best = max(variants, key=lambda v: v.get(primary_metric, 0.0))
        control = variants[0]

        if primary_metric == "ctr":
            p1 = control.get("ctr", 0) / 100
            p2 = best.get("ctr", 0) / 100
            n1 = max(control.get("impressions", 1), 1)
            n2 = max(best.get("impressions", 1), 1)

            p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
            se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
            z = abs(p1 - p2) / max(se, 0.0001)
            is_significant = z > 1.96
        else:
            control_val = control.get(primary_metric, 0.0)
            best_val    = best.get(primary_metric, 0.0)
            lift = (best_val - control_val) / max(control_val, 0.001) * 100
            is_significant = lift >= 10 and best_val > 0

        if is_significant:
            winner_variant = best if best["label"] != "A" else control
            return {
                "winner_label":   winner_variant["label"],
                "winner_avatar":  winner_variant.get("avatar_name", "unknown"),
                "winner_content": winner_variant.get("content", ""),
                "winning_metric": primary_metric,
                "winning_value":  winner_variant.get(primary_metric),
                "control_value":  control.get(primary_metric),
                "lift_pct": round(
                    (winner_variant.get(primary_metric, 0) - control.get(primary_metric, 0))
                    / max(control.get(primary_metric, 0.001), 0.001) * 100, 1
                ),
                "confidence": "95%",
            }
        return None

    def conclude(self, primary_metric: str = "ctr") -> Optional[dict]:
        winner = self.calculate_winner(primary_metric)
        if winner:
            _db.conclude(self._data["test_id"], winner)
            self._data["status"]    = "concluded"
            self._data["winner"]    = winner
            self._data["concluded"] = datetime.now().isoformat()
        return winner

    def summary(self) -> dict:
        variants_summary = []
        for v in self._data.get("variants", []):
            variants_summary.append({
                "label":           v["label"],
                "avatar":          v.get("avatar_name", ""),
                "impressions":     v.get("impressions", 0),
                "ctr":             v.get("ctr", 0.0),
                "engagement_rate": v.get("engagement_rate", 0.0),
                "conversions":     v.get("conversions", 0),
                "revenue":         v.get("revenue", 0.0),
                "content_preview": (v.get("content", "")[:80] + "…") if v.get("content") else "",
            })
        return {
            "test_id":  self._data["test_id"],
            "product":  self._data.get("product_slug"),
            "platform": self._data.get("platform"),
            "status":   self._data.get("status"),
            "winner":   self._data.get("winner"),
            "variants": variants_summary,
        }


# ── ABTestManager ─────────────────────────────────────────────────────────────

class ABTestManager:
    """Creates, saves, loads, and manages all A/B tests via SQLite."""

    def create_test(
        self,
        base_content: str,
        product_slug: str,
        platform: str,
        content_type: str,
        niche: str = "default",
        max_avatars: int = 3,
    ) -> ABTest:
        from agents.avatar_engine import AvatarEngine
        engine = AvatarEngine()

        variants = [{
            "avatar_id":   "control",
            "avatar_name": "Control (Base)",
            "content":     base_content,
        }]

        print(f"  [AB] Generating {max_avatars} avatar variants for {platform}…")
        avatar_variants = engine.generate_all_avatar_variants(
            base_content, content_type, product_slug, platform, niche, max_avatars
        )
        variants.extend(avatar_variants)

        test = ABTest.create(product_slug, platform, content_type, niche, variants, base_content)
        return test

    def create_tests_for_approved_content(
        self,
        approved_content_path: str,
        max_per_platform: int = 5,
        max_avatars: int = 3,
    ) -> list:
        with open(approved_content_path) as f:
            approved = json.load(f)

        slug  = approved_content_path.split("/")[-2] if "/" in approved_content_path else "product"
        niche = approved.get("niche", "default")

        platform_map = {
            "tiktok":    "tiktok_script",
            "instagram": "instagram_caption",
            "youtube":   "youtube_description",
            "ad_hooks":  "ad_hook",
        }

        all_tests = []
        for platform_key, content_type in platform_map.items():
            items = approved.get("content", {}).get(platform_key, [])
            top_items = sorted(items, key=lambda x: x.get("qa_score", 0), reverse=True)[:max_per_platform]

            for item in top_items:
                content = (item.get("final_text") or item.get("script")
                           or item.get("caption") or item.get("content", ""))
                platform = platform_key if platform_key != "ad_hooks" else "ad_hook"
                if not content:
                    continue
                test = self.create_test(content, slug, platform, content_type, niche, max_avatars)
                all_tests.append(test)
                print(f"  [AB] Created test {test.to_dict()['test_id']} for {platform}")

        print(f"[AB] Created {len(all_tests)} A/B tests total")
        return all_tests

    def load_test(self, test_id: str) -> Optional[ABTest]:
        data = _db.get(test_id)
        return ABTest(data) if data else None

    def list_tests(self, product_slug: str = None, status: str = None, platform: str = None) -> list:
        return _db.list(product_slug=product_slug, status=status, platform=platform)

    def record_performance(
        self,
        test_id: str,
        variant_label: str,
        impressions: int = 0,
        clicks: int = 0,
        saves: int = 0,
        shares: int = 0,
        comments: int = 0,
        link_clicks: int = 0,
        conversions: int = 0,
        revenue: float = 0.0,
        traffic_source: dict = None,
    ) -> dict:
        """Record real performance data. Atomic increments — safe for concurrent webhooks."""
        test = self.load_test(test_id)
        if not test:
            return {"error": f"Test {test_id} not found"}

        test.update_metrics(
            variant_label,
            impressions=impressions,
            clicks=clicks,
            saves=saves,
            shares=shares,
            comments=comments,
            link_clicks=link_clicks,
            conversions=conversions,
            revenue=revenue,
            **({"traffic_source": traffic_source} if traffic_source else {}),
        )

        winner = test.conclude("ctr")
        if winner:
            print(f"[AB] Winner: {test_id} → Variant {winner['winner_label']} "
                  f"({winner['winner_avatar']}) +{winner['lift_pct']}% CTR")
            self._notify_learning_engine(test, winner)

        return test.summary()

    def check_all_for_winners(self) -> list:
        winners = []
        for data in self.list_tests(status="active"):
            test = ABTest(data)
            winner = test.conclude("ctr")
            if winner:
                winners.append({"test_id": data["test_id"], "winner": winner})
                self._notify_learning_engine(test, winner)
        return winners

    def get_dashboard_data(self, product_slug: str = None) -> dict:
        return _db.dashboard_data(product_slug=product_slug)

    def _notify_learning_engine(self, test: ABTest, winner: dict):
        try:
            from agents.learning_engine import LearningEngine
            le = LearningEngine()
            le.ingest_ab_winner(test.to_dict(), winner)
        except Exception as e:
            print(f"[AB] Could not notify LearningEngine: {e}")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    mgr = ABTestManager()

    if len(sys.argv) >= 2 and sys.argv[1] == "list":
        slug  = sys.argv[2] if len(sys.argv) > 2 else None
        tests = mgr.list_tests(product_slug=slug)
        print(f"{'Test ID':30} {'Platform':12} {'Status':12} {'Variants':8} {'Winner'}")
        for t in tests[:20]:
            w = t.get("winner") or {}
            winner_str = f"Variant {w.get('winner_label')} +{w.get('lift_pct')}%" if w else "—"
            print(f"  {t['test_id']:30} {t.get('platform',''):12} {t.get('status',''):12} "
                  f"{len(t.get('variants',[]))}       {winner_str}")

    elif len(sys.argv) >= 2 and sys.argv[1] == "check-winners":
        winners = mgr.check_all_for_winners()
        print(f"Found {len(winners)} new winners:")
        for w in winners:
            print(f"  {w['test_id']}: {w['winner']['winner_avatar']} +{w['winner']['lift_pct']}%")

    elif len(sys.argv) >= 2 and sys.argv[1] == "dashboard":
        slug = sys.argv[2] if len(sys.argv) > 2 else None
        data = mgr.get_dashboard_data(slug)
        print(json.dumps(data, indent=2))

    else:
        print("Usage:")
        print("  python ab_testing.py list [product_slug]")
        print("  python ab_testing.py check-winners")
        print("  python ab_testing.py dashboard [product_slug]")
