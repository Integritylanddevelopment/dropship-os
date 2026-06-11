"""
agents/reddit_agent.py — Reddit Organic Growth Agent
The full Reddit strategy orchestrator. Executes the complete framework:
discovery → research → content → warmup → comment → post → scale
"""

import asyncio
import random
from typing import Optional
from loguru import logger
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config
from content.generator import generator
from automation.reddit_browser import RedditBrowserAutomation
from research.subreddit_analyzer import SubredditAnalyzer
from research.market_research import MarketResearchEngine
from storage import (
    db, RedditAccount, Subreddit, RedditAction,
    AccountPhase, SubredditTier, ActionStatus, ContentType, Platform,
    ContentIdea, WeeklyPlan
)


class RedditAgent:
    """
    Full Reddit organic growth agent.

    Phases:
    1. SETUP — Subreddit discovery, account registration, warmup start
    2. WARMUP — Comment only, no promotion, karma building (30 days)
    3. ACTIVE — Posts + comments, credibility building
    4. SCALE — Strategic promotion, profile traffic, lead capture
    """

    def __init__(
        self,
        username: str = None,
        password: str = None,
        auto_mode: bool = False
    ):
        self.username = username or config.reddit_api.username
        self.password = password or config.reddit_api.password
        self.auto_mode = auto_mode
        self.strategy = config.reddit_strategy
        self.automation = RedditBrowserAutomation()
        self.analyzer = SubredditAnalyzer()
        self.researcher = MarketResearchEngine()
        self._account = None

    # ─────────────────────────────────────────────
    # PHASE 0: SETUP
    # ─────────────────────────────────────────────

    async def setup(self, niche_override: str = None) -> dict:
        """
        Complete setup run:
        - Discover and score subreddits
        - Run initial market research
        - Generate content strategy
        - Create 30-day execution plan
        """
        niche = niche_override or config.niche
        logger.info(f"🚀 Starting Reddit Agent setup for niche: {niche}")

        report = {
            "phase": "setup",
            "niche": niche,
            "subreddits": [],
            "market_research": {},
            "content_strategy": {},
            "execution_plan": {},
        }

        # Step 1: Discover and score subreddits
        logger.info("Step 1/4: Discovering subreddits...")
        subreddits = await self.analyzer.run_full_discovery(max_subreddits=20)
        report["subreddits"] = subreddits[:10]

        # Step 2: Market research on top subreddits
        logger.info("Step 2/4: Running market research...")
        top_subs = [s.get("subreddit", s.get("name", "")) for s in subreddits[:3] if s]
        top_subs = [s for s in top_subs if s]

        if top_subs:
            research = await self.researcher.run_full_research_pass(
                subreddits=top_subs,
                keywords=config.target_products,
                competitors=[]
            )
            report["market_research"] = research

        # Step 3: Generate content ideas
        logger.info("Step 3/4: Generating content strategy...")
        content_ideas = await self._generate_initial_content_ideas(subreddits[:5])
        report["content_strategy"] = content_ideas

        # Step 4: Build execution plan
        logger.info("Step 4/4: Building 30-day execution plan...")
        plan = await self._build_30_day_plan(subreddits[:10])
        report["execution_plan"] = plan

        logger.info("✅ Reddit Agent setup complete")
        return report

    # ─────────────────────────────────────────────
    # PHASE 1: WARMUP (Days 1-30)
    # ─────────────────────────────────────────────

    async def run_warmup_session(self) -> dict:
        """
        Daily warmup session.
        Comment-only. No promotion. Build karma and credibility.
        Target: 3 genuine, upvote-worthy comments per day.
        """
        logger.info("🔥 Running warmup session")

        if not await self._ensure_logged_in():
            return {"error": "Login failed"}

        account = self._get_account()
        if not account:
            return {"error": "No account found"}

        phase_info = self._get_phase_info(account)
        if phase_info["phase"] != AccountPhase.WARMUP:
            logger.info(f"Account is in {phase_info['phase']} phase — use run_active_session()")

        # Get target subreddits (warmup: credibility-building and research tiers)
        target_subs = self._get_warmup_subreddits()

        session_results = {
            "date": datetime.utcnow().isoformat(),
            "phase": "warmup",
            "comments_made": 0,
            "threads_engaged": [],
            "errors": [],
        }

        comment_limit = self.strategy.warmup_daily_comments

        for subreddit in target_subs:
            if session_results["comments_made"] >= comment_limit:
                break

            try:
                # Find leverage threads
                keywords = config.target_products + [config.niche]
                threads = await self.automation.find_high_leverage_threads(
                    subreddit,
                    keywords,
                    min_comments=3,
                    max_hours_old=18
                )

                for thread in threads[:2]:
                    if session_results["comments_made"] >= comment_limit:
                        break

                    # Generate value-adding comment
                    comment = await generator.generate_reddit_comment(
                        thread_title=thread.get("title", ""),
                        thread_body=thread.get("selftext", ""),
                        comment_to_reply_to="",
                        subreddit=subreddit,
                        value_angle=f"expertise in {config.niche}",
                        niche=config.niche,
                        include_soft_mention=False  # No promotion during warmup
                    )

                    if self.auto_mode:
                        # Actually post the comment
                        post_url = f"https://www.reddit.com{thread.get('permalink', '')}"
                        result = await self.automation.submit_comment(post_url, comment)

                        if result:
                            session_results["comments_made"] += 1
                            session_results["threads_engaged"].append({
                                "subreddit": subreddit,
                                "thread": thread.get("title", "")[:60],
                                "comment_preview": comment[:100],
                            })
                            # Log to DB
                            self._log_action(
                                action_type=ContentType.COMMENT,
                                content_body=comment,
                                subreddit_name=subreddit,
                                status=ActionStatus.COMPLETED,
                                is_promotional=False
                            )
                    else:
                        # Dry run — just generate and log
                        session_results["comments_made"] += 1
                        session_results["threads_engaged"].append({
                            "subreddit": subreddit,
                            "thread": thread.get("title", "")[:60],
                            "comment_preview": comment[:150],
                            "dry_run": True,
                        })

                    # Human-like delay between comments
                    await asyncio.sleep(random.uniform(300, 900))  # 5-15 minutes between comments

            except Exception as e:
                logger.error(f"Warmup error in r/{subreddit}: {e}")
                session_results["errors"].append(str(e))

        logger.info(f"Warmup session complete: {session_results['comments_made']} comments")
        return session_results

    # ─────────────────────────────────────────────
    # PHASE 2: ACTIVE
    # ─────────────────────────────────────────────

    async def run_active_session(self) -> dict:
        """
        Daily active session.
        Posts + comments. Strategic credibility. Occasional soft mentions.
        """
        logger.info("⚡ Running active session")

        if not await self._ensure_logged_in():
            return {"error": "Login failed"}

        session_results = {
            "date": datetime.utcnow().isoformat(),
            "phase": "active",
            "posts_made": 0,
            "comments_made": 0,
            "content_generated": [],
            "errors": [],
        }

        # Get target subreddits
        target_subs = self._get_active_subreddits()

        # Day's post quota
        post_limit = self.strategy.active_daily_posts
        comment_limit = self.strategy.active_daily_comments

        # Generate and post content
        for i, subreddit in enumerate(target_subs):
            if session_results["posts_made"] >= post_limit and session_results["comments_made"] >= comment_limit:
                break

            try:
                # Post (if quota not met)
                if session_results["posts_made"] < post_limit and i % 3 == 0:
                    post_format = random.choice([
                        "question", "experience", "lessons", "case_study",
                        "myth_bust", "comparison", "what_would_you_do"
                    ])

                    post_data = await generator.generate_reddit_post(
                        post_format=post_format,
                        subreddit=subreddit,
                        topic=f"{config.niche} strategy and insights",
                        niche=config.niche,
                        is_promotional=False
                    )

                    if self.auto_mode:
                        result_url = await self.automation.submit_post(
                            subreddit=subreddit,
                            title=post_data.get("title", ""),
                            body=post_data.get("body", ""),
                        )
                        if result_url:
                            session_results["posts_made"] += 1
                            session_results["content_generated"].append({
                                "type": "post",
                                "subreddit": subreddit,
                                "title": post_data.get("title", "")[:80],
                                "url": result_url,
                            })
                    else:
                        session_results["posts_made"] += 1
                        session_results["content_generated"].append({
                            "type": "post",
                            "subreddit": subreddit,
                            "title": post_data.get("title", "")[:80],
                            "body_preview": post_data.get("body", "")[:150],
                            "dry_run": True,
                        })

                # Comments
                if session_results["comments_made"] < comment_limit:
                    threads = await self.automation.find_high_leverage_threads(
                        subreddit,
                        config.target_products + [config.niche],
                        min_comments=5,
                        max_hours_old=12
                    )

                    for thread in threads[:1]:
                        comment = await generator.generate_reddit_comment(
                            thread_title=thread.get("title", ""),
                            thread_body=thread.get("selftext", ""),
                            comment_to_reply_to="",
                            subreddit=subreddit,
                            value_angle=f"expert in {config.niche}",
                            niche=config.niche,
                            include_soft_mention=False
                        )

                        if self.auto_mode:
                            post_url = f"https://www.reddit.com{thread.get('permalink', '')}"
                            await self.automation.submit_comment(post_url, comment)

                        session_results["comments_made"] += 1
                        await asyncio.sleep(random.uniform(600, 1800))  # 10-30 mins between comments

            except Exception as e:
                logger.error(f"Active session error in r/{subreddit}: {e}")
                session_results["errors"].append(str(e))

        logger.info(f"Active session: {session_results['posts_made']} posts, {session_results['comments_made']} comments")
        return session_results

    # ─────────────────────────────────────────────
    # CONTENT GENERATION (standalone)
    # ─────────────────────────────────────────────

    async def generate_content_batch(
        self,
        subreddit: str,
        formats: list = None,
        count: int = 5
    ) -> list:
        """Generate a batch of content ideas for a subreddit"""
        formats = formats or ["question", "experience", "lessons", "myth_bust", "comparison"]
        results = []

        for i in range(count):
            fmt = formats[i % len(formats)]
            post = await generator.generate_reddit_post(
                post_format=fmt,
                subreddit=subreddit,
                topic=f"{config.niche} tips and insights",
                niche=config.niche,
            )
            results.append(post)
            await asyncio.sleep(1)

        return results

    async def generate_weekly_comment_angles(self, subreddit: str) -> list:
        """Generate a week's worth of comment angles for a subreddit"""
        posts = await self.automation.scrape_subreddit_posts(subreddit, limit=20)
        angles = []

        for post in posts[:7]:
            angle = {
                "thread": post.get("title", ""),
                "permalink": f"https://www.reddit.com{post.get('permalink', '')}",
                "suggested_angle": f"Add expertise on {config.niche} related to: {post.get('title', '')[:60]}",
                "num_comments": post.get("num_comments", 0),
                "score": post.get("score", 0),
            }
            angles.append(angle)

        return angles

    # ─────────────────────────────────────────────
    # WEEKLY PLAN
    # ─────────────────────────────────────────────

    async def generate_weekly_plan(self) -> dict:
        """Generate a full 7-day Reddit execution plan"""
        logger.info("Generating weekly Reddit plan")

        account = self._get_account()
        phase = self._get_phase_info(account)["phase"] if account else AccountPhase.WARMUP

        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        plan = {}

        for i, day in enumerate(days):
            day_actions = []

            # Comments every day
            day_actions.append({
                "type": "comment",
                "count": self.strategy.warmup_daily_comments if phase == AccountPhase.WARMUP else self.strategy.active_daily_comments,
                "focus": "value-adding comment in top subreddits",
                "timing": "early morning or evening when engagement is highest",
            })

            # Research on Mon/Wed/Fri
            if i in [0, 2, 4]:
                day_actions.append({
                    "type": "research",
                    "action": "Scan top posts for pain points and new angles",
                    "time": "15 minutes",
                })

            # Post on Tue/Thu (active phase only)
            if phase != AccountPhase.WARMUP and i in [1, 3]:
                day_actions.append({
                    "type": "post",
                    "format": "experience" if i == 1 else "question",
                    "subreddit": "best_scored_subreddit",
                    "timing": "9-11am or 6-8pm",
                })

            # Weekly review on Sunday
            if i == 6:
                day_actions.append({
                    "type": "review",
                    "action": "Check karma, upvotes, profile visits. Adjust strategy.",
                })

            plan[day] = day_actions

        weekly_plan = {
            "phase": phase.value if hasattr(phase, "value") else str(phase),
            "week_start": datetime.utcnow().strftime("%Y-%m-%d"),
            "plan": plan,
            "kpis": {
                "target_comments": 7 * (self.strategy.warmup_daily_comments if phase == AccountPhase.WARMUP else self.strategy.active_daily_comments),
                "target_posts": 0 if phase == AccountPhase.WARMUP else 2,
                "target_karma_gain": 50 if phase == AccountPhase.WARMUP else 150,
                "target_profile_visits": 0 if phase == AccountPhase.WARMUP else 20,
            },
            "do_not_do": [
                "Post promotional content before karma > 1000",
                "Use the same account for multiple subreddits in the same day at startup",
                "Respond to every comment — looks robotic",
                "Post links to your store/site without community context",
                "Use keywords or phrases that sound like ad copy",
                "Vote manipulate — instant ban",
                "Delete posts or comments after submitting",
                "Use a VPN that Reddit has flagged",
            ]
        }

        return weekly_plan

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────

    async def _ensure_logged_in(self) -> bool:
        if not self.username or not self.password:
            logger.warning("No credentials. Running in research-only mode.")
            return False

        async with self.automation:
            is_logged_in = await self.automation.check_login_status()
            if not is_logged_in:
                return await self.automation.login(self.username, self.password)
            return True

    def _get_account(self) -> Optional[RedditAccount]:
        if not self._account and self.username:
            with db.session() as session:
                self._account = session.query(RedditAccount).filter_by(username=self.username).first()
        return self._account

    def _get_phase_info(self, account: RedditAccount) -> dict:
        if not account:
            return {"phase": AccountPhase.WARMUP, "days_in_phase": 0}

        days_in_warmup = account.days_since_warmup
        if days_in_warmup < self.strategy.warmup_days:
            return {"phase": AccountPhase.WARMUP, "days_remaining": self.strategy.warmup_days - days_in_warmup}
        elif account.total_karma < self.strategy.promotion_karma_threshold:
            return {"phase": AccountPhase.ACTIVE, "karma_needed": self.strategy.promotion_karma_threshold - account.total_karma}
        else:
            return {"phase": AccountPhase.PROMOTION, "karma": account.total_karma}

    def _get_warmup_subreddits(self) -> list:
        with db.session() as session:
            subs = session.query(Subreddit).filter(
                Subreddit.tier.in_([SubredditTier.RESEARCH, SubredditTier.CREDIBILITY])
            ).order_by(Subreddit.score_overall.desc()).limit(5).all()
            return [s.name for s in subs] or ["entrepreneur", "smallbusiness", "ecommerce"]

    def _get_active_subreddits(self) -> list:
        with db.session() as session:
            subs = session.query(Subreddit).filter(
                Subreddit.tier.in_([SubredditTier.CREDIBILITY, SubredditTier.ENGAGEMENT, SubredditTier.BUYER_INTENT])
            ).order_by(Subreddit.score_overall.desc()).limit(config.reddit_strategy.max_active_subreddits).all()
            return [s.name for s in subs] or ["dropshipping", "ecommerce", "entrepreneur"]

    def _log_action(self, action_type, content_body, subreddit_name, status, is_promotional=False):
        try:
            with db.session() as session:
                action = RedditAction(
                    action_type=action_type,
                    content_body=content_body[:2000],
                    status=status,
                    is_promotional=is_promotional,
                    executed_at=datetime.utcnow(),
                )
                session.add(action)
        except Exception as e:
            logger.error(f"Action log failed: {e}")

    async def _generate_initial_content_ideas(self, subreddits: list) -> dict:
        ideas = {}
        for sub_data in subreddits[:3]:
            sub_name = sub_data.get("subreddit", sub_data.get("name", ""))
            if sub_name:
                batch = await self.generate_content_batch(sub_name, count=3)
                ideas[sub_name] = batch
                await asyncio.sleep(1)
        return ideas

    async def _build_30_day_plan(self, subreddits: list) -> dict:
        top_subs = [s.get("subreddit", s.get("name", "")) for s in subreddits[:5] if s]
        return {
            "days_1_10": {
                "phase": "warmup",
                "focus": "Comment only. Build karma. No promotion.",
                "daily_actions": f"{self.strategy.warmup_daily_comments} comments in credibility subreddits",
                "target_subreddits": top_subs[:3],
                "success_metric": "Zero bans. Positive comment karma.",
            },
            "days_11_20": {
                "phase": "warmup_continued",
                "focus": "Increase comment quality and frequency. Start tracking which posts get most engagement.",
                "daily_actions": f"{self.strategy.warmup_daily_comments} comments + research tracking",
                "target_subreddits": top_subs,
                "success_metric": "200+ comment karma.",
            },
            "days_21_30": {
                "phase": "transition",
                "focus": "First original posts. Experience/lesson format only. No links yet.",
                "daily_actions": f"{self.strategy.warmup_daily_comments} comments + 1 post every 3 days",
                "target_subreddits": top_subs,
                "success_metric": "500+ karma. First post > 10 upvotes.",
            },
        }
