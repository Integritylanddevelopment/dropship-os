"""
learning_engine.py — Self-Improving Content Intelligence for ShipStack
=======================================================================
The brain that gets smarter over time.

Storage: Qdrant (192.168.1.123:6333) via agents.db.LearningDB
         SQLite fallback if Qdrant is unavailable
         winning_formulas.json still written for spinner injection

What it learns:
  - Which hook formulas win for which avatars
  - Which CTAs drive the most link clicks
  - Which platforms convert best for which niches
  - Which content patterns produce the highest CTR
  - Which traffic sources bring buyers
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests

try:
    from dotenv import load_dotenv
    _ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    load_dotenv(_ENV_PATH)
except ImportError:
    pass

from agents.db import LearningDB, init_db

init_db()
_db = LearningDB()

BASE_DIR     = Path(__file__).parent.parent
LEARNING_DIR = BASE_DIR / "data" / "learning"
LEARNING_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_URL   = f"http://{os.getenv('OLLAMA_HOST', '127.0.0.1')}:{os.getenv('OLLAMA_PORT', '11434')}/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


def _ollama(prompt: str, model: str = OLLAMA_MODEL, timeout: int = 60) -> str:
    try:
        r = requests.post(OLLAMA_URL, json={"model": model, "prompt": prompt, "stream": False}, timeout=timeout)
        if r.ok:
            return r.json().get("response", "").strip()
    except Exception as e:
        print(f"[Learning] Ollama error: {e}")
    return ""


# ── Pattern extraction ────────────────────────────────────────────────────────

def extract_hook_pattern(text: str) -> str:
    first_line = text.strip().split("\n")[0][:100]
    pattern = re.sub(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', '[PRODUCT]', first_line)
    pattern = re.sub(r'\b\d+\b', '[N]', pattern)
    return pattern.lower().strip()


def extract_cta_pattern(text: str) -> str:
    lines = text.strip().split("\n")
    cta_candidates = [l for l in reversed(lines) if any(
        w in l.lower() for w in ["link", "comment", "save", "share", "dm", "click", "shop", "grab"]
    )]
    if cta_candidates:
        cta = cta_candidates[0][:80]
        cta = re.sub(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', '[PRODUCT]', cta)
        return cta.lower().strip()
    return ""


def classify_emotion(text: str) -> str:
    text_lower = text.lower()
    emotions = {
        "fomo":         ["everyone", "viral", "selling out", "before it's gone", "limited"],
        "curiosity":    ["secret", "nobody talks", "why is", "wait", "bet you didn't"],
        "social_proof": ["k people", "reviews", "5 star", "obsessed", "best seller"],
        "aspiration":   ["transform", "glow up", "level up", "dream", "imagine"],
        "humor":        ["girl math", "no bc", "lowkey", "the way", "not me"],
        "authority":    ["honest review", "tested", "i tried", "dermatologist", "expert"],
        "value":        ["free", "cheap", "under $", "dupe", "budget"],
    }
    scores = {e: sum(1 for w in words if w in text_lower) for e, words in emotions.items()}
    if max(scores.values(), default=0) == 0:
        return "neutral"
    return max(scores, key=scores.get)


# ── LearningEngine ────────────────────────────────────────────────────────────

class LearningEngine:

    def __init__(self):
        self.master = _db.load_master()
        if not self.master:
            self.master = self._blank_master()
            _db.save_master(self.master)

    def _blank_master(self) -> dict:
        return {
            "version": 1,
            "last_updated": None,
            "total_tests_ingested": 0,
            "total_winners_ingested": 0,
            "hook_patterns": {},
            "cta_patterns": {},
            "emotions": {},
            "avatar_performance": {},
            "platform_performance": {},
            "niche_performance": {},
            "traffic_sources": {},
            "best_posting_times": {},
            "winning_formulas": [],
        }

    def _save(self):
        self.master["last_updated"] = datetime.now().isoformat()
        _db.save_master(self.master)

    def _log(self, message: str, event_type: str = "info"):
        _db.log_event(event_type=event_type, message=message)

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def ingest_ab_winner(self, test_data: dict, winner: dict):
        """Called when an A/B test concludes with a winner. Stores to Qdrant + SQLite."""
        platform  = test_data.get("platform", "unknown")
        niche     = test_data.get("niche", "default")
        avatar_id = winner.get("winner_avatar", "unknown")
        content   = winner.get("winner_content", "")
        ctr       = winner.get("winning_value", 0.0) or 0.0
        lift      = winner.get("lift_pct", 0.0)

        if not content:
            return

        hook_pattern = extract_hook_pattern(content)
        cta_pattern  = extract_cta_pattern(content)
        emotion      = classify_emotion(content)

        # Store winner vector in Qdrant for semantic retrieval
        winner_payload = {
            "type":         "ab_winner",
            "platform":     platform,
            "niche":        niche,
            "avatar_id":    avatar_id,
            "content":      content[:500],
            "ctr":          ctr,
            "lift_pct":     lift,
            "hook_pattern": hook_pattern,
            "cta_pattern":  cta_pattern,
            "emotion":      emotion,
            "timestamp":    datetime.now().isoformat(),
        }
        _db.store_winner(content=content, metadata=winner_payload)

        # Update in-memory master knowledge
        hp = self.master["hook_patterns"].setdefault(hook_pattern, {"wins": 0, "ctr_sum": 0.0, "count": 0})
        hp["wins"] += 1; hp["ctr_sum"] += ctr; hp["count"] += 1

        if cta_pattern:
            cp = self.master["cta_patterns"].setdefault(cta_pattern, {"wins": 0, "link_clicks_sum": 0.0, "count": 0})
            cp["wins"] += 1; cp["count"] += 1

        em = self.master["emotions"].setdefault(emotion, {"wins": 0, "ctr_sum": 0.0, "count": 0})
        em["wins"] += 1; em["ctr_sum"] += ctr; em["count"] += 1

        av = self.master["avatar_performance"].setdefault(avatar_id, {"wins": 0, "ctr_sum": 0.0, "conversion_sum": 0.0, "count": 0})
        av["wins"] += 1; av["ctr_sum"] += ctr; av["count"] += 1

        pp = self.master["platform_performance"].setdefault(platform, {"avg_ctr": 0.0, "ctr_sum": 0.0, "count": 0, "best_avatar": {}})
        pp["ctr_sum"] += ctr; pp["count"] += 1
        pp["avg_ctr"] = round(pp["ctr_sum"] / pp["count"], 3)
        pp["best_avatar"][avatar_id] = pp["best_avatar"].get(avatar_id, 0) + 1

        np = self.master["niche_performance"].setdefault(niche, {"avatar_wins": {}, "platform_wins": {}, "emotion_wins": {}})
        np["avatar_wins"][avatar_id]   = np["avatar_wins"].get(avatar_id, 0) + 1
        np["platform_wins"][platform]  = np["platform_wins"].get(platform, 0) + 1
        np["emotion_wins"][emotion]    = np["emotion_wins"].get(emotion, 0) + 1

        self.master["total_winners_ingested"] += 1

        # Update avatar learned patterns
        try:
            from agents.avatar_engine import AvatarEngine
            AvatarEngine().update_learned_patterns(avatar_id, content, "ctr", ctr)
        except:
            pass

        self._log(f"Winner ingested: {platform}/{niche}/{avatar_id} CTR={ctr:.2f}% lift={lift:.1f}%", "ingest")
        self._save()

        if self.master["total_winners_ingested"] % 10 == 0:
            self.rebuild_winning_formulas()

    def ingest_performance_metrics(
        self,
        platform: str,
        niche: str,
        content: str,
        impressions: int,
        clicks: int,
        conversions: int,
        revenue: float,
        traffic_source: dict = None,
    ):
        """Ingest raw performance data (no A/B test required)."""
        if traffic_source:
            for src, count in traffic_source.items():
                ts = self.master["traffic_sources"].setdefault(src, {"impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0.0})
                ts["impressions"] += impressions
                ts["clicks"]      += clicks
                ts["conversions"] += conversions
                ts["revenue"]     += revenue

        self.master["total_tests_ingested"] += 1
        self._save()

    # ── Insights ──────────────────────────────────────────────────────────────

    def get_top_hooks(self, n: int = 10) -> list:
        hooks = [
            {"pattern": k, "avg_ctr": round(v["ctr_sum"] / max(v["count"], 1), 3),
             "wins": v["wins"], "count": v["count"]}
            for k, v in self.master["hook_patterns"].items()
            if v["count"] >= 2
        ]
        return sorted(hooks, key=lambda x: x["avg_ctr"], reverse=True)[:n]

    def get_top_avatars(self, niche: str = None, platform: str = None) -> list:
        if niche and niche in self.master["niche_performance"]:
            wins = self.master["niche_performance"][niche]["avatar_wins"]
            total = sum(wins.values()) or 1
            return sorted(
                [{"avatar": k, "win_rate": round(v/total*100, 1), "wins": v} for k, v in wins.items()],
                key=lambda x: x["win_rate"], reverse=True
            )
        av = self.master["avatar_performance"]
        return sorted(
            [{"avatar": k, "wins": v["wins"], "avg_ctr": round(v["ctr_sum"]/max(v["count"],1), 3)}
             for k, v in av.items()],
            key=lambda x: x["avg_ctr"], reverse=True
        )

    def get_best_platform(self, niche: str) -> str:
        np_ = self.master["niche_performance"].get(niche, {})
        pw = np_.get("platform_wins", {})
        return max(pw, key=pw.get) if pw else "tiktok"

    def get_top_traffic_sources(self) -> list:
        ts = self.master["traffic_sources"]
        result = []
        for src, data in ts.items():
            result.append({
                "source":      src,
                "impressions": data["impressions"],
                "clicks":      data["clicks"],
                "ctr":         round(data["clicks"] / max(data["impressions"], 1) * 100, 3),
                "conversions": data["conversions"],
                "revenue":     data["revenue"],
                "conv_rate":   round(data["conversions"] / max(data["clicks"], 1) * 100, 2),
            })
        return sorted(result, key=lambda x: x["revenue"], reverse=True)

    def get_top_emotions(self) -> list:
        em = self.master["emotions"]
        return sorted(
            [{"emotion": k, "wins": v["wins"], "avg_ctr": round(v["ctr_sum"]/max(v["count"],1), 3)}
             for k, v in em.items()],
            key=lambda x: x["avg_ctr"], reverse=True
        )

    def find_similar_winners(self, content: str, n: int = 5) -> list:
        """Semantic search for past winners similar to this content (uses Qdrant)."""
        return _db.find_similar_winners(content, n=n)

    # ── Winning formula generation ────────────────────────────────────────────

    def rebuild_winning_formulas(self) -> list:
        print("[Learning] Rebuilding winning formulas from data…")

        top_hooks    = self.get_top_hooks(5)
        top_avatars  = self.get_top_avatars()[:3]
        top_emotions = self.get_top_emotions()[:3]

        if not top_hooks:
            return []

        hook_examples    = "\n".join(f"  - {h['pattern']} (avg CTR {h['avg_ctr']}%)" for h in top_hooks)
        avatar_examples  = "\n".join(f"  - {a['avatar']} ({a['wins']} wins)" for a in top_avatars)
        emotion_examples = "\n".join(f"  - {e['emotion']} (avg CTR {e['avg_ctr']}%)" for e in top_emotions)

        synthesis_prompt = f"""Based on real A/B test data from {self.master['total_winners_ingested']} winning posts,
