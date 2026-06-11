"""
scheduler/task_scheduler.py — Automated task execution engine
Runs Reddit + Pinterest agents on schedule. Fully autonomous when auto_mode=True.
"""

import asyncio
from loguru import logger
from datetime import datetime, time

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not installed")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config
from agents.reddit_agent import RedditAgent
from agents.pinterest_agent import PinterestAgent
from storage import db, WeeklyPlan, Platform


class AgentScheduler:
    """
    Automated scheduler for both Reddit and Pinterest agents.
    Can run fully autonomously when configured.
    """

    def __init__(
        self,
        reddit_username: str = None,
        reddit_password: str = None,
        pinterest_email: str = None,
        pinterest_password: str = None,
        auto_mode: bool = False,
    ):
        self.reddit_agent = RedditAgent(
            username=reddit_username or config.reddit_api.username,
            password=reddit_password or config.reddit_api.password,
            auto_mode=auto_mode,
        )
        self.pinterest_agent = PinterestAgent(
            email=pinterest_email,
            password=pinterest_password,
            auto_mode=auto_mode,
        )
        self.auto_mode = auto_mode
        self._scheduler = None
        self._results_log = []

    def start(self):
        """Start the scheduler"""
        if not SCHEDULER_AVAILABLE:
            logger.error("APScheduler not installed. Run: pip install apscheduler")
            return

        self._scheduler = AsyncIOScheduler()

        # ─── REDDIT SCHEDULE ───────────────────────────────────
        # Morning comment session — 8:30am
        self._scheduler.add_job(
            self._run_reddit_morning,
            CronTrigger(hour=8, minute=30),
            id="reddit_morning",
            name="Reddit Morning Session",
            misfire_grace_time=1800,
        )

        # Evening comment session — 7:00pm
        self._scheduler.add_job(
            self._run_reddit_evening,
            CronTrigger(hour=19, minute=0),
            id="reddit_evening",
            name="Reddit Evening Session",
            misfire_grace_time=1800,
        )

        # Research pass — Monday, Wednesday, Friday at 6am
        self._scheduler.add_job(
            self._run_reddit_research,
            CronTrigger(day_of_week="mon,wed,fri", hour=6, minute=0),
            id="reddit_research",
            name="Reddit Research Pass",
        )

        # Weekly plan generation — Sunday 9pm
        self._scheduler.add_job(
            self._generate_weekly_plans,
            CronTrigger(day_of_week="sun", hour=21, minute=0),
            id="weekly_plans",
            name="Weekly Plan Generation",
        )

        # ─── PINTEREST SCHEDULE ────────────────────────────────
        # Morning pins — 8:00am (Pinterest peaks 8-11am EST)
        self._scheduler.add_job(
            self._run_pinterest_morning,
            CronTrigger(hour=8, minute=0),
            id="pinterest_morning",
            name="Pinterest Morning Pins",
        )

        # Midday pins — 12:00pm
        self._scheduler.add_job(
            self._run_pinterest_midday,
            CronTrigger(hour=12, minute=0),
            id="pinterest_midday",
            name="Pinterest Midday Pins",
        )

        # Evening pins — 8:00pm (Pinterest peaks 8-11pm EST)
        self._scheduler.add_job(
            self._run_pinterest_evening,
            CronTrigger(hour=20, minute=0),
            id="pinterest_evening",
            name="Pinterest Evening Pins",
        )

        # Performance check — Friday 9am
        self._scheduler.add_job(
            self._run_pinterest_analysis,
            CronTrigger(day_of_week="fri", hour=9, minute=0),
            id="pinterest_analysis",
            name="Pinterest Performance Analysis",
        )

        self._scheduler.start()
        logger.info("✅ Agent scheduler started")
        logger.info("Jobs scheduled:")
        for job in self._scheduler.get_jobs():
            logger.info(f"  • {job.name} ({job.trigger})")

    def stop(self):
        if self._scheduler:
            self._scheduler.shutdown()
            logger.info("Scheduler stopped")

    def get_jobs(self) -> list:
        if self._scheduler:
            return [{"id": j.id, "name": j.name, "next_run": str(j.next_run_time)} for j in self._scheduler.get_jobs()]
        return []

    # ─────────────────────────────────────────────
    # REDDIT SCHEDULED TASKS
    # ─────────────────────────────────────────────

    async def _run_reddit_morning(self):
        logger.info("⏰ Scheduled: Reddit Morning Session")
        try:
            result = await self.reddit_agent.run_warmup_session()
            self._log_result("reddit_morning", result)
        except Exception as e:
            logger.error(f"Reddit morning session failed: {e}")

    async def _run_reddit_evening(self):
        logger.info("⏰ Scheduled: Reddit Evening Session")
        try:
            result = await self.reddit_agent.run_active_session()
            self._log_result("reddit_evening", result)
        except Exception as e:
            logger.error(f"Reddit evening session failed: {e}")

    async def _run_reddit_research(self):
        logger.info("⏰ Scheduled: Reddit Research Pass")
        try:
            from research.market_research import MarketResearchEngine
            researcher = MarketResearchEngine()
            subreddits = ["dropshipping", "ecommerce", "entrepreneur"]
            result = await researcher.run_full_research_pass(subreddits)
            self._log_result("reddit_research", result)
        except Exception as e:
            logger.error(f"Reddit research failed: {e}")

    # ─────────────────────────────────────────────
    # PINTEREST SCHEDULED TASKS
    # ─────────────────────────────────────────────

    async def _run_pinterest_morning(self):
        logger.info("⏰ Scheduled: Pinterest Morning Pins")
        try:
            result = await self.pinterest_agent.run_daily_session(pins_today=5)
            self._log_result("pinterest_morning", result)
        except Exception as e:
            logger.error(f"Pinterest morning session failed: {e}")

    async def _run_pinterest_midday(self):
        logger.info("⏰ Scheduled: Pinterest Midday Pins")
        try:
            result = await self.pinterest_agent.run_daily_session(pins_today=4)
            self._log_result("pinterest_midday", result)
        except Exception as e:
            logger.error(f"Pinterest midday session failed: {e}")

    async def _run_pinterest_evening(self):
        logger.info("⏰ Scheduled: Pinterest Evening Pins")
        try:
            result = await self.pinterest_agent.run_daily_session(pins_today=6)
            self._log_result("pinterest_evening", result)
        except Exception as e:
            logger.error(f"Pinterest evening session failed: {e}")

    async def _run_pinterest_analysis(self):
        logger.info("⏰ Scheduled: Pinterest Performance Analysis")
        try:
            result = await self.pinterest_agent.analyze_pin_performance()
            self._log_result("pinterest_analysis", result)
        except Exception as e:
            logger.error(f"Pinterest analysis failed: {e}")

    # ─────────────────────────────────────────────
    # SHARED
    # ─────────────────────────────────────────────

    async def _generate_weekly_plans(self):
        logger.info("⏰ Scheduled: Weekly Plan Generation")
        try:
            reddit_plan = await self.reddit_agent.generate_weekly_plan()
            pinterest_plan = await self.pinterest_agent.generate_weekly_plan()
            self._log_result("weekly_plans", {"reddit": reddit_plan, "pinterest": pinterest_plan})
        except Exception as e:
            logger.error(f"Weekly plan generation failed: {e}")

    def _log_result(self, task_name: str, result: dict):
        self._results_log.append({
            "task": task_name,
            "timestamp": datetime.utcnow().isoformat(),
            "result_summary": str(result)[:500],
        })
        # Keep only last 100 results
        if len(self._results_log) > 100:
            self._results_log = self._results_log[-100:]

    def get_recent_results(self, limit: int = 10) -> list:
        return self._results_log[-limit:]
