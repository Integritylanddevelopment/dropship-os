"""
research/trend_engine.py — Google Trends + Niche Research Engine
No API keys required. Uses pytrends (Google Trends) + requests.

Usage:
    from research.trend_engine import TrendEngine
    engine = TrendEngine()
    results = engine.run(niches=["pet accessories", "home kitchen", "fitness tools"])
"""

import json
import time
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from pytrends.request import TrendReq

logger = logging.getLogger(__name__)

# ── Channel CPM benchmarks (manually researched, Gary Vee framework)
CHANNEL_CPM = {
    "tiktok_organic":    {"cpm": 0.00,  "viral_coeff": 1.6, "audience_type": "discovery", "priority": 1},
    "pinterest_organic": {"cpm": 0.28,  "viral_coeff": 1.4, "audience_type": "search_intent", "priority": 1},
    "youtube_shorts":    {"cpm": 0.41,  "viral_coeff": 1.2, "audience_type": "search_feed", "priority": 2},
    "instagram_reels":   {"cpm": 3.20,  "viral_coeff": 1.0, "audience_type": "discovery", "priority": 3},
    "x_twitter":         {"cpm": 5.80,  "viral_coeff": 0.9, "audience_type": "conversation", "priority": 3},
    "meta_paid":         {"cpm": 14.20, "viral_coeff": 0.8, "audience_type": "paid_interrupt", "priority": 4},
    "google_paid":       {"cpm": 22.80, "viral_coeff": 0.6, "audience_type": "search_intent", "priority": 5},
}

# ── Niche definitions with baseline margin estimates
NICHE_PROFILES = {
    "pet accessories":      {"base_margin": 72, "avg_price": 29, "competition": "medium", "supplier": "zendrop"},
    "home kitchen":         {"base_margin": 68, "avg_price": 35, "competition": "high",   "supplier": "autods"},
    "fitness tools":        {"base_margin": 55, "avg_price": 45, "competition": "high",   "supplier": "autods"},
    "desk organizers":      {"base_margin": 61, "avg_price": 22, "competition": "medium", "supplier": "aliexpress"},
    "led grow lights":      {"base_margin": 61, "avg_price": 38, "competition": "low",    "supplier": "aliexpress"},
    "posture corrector":    {"base_margin": 64, "avg_price": 32, "competition": "medium", "supplier": "zendrop"},
    "phone accessories":    {"base_margin": 38, "avg_price": 15, "competition": "very_high","supplier": "aliexpress"},
    "baby products":        {"base_margin": 70, "avg_price": 40, "competition": "medium", "supplier": "zendrop"},
    "beauty skincare":      {"base_margin": 75, "avg_price": 28, "competition": "high",   "supplier": "zendrop"},
    "outdoor camping":      {"base_margin": 58, "avg_price": 55, "competition": "low",    "supplier": "autods"},
}


def score_combo(margin_pct: float, cpm_cents: float, viral_coeff: float) -> float:
    """
    Decision Engine score formula.
    Score = Margin% × (100 / max(CPM_cents, 0.01)) × ViralCoeff
    Capped at 100.
    """
    cpm_score = 100 / max(cpm_cents * 100, 0.01)  # $0.00 CPM → very high score
    cpm_score = min(cpm_score, 50)  # cap free channels at 50 for CPM component
    raw = margin_pct * cpm_score * viral_coeff / 100
    return round(min(raw, 100), 1)