generate 5 high-converting content formula templates for social media.

TOP-PERFORMING HOOK PATTERNS:
{hook_examples}

TOP-PERFORMING AVATARS:
{avatar_examples}

TOP-PERFORMING EMOTIONS:
{emotion_examples}

Create 5 content formula templates that combine the best elements above.
Each template should have:
1. A hook structure using the winning patterns
2. The emotion trigger that performs best
3. A CTA format optimized for conversions

Format each as:
FORMULA [N]:
Hook: [hook template with [PRODUCT] placeholder]
Emotion: [emotion type]
Body: [body structure hint]
CTA: [CTA template]
---"""

        result = _ollama(synthesis_prompt)

        formulas = []
        if result:
            for block in result.split("---"):
                if "Hook:" in block and "CTA:" in block:
                    formula = {
                        "generated":       datetime.now().isoformat(),
                        "based_on_tests":  self.master["total_winners_ingested"],
                        "raw":             block.strip(),
                    }
                    for line in block.split("\n"):
                        if line.strip().startswith("Hook:"):
                            formula["hook"] = line.split("Hook:", 1)[1].strip()
                        elif line.strip().startswith("CTA:"):
                            formula["cta"] = line.split("CTA:", 1)[1].strip()
                        elif line.strip().startswith("Emotion:"):
                            formula["emotion"] = line.split("Emotion:", 1)[1].strip()
                    formulas.append(formula)

        self.master["winning_formulas"] = formulas

        # Write to file so ContentSpinner can inject them
        formulas_path = LEARNING_DIR / "winning_formulas.json"
        formulas_path.write_text(json.dumps({"formulas": formulas, "generated": datetime.now().isoformat()}, indent=2))

        self._save()
        self._log(f"Rebuilt {len(formulas)} winning formulas from {self.master['total_winners_ingested']} tests", "rebuild")
        print(f"[Learning] Generated {len(formulas)} winning formulas")
        return formulas

    def get_recommendations_for_product(self, product_slug: str, niche: str, platform: str) -> dict:
        top_avatars   = self.get_top_avatars(niche=niche, platform=platform)[:3]
        top_hooks     = self.get_top_hooks(5)
        top_emotions  = self.get_top_emotions()[:3]
        best_platform = self.get_best_platform(niche)
        top_sources   = self.get_top_traffic_sources()[:3]
        formulas      = self.master.get("winning_formulas", [])[:3]

        rec = {
            "product":     product_slug,
            "niche":       niche,
            "platform":    platform,
            "generated":   datetime.now().isoformat(),
            "data_points": self.master["total_winners_ingested"],
        }

        if self.master["total_winners_ingested"] < 5:
            rec["status"]  = "learning"
            rec["message"] = f"Only {self.master['total_winners_ingested']} tests complete. Need 5+ for recommendations."
            return rec

        rec["status"]                  = "ready"
        rec["top_avatars_to_target"]   = [a["avatar"] for a in top_avatars]
        rec["best_platform_for_niche"] = best_platform
        rec["winning_hook_patterns"]   = [h["pattern"] for h in top_hooks[:3]]
        rec["winning_emotions"]        = [e["emotion"] for e in top_emotions]
        rec["top_traffic_sources"]     = [s["source"] for s in top_sources]
        rec["winning_formulas"]        = formulas

        if top_avatars:
            rec["priority_avatar"]         = top_avatars[0]["avatar"]
            rec["priority_avatar_winrate"] = top_avatars[0].get("win_rate") or top_avatars[0].get("avg_ctr")

        return rec

    def generate_weekly_report(self) -> dict:
        report = {
            "generated": datetime.now().isoformat(),
            "period":    "last 7 days",
            "summary": {
                "total_tests":      self.master["total_tests_ingested"],
                "winners_analyzed": self.master["total_winners_ingested"],
            },
            "top_performing_avatars": self.get_top_avatars()[:5],
            "top_hook_patterns":      self.get_top_hooks(5),
            "top_emotions":           self.get_top_emotions()[:5],
            "top_traffic_sources":    self.get_top_traffic_sources()[:5],
            "platform_performance":   self.master["platform_performance"],
            "winning_formulas":       self.master.get("winning_formulas", [])[:5],
            "recommendations":        [],
        }

        if self.master["total_winners_ingested"] >= 5:
            top_av = self.get_top_avatars()
            top_em = self.get_top_emotions()
            if top_av:
                report["recommendations"].append(
                    f"Lead with {top_av[0]['avatar']} avatar — winning {top_av[0].get('wins',0)} tests"
                )
            if top_em:
                report["recommendations"].append(
                    f"Use {top_em[0]['emotion']} emotion trigger — avg CTR {top_em[0]['avg_ctr']}%"
                )
            top_hooks = self.get_top_hooks(1)
            if top_hooks:
                report["recommendations"].append(
                    f"Best hook pattern: \"{top_hooks[0]['pattern']}\" ({top_hooks[0]['avg_ctr']}% avg CTR)"
                )
            top_src = self.get_top_traffic_sources()
            if top_src:
                report["recommendations"].append(
                    f"Best traffic source: {top_src[0]['source']} ({top_src[0]['conv_rate']}% conversion rate)"
                )

        report_path = LEARNING_DIR / f"weekly_report_{datetime.now().strftime('%Y%m%d')}.json"
        report_path.write_text(json.dumps(report, indent=2))
        print(f"[Learning] Weekly report saved to {report_path}")
        return report

    def get_status(self) -> dict:
        return {
            "total_tests_ingested":   self.master["total_tests_ingested"],
            "total_winners_ingested": self.master["total_winners_ingested"],
            "last_updated":           self.master["last_updated"],
            "avatars_tracked":        len(self.master["avatar_performance"]),
            "hook_patterns_learned":  len(self.master["hook_patterns"]),
            "winning_formulas":       len(self.master.get("winning_formulas", [])),
            "storage_backend":        _db.backend,
            "learning_status": (
                "active"         if self.master["total_winners_ingested"] >= 10 else
                "warming_up"     if self.master["total_winners_ingested"] >= 3  else
                "collecting_data"
            ),
        }


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    le = LearningEngine()

    if len(sys.argv) >= 2 and sys.argv[1] == "status":
        for k, v in le.get_status().items():
            print(f"  {k:35}: {v}")

    elif len(sys.argv) >= 2 and sys.argv[1] == "report":
        print(json.dumps(le.generate_weekly_report(), indent=2))

    elif len(sys.argv) >= 2 and sys.argv[1] == "rebuild":
        formulas = le.rebuild_winning_formulas()
        print(f"Generated {len(formulas)} winning formulas")
        for i, f in enumerate(formulas):
            print(f"\n  Formula {i+1}: {f.get('hook', '—')}")

    elif len(sys.argv) >= 2 and sys.argv[1] == "top-avatars":
        niche = sys.argv[2] if len(sys.argv) > 2 else None
        for a in le.get_top_avatars(niche=niche):
            print(f"  {a['avatar']:30} wins={a.get('wins',0)}  ctr={a.get('avg_ctr',0)}%")

    elif len(sys.argv) >= 2 and sys.argv[1] == "recommend":
        slug     = sys.argv[2] if len(sys.argv) > 2 else "product"
        niche    = sys.argv[3] if len(sys.argv) > 3 else "default"
        platform = sys.argv[4] if len(sys.argv) > 4 else "tiktok"
        print(json.dumps(le.get_recommendations_for_product(slug, niche, platform), indent=2))

    else:
        print("Usage:")
        print("  python learning_engine.py status")
        print("  python learning_engine.py report")
        print("  python learning_engine.py rebuild")
        print("  python learning_engine.py top-avatars [niche]")
        print("  python learning_engine.py recommend <slug> <niche> <platform>")
