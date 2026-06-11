"""
agents/pinterest_agent.py — Pinterest Organic Growth Agent
Full Pinterest strategy orchestrator.
keyword research → board strategy → pin creation → publishing → scale
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
from automation.pinterest_browser import PinterestBrowserAutomation
from storage import (
    db, PinterestBoard, PinterestPin, PinterestKeyword,
    ContentIdea, WeeklyPlan, PerformanceMetric, Platform, ActionStatus
)


class PinterestAgent:
    """
    Full Pinterest organic growth agent.

    Phases:
    1. SETUP — Keyword research, board strategy, account optimization
    2. SEEDING — Create initial boards and seed pins
    3. SCALING — Daily publishing, performance tracking, iteration
    4. COMPOUNDING — Repurpose top performers, seasonal pushes
    """

    def __init__(self, email: str = None, password: str = None, auto_mode: bool = False):
        self.email = email
        self.password = password
        self.auto_mode = auto_mode
        self.strategy = config.pinterest_strategy
        self.automation = PinterestBrowserAutomation()
        self.niche = config.niche

    # ─────────────────────────────────────────────
    # PHASE 0: SETUP
    # ─────────────────────────────────────────────

    async def setup(self, niche_override: str = None) -> dict:
        """
        Complete Pinterest setup:
        - Keyword research and cluster mapping
        - Board strategy design
        - Initial pin content calendar
        - 30-day publishing plan
        """
        niche = niche_override or self.niche
        logger.info(f"🚀 Starting Pinterest Agent setup for: {niche}")

        report = {
            "phase": "setup",
            "niche": niche,
            "keyword_strategy": {},
            "board_strategy": {},
            "content_calendar": {},
            "publishing_plan": {},
        }

        # Step 1: Keyword research
        logger.info("Step 1/4: Building keyword strategy...")
        keywords = await generator.generate_keyword_clusters(niche, config.target_products)
        report["keyword_strategy"] = keywords
        await self._save_keywords(keywords)
        await asyncio.sleep(1)

        # Step 2: Board strategy
        logger.info("Step 2/4: Designing board strategy...")
        boards = await generator.generate_board_strategy(niche, config.target_products)
        report["board_strategy"] = boards
        await asyncio.sleep(1)

        # Step 3: Generate initial pin content
        logger.info("Step 3/4: Generating initial pin content...")
        pins = await self._generate_initial_pin_batch(keywords, boards)
        report["content_calendar"] = pins
        await asyncio.sleep(1)

        # Step 4: Publishing plan
        logger.info("Step 4/4: Building publishing plan...")
        plan = await self._build_publishing_plan(boards)
        report["publishing_plan"] = plan

        logger.info("✅ Pinterest Agent setup complete")
        return report

    # ─────────────────────────────────────────────
    # PHASE 1: SEEDING
    # ─────────────────────────────────────────────

    async def create_boards(self, boards_data: list = None) -> list:
        """Create boards from the strategy. Uses browser automation or API."""
        if not boards_data:
            boards_data = await self._get_boards_from_db()

        created = []

        for board in boards_data[:20]:
            name = board.get("name", "")
            description = board.get("description", "")

            if not name:
                continue

            logger.info(f"Creating board: {name}")

            if self.auto_mode and self.email and self.password:
                async with self.automation:
                    url = await self.automation.create_board(name, description)
                    if url:
                        created.append({"name": name, "url": url, "status": "created"})
                    else:
                        created.append({"name": name, "status": "failed"})
            else:
                # Dry run — save to DB only
                self._save_board_to_db(board)
                created.append({"name": name, "status": "planned", "dry_run": True})

            await asyncio.sleep(random.uniform(3, 8))

        return created

    # ─────────────────────────────────────────────
    # PHASE 2: DAILY PUBLISHING
    # ─────────────────────────────────────────────

    async def run_daily_session(self, pins_today: int = None) -> dict:
        """
        Daily pin publishing session.
        Generates and publishes pins across boards.
        """
        pins_today = pins_today or self.strategy.daily_pins
        logger.info(f"📌 Running Pinterest daily session ({pins_today} pins)")

        session = {
            "date": datetime.utcnow().isoformat(),
            "pins_published": 0,
            "pins_planned": pins_today,
            "content_generated": [],
            "errors": [],
        }

        # Get keyword-board pairs to target
        targets = await self._get_daily_targets(pins_today)

        for target in targets:
            try:
                keyword = target.get("keyword", config.niche)
                board_name = target.get("board", "General")
                pin_format = target.get("format", "standard")
                funnel_stage = target.get("funnel", "awareness")

                # Generate pin content
                pin_data = await generator.generate_pin_content(
                    topic=f"{config.niche} {keyword}",
                    keyword=keyword,
                    pin_format=pin_format,
                    destination_url=config.website_url,
                    funnel_stage=funnel_stage,
                    niche=config.niche,
                )

                if self.auto_mode and self.email and self.password:
                    async with self.automation:
                        # Log in if needed
                        await self.automation.login(self.email, self.password)

                        pin_url = await self.automation.create_pin(
                            board_name=board_name,
                            title=pin_data.get("title", ""),
                            description=pin_data.get("description", ""),
                            destination_url=config.website_url,
                        )

                        if pin_url:
                            session["pins_published"] += 1
                            self._save_pin_to_db(pin_data, board_name, ActionStatus.COMPLETED)
                        else:
                            session["errors"].append(f"Pin creation failed: {pin_data.get('title', '')[:50]}")
                else:
                    # Dry run
                    session["pins_published"] += 1
                    self._save_pin_to_db(pin_data, board_name, ActionStatus.PENDING)
                    session["content_generated"].append({
                        "title": pin_data.get("title", "")[:80],
                        "board": board_name,
                        "keyword": keyword,
                        "text_overlay": pin_data.get("text_overlay", ""),
                        "dry_run": True,
                    })

                await asyncio.sleep(random.uniform(5, 15))  # Natural delay between pins

            except Exception as e:
                logger.error(f"Pin session error: {e}")
                session["errors"].append(str(e))

        logger.info(f"Pinterest session: {session['pins_published']} pins published")
        return session

    # ─────────────────────────────────────────────
    # RESEARCH
    # ─────────────────────────────────────────────

    async def run_keyword_research(self, seed_keywords: list = None) -> dict:
        """
        Full Pinterest keyword research session.
        Uses autocomplete + competitor analysis.
        """
        seeds = seed_keywords or [config.niche] + config.target_products
        all_keywords = {}

        async with self.automation:
            for seed in seeds[:5]:
                suggestions = await self.automation.get_keyword_suggestions(seed)
                all_keywords[seed] = suggestions
                await asyncio.sleep(2)

        # AI cluster + intent analysis
        keyword_strategy = await generator.generate_keyword_clusters(
            config.niche,
            config.target_products
        )

        # Merge with discovered suggestions
        keyword_strategy["discovered_from_autocomplete"] = all_keywords

        return keyword_strategy

    async def research_competitors(self, competitor_usernames: list) -> list:
        """Analyze competitor Pinterest accounts"""
        reports = []

        async with self.automation:
            for username in competitor_usernames:
                analysis = await self.automation.analyze_competitor_boards(username)
                reports.append(analysis)
                await asyncio.sleep(3)

        return reports

    async def get_trending_topics(self) -> list:
        """Pull current Pinterest trending topics"""
        async with self.automation:
            trends = await self.automation.research_trending_topics()
        return trends

    # ─────────────────────────────────────────────
    # PERFORMANCE & OPTIMIZATION
    # ─────────────────────────────────────────────

    async def analyze_pin_performance(self) -> dict:
        """Analyze which pins are performing and why"""
        with db.session() as session:
            pins = session.query(PinterestPin).filter(
                PinterestPin.status == ActionStatus.COMPLETED
            ).order_by(PinterestPin.saves.desc()).all()

            if not pins:
                return {"message": "No published pins to analyze yet"}

            top_pins = []
            low_pins = []
            for pin in pins:
                data = {
                    "title": pin.title,
                    "saves": pin.saves,
                    "clicks": pin.outbound_clicks,
                    "impressions": pin.impressions,
                    "keyword": pin.primary_keyword,
                    "format": pin.pin_format,
                    "funnel_stage": pin.funnel_stage,
                }
                if pin.saves >= self.strategy.min_saves_for_boost:
                    top_pins.append(data)
                else:
                    low_pins.append(data)

            return {
                "total_pins": len(pins),
                "top_performers": top_pins[:10],
                "low_performers": low_pins[:5],
                "optimization_notes": [
                    f"Boost top {len(top_pins)} pins by creating 3-5 variations each",
                    "Retire low performers after 30 days if < 2 saves",
                    "Identify common keywords in top performers and create more content around them",
                ],
            }

    async def generate_seasonal_calendar(self) -> dict:
        """Generate a seasonal content calendar"""
        seasons = {
            "Q1_jan_mar": ["new year", "winter", "valentine", "spring prep"],
            "Q2_apr_jun": ["spring", "mothers day", "graduation", "summer prep"],
            "Q3_jul_sep": ["summer", "back to school", "fall prep"],
            "Q4_oct_dec": ["halloween", "thanksgiving", "black friday", "christmas", "holiday gifts"],
        }

        calendar = {}
        for period, themes in seasons.items():
            pins = []
            for theme in themes[:2]:
                pin = await generator.generate_pin_content(
                    topic=f"{config.niche} {theme}",
                    keyword=f"{config.niche} {theme}",
                    pin_format="standard",
                    destination_url=config.website_url,
                    funnel_stage="awareness",
                )
                pins.append(pin)
                await asyncio.sleep(0.5)
            calendar[period] = {
                "themes": themes,
                "sample_pins": pins,
                "post_start": f"{self.strategy.seasonal_lead_days} days before season peak",
            }

        return calendar

    # ─────────────────────────────────────────────
    # WEEKLY PLAN
    # ─────────────────────────────────────────────

    async def generate_weekly_plan(self) -> dict:
        """Generate a full 7-day Pinterest execution plan"""
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        pin_distribution = {
            "monday": 3,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 2,
            "friday": 2,
            "saturday": 2,
            "sunday": 1,
        }

        plan = {}
        for day in days:
            plan[day] = {
                "pins_to_publish": pin_distribution[day],
                "focus": "product pins" if day in ["monday", "wednesday", "friday"] else "content/blog pins",
                "boards_to_hit": "rotate across 3-4 active boards",
                "timing": "8am, 12pm, 8pm EST (peak engagement windows)",
                "research_task": "15 min keyword tracking" if day == "monday" else None,
                "analysis_task": "Review saves and clicks" if day == "friday" else None,
            }

        return {
            "week_start": datetime.utcnow().strftime("%Y-%m-%d"),
            "total_pins_planned": sum(pin_distribution.values()),
            "plan": plan,
            "kpis": {
                "target_impressions": 5000,
                "target_saves": 50,
                "target_outbound_clicks": 20,
                "target_new_followers": 10,
            },
            "do_not_do": [
                "Repin the same image to the same board twice in a week",
                "Use keyword stuffing in descriptions",
                "Upload low-resolution images (minimum 1000x1500px)",
                "Pin with broken destination URLs",
                "Ignore seasonal lead times — pin holiday content 45 days early",
                "Create boards with zero content — minimum 10 pins before making public",
                "Use hashtags excessively — 2-5 max, highly relevant only",
                "Copy competitor pins directly — create inspired variations",
            ]
        }

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────

    async def _get_daily_targets(self, count: int) -> list:
        """Build list of keyword + board + format targets for the day"""
        with db.session() as session:
            keywords = session.query(PinterestKeyword).order_by(
                PinterestKeyword.priority_score.desc()
            ).limit(count * 2).all()

            boards = session.query(PinterestBoard).filter_by(is_active=True).all()

        formats = ["standard", "checklist", "comparison", "tutorial", "problem_solution"]
        stages = ["awareness", "consideration", "conversion"]

        targets = []
        for i in range(count):
            kw = keywords[i % len(keywords)].keyword if keywords else config.niche
            board = boards[i % len(boards)].name if boards else "General"
            targets.append({
                "keyword": kw,
                "board": board,
                "format": formats[i % len(formats)],
                "funnel": stages[i % len(stages)],
            })

        return targets

    async def _generate_initial_pin_batch(self, keywords: dict, boards: dict) -> list:
        """Generate first batch of pins for setup"""
        pins = []
        core_clusters = keywords.get("core_clusters", [])[:5]

        for cluster in core_clusters:
            kw = cluster.get("primary_keyword", config.niche)
            pin = await generator.generate_pin_content(
                topic=f"{config.niche} {kw}",
                keyword=kw,
                pin_format="standard",
                destination_url=config.website_url,
                funnel_stage="awareness",
            )
            pins.append(pin)
            await asyncio.sleep(0.5)

        return pins

    async def _build_publishing_plan(self, boards: dict) -> dict:
        board_list = boards.get("first_10_to_create", [])
        return {
            "week_1": "Create all boards. Pin 5 seed pins per board.",
            "week_2": f"Publish {self.strategy.daily_pins} fresh pins daily across all boards.",
            "week_3": "Identify top-saving pins. Create 3 variations of each.",
            "week_4": "Start seasonal content calendar. Begin tracking outbound clicks.",
            "month_2_plus": "Double down on top-performing keyword clusters. Add new boards for emerging topics.",
        }

    async def _get_boards_from_db(self) -> list:
        with db.session() as session:
            boards = session.query(PinterestBoard).filter_by(is_active=True).all()
            return [{"name": b.name, "description": b.description} for b in boards]

    async def _save_keywords(self, keywords: dict):
        try:
            with db.session() as session:
                for cluster in keywords.get("core_clusters", []):
                    for kw in [cluster.get("primary_keyword")] + cluster.get("long_tail_keywords", []):
                        if kw:
                            existing = session.query(PinterestKeyword).filter_by(keyword=kw).first()
                            if not existing:
                                session.add(PinterestKeyword(
                                    keyword=kw,
                                    cluster=cluster.get("cluster_name", ""),
                                    intent_type=cluster.get("intent_type", ""),
                                    search_volume=cluster.get("search_volume", "medium"),
                                    competition=cluster.get("competition", "medium"),
                                    priority_score=float(cluster.get("priority", 5)),
                                ))
        except Exception as e:
            logger.error(f"Keyword save failed: {e}")

    def _save_board_to_db(self, board: dict):
        try:
            with db.session() as session:
                existing = session.query(PinterestBoard).filter_by(name=board.get("name", "")).first()
                if not existing:
                    session.add(PinterestBoard(
                        name=board.get("name", ""),
                        description=board.get("description", ""),
                        primary_keyword=board.get("primary_keyword", ""),
                        board_tier=board.get("board_type", "core"),
                    ))
        except Exception as e:
            logger.error(f"Board DB save failed: {e}")

    def _save_pin_to_db(self, pin_data: dict, board_name: str, status: ActionStatus):
        try:
            with db.session() as session:
                session.add(PinterestPin(
                    title=pin_data.get("title", "")[:200],
                    description=pin_data.get("description", "")[:500],
                    destination_url=config.website_url,
                    primary_keyword=pin_data.get("primary_keyword", ""),
                    keywords=pin_data.get("secondary_keywords", []),
                    pin_format=pin_data.get("pin_format", "standard"),
                    status=status,
                    published_at=datetime.utcnow() if status == ActionStatus.COMPLETED else None,
                ))
        except Exception as e:
            logger.error(f"Pin DB save failed: {e}")