class TrendEngine:
    """
    Pulls Google Trends data for dropship niches and computes
    attention-arbitrage scores for each product × channel combo.
    """

    def __init__(self, hl: str = "en-US", tz: int = 360):
        self.pytrends = TrendReq(hl=hl, tz=tz, timeout=(10, 25), retries=2, backoff_factor=0.5)
        self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(exist_ok=True)

    # ──────────────────────────────────────────
    # PUBLIC
    # ──────────────────────────────────────────

    def run(self, niches: Optional[list] = None, timeframe: str = "today 3-m") -> dict:
        """
        Full research pass. Returns scored combo table + channel rankings.
        Also writes results to data/trend_results.json.
        """
        niches = niches or list(NICHE_PROFILES.keys())
        print(f"[TrendEngine] Running research for {len(niches)} niches...")

        trend_data = self._fetch_trends(niches, timeframe)
        combos = self._score_all_combos(niches, trend_data)
        channel_ranking = self._rank_channels()

        results = {
            "generated_at": datetime.utcnow().isoformat(),
            "timeframe": timeframe,
            "niches_analyzed": len(niches),
            "top_combos": combos[:10],
            "all_combos": combos,
            "channel_rankings": channel_ranking,
            "trend_data": trend_data,
            "decision": {
                "scale":  [c for c in combos if c["score"] >= 70][:3],
                "test":   [c for c in combos if 40 <= c["score"] < 70][:3],
                "kill":   [c for c in combos if c["score"] < 30],
            }
        }

        out_path = self.data_dir / "trend_results.json"
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        print(f"[TrendEngine] Results saved → {out_path}")
        print(f"[TrendEngine] Top combo: {combos[0]['niche']} × {combos[0]['channel']} (Score {combos[0]['score']})")
        return results

    # ──────────────────────────────────────────
    # INTERNAL
    # ──────────────────────────────────────────

    def _fetch_trends(self, niches: list, timeframe: str) -> dict:
        """
        Pulls Google Trends interest_over_time for each niche.
        Returns dict: {niche: {avg_interest, peak_interest, trend_direction, keywords}}
        """
        trend_data = {}
        # Google Trends allows max 5 keywords per request
        chunks = [niches[i:i+5] for i in range(0, len(niches), 5)]

        for chunk in chunks:
            try:
                self.pytrends.build_payload(chunk, timeframe=timeframe, geo="US")
                df = self.pytrends.interest_over_time()

                for niche in chunk:
                    if niche in df.columns:
                        series = df[niche]
                        avg = float(series.mean())
                        peak = float(series.max())
                        recent = float(series.tail(4).mean())  # last 4 weeks
                        older = float(series.head(4).mean())   # first 4 weeks

                        if older > 0:
                            direction = "rising" if recent > older * 1.1 else ("falling" if recent < older * 0.9 else "stable")
                        else:
                            direction = "stable"

                        trend_data[niche] = {
                            "avg_interest": round(avg, 1),
                            "peak_interest": round(peak, 1),
                            "recent_interest": round(recent, 1),
                            "trend_direction": direction,
                            "trend_multiplier": round(recent / max(avg, 1), 2),
                        }
                    else:
                        trend_data[niche] = self._fallback_trend(niche)

                time.sleep(random.uniform(1.5, 3.0))  # be polite to Google

            except Exception as e:
                logger.warning(f"Trends fetch failed for chunk {chunk}: {e}")
                for niche in chunk:
                    trend_data[niche] = self._fallback_trend(niche)

        return trend_data

    def _fallback_trend(self, niche: str) -> dict:
        """Sensible defaults when Google Trends is unavailable."""
        return {
            "avg_interest": 50,
            "peak_interest": 75,
            "recent_interest": 50,
            "trend_direction": "stable",
            "trend_multiplier": 1.0,
        }

    def _score_all_combos(self, niches: list, trend_data: dict) -> list:
        """Compute score for every niche × channel combo. Returns sorted list."""
        combos = []

        for niche in niches:
            profile = NICHE_PROFILES.get(niche, {"base_margin": 50, "avg_price": 30, "competition": "medium", "supplier": "aliexpress"})
            t = trend_data.get(niche, self._fallback_trend(niche))

            # Adjust margin by trend direction
            margin = profile["base_margin"]
            if t["trend_direction"] == "rising":
                margin = min(margin * 1.05, 90)
            elif t["trend_direction"] == "falling":
                margin = margin * 0.90

            for channel, ch_data in CHANNEL_CPM.items():
                # Pinterest bonus for search-intent niches
                search_niches = ["pet accessories", "home kitchen", "desk organizers", "led grow lights", "beauty skincare"]
                viral_coeff = ch_data["viral_coeff"]
                if channel == "pinterest_organic" and niche in search_niches:
                    viral_coeff *= 1.15

                score = score_combo(margin, ch_data["cpm"], viral_coeff)

                # Apply trend multiplier (capped)
                score = min(score * min(t["trend_multiplier"], 1.3), 100)
                score = round(score, 1)

                action = "SCALE" if score >= 70 else ("TEST" if score >= 40 else ("HOLD" if score >= 30 else "KILL"))

                combos.append({
                    "niche": niche,
                    "channel": channel,
                    "score": score,
                    "margin_pct": round(margin, 1),
                    "cpm": ch_data["cpm"],
                    "viral_coeff": viral_coeff,
                    "trend": t["trend_direction"],
                    "trend_multiplier": t["trend_multiplier"],
                    "avg_interest": t["avg_interest"],
                    "supplier": profile["supplier"],
                    "avg_price": profile["avg_price"],
                    "action": action,
                })

        combos.sort(key=lambda x: x["score"], reverse=True)
        return combos

    def _rank_channels(self) -> list:
        """Returns channels ranked by cost-efficiency (cheapest CPM first)."""
        ranked = []
        for name, data in CHANNEL_CPM.items():
            efficiency = score_combo(60, data["cpm"], data["viral_coeff"])  # using 60% baseline margin
            ranked.append({
                "channel": name,
                "cpm": data["cpm"],
                "viral_coeff": data["viral_coeff"],
                "audience_type": data["audience_type"],
                "efficiency_score": efficiency,
                "priority": data["priority"],
            })
        ranked.sort(key=lambda x: x["efficiency_score"], reverse=True)
        return ranked
