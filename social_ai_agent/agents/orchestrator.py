"""
agents/orchestrator.py — Enterprise Master Orchestrator
The top-level brain. Makes autonomous decisions:
- Which platform gets more content volume today?
- Which subreddit is highest-leverage right now?
- Which keywords are trending and should be pinned today?
- What's the ROI on each channel?
- Where is attention cheapest TODAY?

This is the enterprise tier — it doesn't wait for instructions.
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config
from agents.reddit_agent import RedditAgent
from agents.pinterest_agent import PinterestAgent
from research.trend_intelligence import trend_intel
from research.market_research import MarketResearchEngine
from storage import db, PerformanceMetric, Platform, WeeklyPlan


class DecisionEngine:
    """
    Autonomous decision-making layer.
    Reads performance data + trend signals and decides where to push volume.
    """

    def should_increase_reddit_volume(self) -> bool:
        """Check if Reddit is outperforming and deserves more volume"""
        with db.session() as session:
            # Look at recent Reddit performance
            recent = session.query(PerformanceMetric).filter(
                PerformanceMetric.platform == Platform.REDDIT,
                PerformanceMetric.metric_date >= datetime.utcnow() - timedelta(days=7)
            ).all()

            if not recent:
                return True  # Default: yes, build Reddit

            avg_score = sum(m.value for m in recent) / len(recent)
            return avg_score > 5.0  # If engagement above threshold

    def should_increase_pinterest_volume(self) -> bool:
        """Check if Pinterest is generating saves/clicks worth scaling"""
        with db.session() as session:
            recent = session.query(PerformanceMetric).filter(
                PerformanceMetric.platform == Platform.PINTEREST,
                PerformanceMetric.metric_date >= datetime.utcnow() - timedelta(days=7)
            ).all()
            if not recent:
                return True
            avg = sum(m.value for m in recent) / len(recent)
            return avg > 3.0

    def get_today_content_priorities(self, trend_signals: dict) -> list:
        """
        Determine today's content priorities based on trends + performance.
        Returns ordered list of (platform, action, priority_score).
        """
        priorities = []

        hot = trend_signals.get("hot_right_now", [])
        rising = trend_signals.get("rising_fast", [])

        # If something is trending hot → post Reddit question or experience about it
        for topic in hot[:2]:
            priorities.append({
                "platform": "reddit",
                "action": "post",
                "format": "question",
                "topic": topic,
                "priority": 10,
                "reason": f"'{topic}' is trending hot on Google",
            })
            priorities.append({
                "platform": "pinterest",
                "action": "pin",
                "keyword": topic,
                "format": "standard",
                "priority": 9,
                "reason": f"Capture trending search intent: '{topic}'",
            })

        # Rising topics → comment strategy on Reddit, SEO pins on Pinterest
        for topic in rising[:2]:
            priorities.append({
                "platform": "reddit",
                "action": "comment",
                "topic": topic,
                "priority": 8,
                "reason": f"'{topic}' is rising — add expert commentary",
            })
            priorities.append({
                "platform": "pinterest",
                "action": "pin",
                "keyword": topic,
                "format": "checklist",
                "priority": 7,
                "reason": f"Capture rising search volume for '{topic}'",
            })

        # Sort by priority
        priorities.sort(key=lambda x: x["priority"], reverse=True)
        return priorities

    def get_attention_cost_report(self) -> dict:
        """
        Real-time attention cost analysis.
        Which channel is cheapest per qualified impression TODAY?
        """
        with db.session() as session:
            reddit_metrics = session.query(PerformanceMetric).filter(
                PerformanceMetric.platform == Platform.REDDIT,
                PerformanceMetric.metric_date >= datetime.utcnow() - timedelta(days=30)
            ).all()

            pinterest_metrics = session.query(PerformanceMetric).filter(
                PerformanceMetric.platform == Platform.PINTEREST,
                PerformanceMetric.metric_date >= datetime.utcnow() - timedelta(days=30)
            ).all()

        def calc_avg(metrics):
            if not metrics:
                return 0
            return sum(m.value for m in metrics) / len(metrics)

        reddit_avg = calc_avg(reddit_metrics)
        pinterest_avg = calc_avg(pinterest_metrics)

        winner = "reddit" if reddit_avg >= pinterest_avg else "pinterest"

        return {
            "reddit_avg_engagement": round(reddit_avg, 2),
            "pinterest_avg_engagement": round(pinterest_avg, 2),
            "cheapest_attention_channel": winner,
            "recommendation": f"Push more volume to {winner} — highest engagement per action",
            "generated_at": datetime.utcnow().isoformat(),
        }


class MasterOrchestrator:
    """
    Enterprise top-level orchestrator.
    Runs the full system autonomously — no human input needed after setup.

    Daily loop:
    1. Pull trend signals
    2. Recall relevant research intel
    3. Make content priority decisions
    4. Execute Reddit session
    5. Execute Pinterest session
    6. Log performance
    7. Adjust strategy for tomorrow
    """

    def __init__(self, auto_mode: bool = False):
        self.auto_mode = auto_mode
        self.reddit_agent = RedditAgent(auto_mode=auto_mode)
        self.pinterest_agent = PinterestAgent(auto_mode=auto_mode)
        self.researcher = MarketResearchEngine()
        self.decision_engine = DecisionEngine()
        self._daily_log = []

    async def run_full_day(self) -> dict:
        """
        Execute the full daily autonomous cycle.
        This is what runs on the scheduler every day.
        """
        start_time = datetime.utcnow()
        logger.info("🤖 Master Orchestrator: Starting full daily cycle")

        day_report = {
            "date": start_time.strftime("%Y-%m-%d"),
            "start_time": start_time.isoformat(),
            "trend_signals": {},
            "content_priorities": [],
            "reddit_results": {},
            "pinterest_results": {},
            "research_insights": {},
            "attention_cost_report": {},
            "decisions_made": [],
            "total_content_pieces": 0,
        }

        # ── Step 1: Pull trend signals ──────────────────────
        logger.info("Step 1: Pulling trend signals...")
        try:
            trends = await trend_intel.get_daily_trend_signals()
            day_report["trend_signals"] = trends
            logger.info(f"Trending now: {trends.get('hot_right_now', [])[:3]}")
        except Exception as e:
            logger.error(f"Trend pull failed: {e}")
            trends = {}

        # ── Step 2: Get content priorities ─────────────────
        logger.info("Step 2: Making content priority decisions...")
        priorities = self.decision_engine.get_today_content_priorities(trends)
        day_report["content_priorities"] = priorities
        day_report["decisions_made"].append(
            f"Today's top priority: {priorities[0]['reason'] if priorities else 'balanced execution'}"
        )

        # ── Step 3: Get content briefs from vector memory ──
        logger.info("Step 3: Recalling relevant research intel...")
        top_topic = (trends.get("hot_right_now") or [config.niche])[0]
        reddit_brief = await trend_intel.get_content_brief(top_topic, "reddit")
        pinterest_brief = await trend_intel.get_content_brief(top_topic, "pinterest")

        # ── Step 4: Reddit execution ────────────────────────
        logger.info("Step 4: Running Reddit session...")
        try:
            reddit_result = await self.reddit_agent.run_warmup_session()
            day_report["reddit_results"] = reddit_result
            day_report["total_content_pieces"] += reddit_result.get("comments_made", 0)
            day_report["decisions_made"].append(
                f"Reddit: {reddit_result.get('comments_made', 0)} comments executed"
            )
        except Exception as e:
            logger.error(f"Reddit session failed: {e}")
            day_report["reddit_results"] = {"error": str(e)}

        # Brief pause between platforms
        await asyncio.sleep(5)

        # ── Step 5: Pinterest execution ─────────────────────
        logger.info("Step 5: Running Pinterest session...")
        try:
            pinterest_result = await self.pinterest_agent.run_daily_session()
            day_report["pinterest_results"] = pinterest_result
            day_report["total_content_pieces"] += pinterest_result.get("pins_published", 0)
            day_report["decisions_made"].append(
                f"Pinterest: {pinterest_result.get('pins_published', 0)} pins published"
            )
        except Exception as e:
            logger.error(f"Pinterest session failed: {e}")
            day_report["pinterest_results"] = {"error": str(e)}

        # ── Step 6: Market research pulse ──────────────────
        logger.info("Step 6: Quick research pulse...")
        try:
            # Quick 1-subreddit research pass
            from storage import Subreddit, SubredditTier
            with db.session() as session:
                top_sub = session.query(Subreddit).order_by(
                    Subreddit.score_overall.desc()
                ).first()
                sub_name = top_sub.name if top_sub else "dropshipping"

            research = await self.researcher.research_subreddit(sub_name, depth=1, posts_limit=25)
            intel = research.get("intelligence", {})

            # Store new intel in vector memory
            pain_points = [p.get("pain", str(p)) if isinstance(p, dict) else str(p)
                           for p in intel.get("pain_points", [])]
            trend_intel.store_research_batch([
                {"text": p, "intel_type": "pain_point", "source": sub_name}
                for p in pain_points
            ])

            day_report["research_insights"] = {
                "subreddit": sub_name,
                "new_pain_points": pain_points[:3],
                "stored_to_memory": len(pain_points),
            }
        except Exception as e:
            logger.error(f"Research pulse failed: {e}")

        # ── Step 7: Attention cost analysis ────────────────
        day_report["attention_cost_report"] = self.decision_engine.get_attention_cost_report()

        # ── Step 8: Log to DB ───────────────────────────────
        self._log_day_metrics(day_report)

        end_time = datetime.utcnow()
        day_report["end_time"] = end_time.isoformat()
        day_report["duration_minutes"] = round((end_time - start_time).total_seconds() / 60, 1)

        logger.info(f"✅ Daily cycle complete: {day_report['total_content_pieces']} content pieces in {day_report['duration_minutes']}m")

        return day_report

    async def run_weekly_strategy_review(self) -> dict:
        """
        Weekly review: what worked, what didn't, adjust for next week.
        Runs every Sunday night.
        """
        logger.info("📊 Running weekly strategy review")

        reddit_plan = await self.reddit_agent.generate_weekly_plan()
        pinterest_plan = await self.pinterest_agent.generate_weekly_plan()
        attention_report = self.decision_engine.get_attention_cost_report()
        memory_stats = trend_intel.get_collection_stats()

        review = {
            "week_ending": datetime.utcnow().strftime("%Y-%m-%d"),
            "attention_cost_report": attention_report,
            "vector_memory_stats": memory_stats,
            "next_week_reddit": reddit_plan,
            "next_week_pinterest": pinterest_plan,
            "strategic_recommendation": (
                f"Double down on {attention_report.get('cheapest_attention_channel', 'reddit')} "
                f"— highest engagement per action this week"
            ),
        }

        # Save weekly report
        report_path = Path(__file__).parent.parent / "data" / f"weekly_review_{datetime.utcnow().strftime('%Y%m%d')}.json"
        with open(report_path, "w") as f:
            json.dump(review, f, indent=2, default=str)

        logger.info(f"Weekly review saved to {report_path}")
        return review

    async def cold_start(self, niche: str = None) -> dict:
        """
        Full cold start — run this once to bootstrap the entire system.
        Sets up both platforms, runs initial research, populates vector memory.
        """
        logger.info("🚀 Enterprise Cold Start")

        # Setup both agents
        reddit_setup = await self.reddit_agent.setup(niche_override=niche)
        pinterest_setup = await self.pinterest_agent.setup(niche_override=niche)

        # Populate initial vector memory from research
        if reddit_setup.get("market_research", {}).get("summary"):
            pain_points = reddit_setup["market_research"]["summary"].get("top_pain_points", [])
            language = reddit_setup["market_research"]["summary"].get("top_customer_language", [])

            trend_intel.store_research_batch([
                {"text": str(p), "intel_type": "pain_point"} for p in pain_points
            ])
            trend_intel.store_research_batch([
                {"text": str(l), "intel_type": "language"} for l in language
            ])
            logger.info(f"Stored {len(pain_points) + len(language)} items in vector memory")

        return {
            "status": "cold_start_complete",
            "reddit_ready": bool(reddit_setup.get("subreddits")),
            "pinterest_ready": bool(pinterest_setup.get("board_strategy")),
            "memory_stats": trend_intel.get_collection_stats(),
            "next_step": "Run python main.py schedule --auto to go fully autonomous",
        }

    def _log_day_metrics(self, report: dict):
        """Log daily metrics to DB"""
        try:
            with db.session() as session:
                for platform_key, platform_enum in [("reddit_results", Platform.REDDIT), ("pinterest_results", Platform.PINTEREST)]:
                    results = report.get(platform_key, {})
                    value = results.get("comments_made", 0) + results.get("pins_published", 0) + results.get("posts_made", 0)
                    session.add(PerformanceMetric(
                        platform=platform_enum,
                        metric_date=datetime.utcnow(),
                        metric_type="daily_actions",
                        value=float(value),
                        context={"report_date": report.get("date")},
                    ))
        except Exception as e:
            logger.error(f"Day metrics log failed: {e}")

    def get_system_status(self) -> dict:
        """Get full system status for dashboard"""
        memory_stats = trend_intel.get_collection_stats()
        attention_report = self.decision_engine.get_attention_cost_report()

        with db.session() as session:
            from storage.models import RedditAction, PinterestPin, Subreddit, ResearchIntel
            reddit_total = session.query(RedditAction).count()
            pinterest_total = session.query(PinterestPin).count()
            subreddits = session.query(Subreddit).count()
            intel_count = session.query(ResearchIntel).count()

        return {
            "system": "operational",
            "auto_mode": self.auto_mode,
            "reddit_actions_total": reddit_total,
            "pinterest_pins_total": pinterest_total,
            "subreddits_tracked": subreddits,
            "research_intel_entries": intel_count,
            "vector_memory": memory_stats,
            "attention_cost": attention_report,
            "last_checked": datetime.utcnow().isoformat(),
        }
