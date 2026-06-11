"""
research/market_research.py — Market intelligence extraction engine
Extracts pain points, customer language, objections, triggers from Reddit and Pinterest.
This is your real-time customer research lab.
"""

import asyncio
from typing import Optional
from loguru import logger
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config
from content.generator import generator
from automation.reddit_browser import RedditBrowserAutomation
from storage import db, ResearchIntel, Platform


class MarketResearchEngine:
    """
    Extracts buyer psychology data from Reddit.
    Output feeds directly into: ad copy, landing pages, product positioning, content.
    """

    def __init__(self):
        self.reddit = RedditBrowserAutomation()
        self.niche = config.niche

    async def research_subreddit(
        self,
        subreddit: str,
        depth: int = 3,
        posts_limit: int = 50
    ) -> dict:
        """
        Deep research pass on a subreddit.
        Extracts all market intelligence signals.
        depth: 1=titles only, 2=posts+comments, 3=full thread analysis
        """
        logger.info(f"Market research: r/{subreddit} (depth={depth})")

        # Collect posts
        posts = await self.reddit.scrape_subreddit_posts(subreddit, sort="top", limit=posts_limit)
        await asyncio.sleep(1)

        # Also get recent posts for fresh signals
        recent = await self.reddit.scrape_subreddit_posts(subreddit, sort="new", limit=25)
        posts.extend(recent)

        # Prepare for AI analysis
        raw_content = []
        for post in posts:
            entry = f"TITLE: {post.get('title', '')}"
            if post.get('selftext'):
                entry += f"\nBODY: {post['selftext'][:400]}"
            raw_content.append(entry)

        # Extract intelligence
        intel = await generator.extract_market_research(raw_content, "Reddit")

        # Save to DB
        await self._save_intel(subreddit, intel)

        # Return structured report
        return {
            "subreddit": subreddit,
            "posts_analyzed": len(posts),
            "intelligence": intel,
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def research_keyword(
        self,
        keyword: str,
        subreddits: list = None
    ) -> dict:
        """
        Search Reddit for a keyword across subreddits to extract buying signals.
        Best used for product-specific research.
        """
        logger.info(f"Keyword research across Reddit: '{keyword}'")

        results = await self.reddit.search_reddit(keyword, limit=50)

        raw_content = [
            f"TITLE: {r.get('title', '')}\nBODY: {r.get('selftext', '')[:300]}"
            for r in results
        ]

        intel = await generator.extract_market_research(raw_content, "Reddit")

        return {
            "keyword": keyword,
            "results_analyzed": len(results),
            "intelligence": intel,
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def find_competitor_mentions(self, competitor_names: list) -> dict:
        """
        Find how Reddit talks about competitors.
        Gold for positioning and differentiation.
        """
        logger.info(f"Researching competitor mentions: {competitor_names}")
        all_mentions = []

        for competitor in competitor_names:
            results = await self.reddit.search_reddit(competitor, limit=25)
            for r in results:
                r["competitor"] = competitor
                all_mentions.append(r)
            await asyncio.sleep(1.5)

        raw_content = [
            f"COMPETITOR: {r.get('competitor')}\nTITLE: {r.get('title', '')}\nBODY: {r.get('selftext', '')[:300]}"
            for r in all_mentions
        ]

        intel = await generator.extract_market_research(raw_content, "Reddit")

        return {
            "competitors_researched": competitor_names,
            "mentions_found": len(all_mentions),
            "intelligence": intel,
        }

    async def run_full_research_pass(
        self,
        subreddits: list,
        keywords: list = None,
        competitors: list = None
    ) -> dict:
        """
        Complete market research pass: subreddits + keywords + competitors.
        Returns comprehensive buyer intelligence report.
        """
        logger.info("Starting full market research pass")
        report = {
            "subreddit_intel": [],
            "keyword_intel": [],
            "competitor_intel": {},
            "summary": {},
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Subreddit research
        for sub in subreddits[:5]:  # Limit to avoid rate limiting
            intel = await self.research_subreddit(sub)
            report["subreddit_intel"].append(intel)
            await asyncio.sleep(3)

        # Keyword research
        if keywords:
            for kw in keywords[:5]:
                intel = await self.research_keyword(kw)
                report["keyword_intel"].append(intel)
                await asyncio.sleep(2)

        # Competitor research
        if competitors:
            intel = await self.find_competitor_mentions(competitors)
            report["competitor_intel"] = intel

        # Synthesize
        all_pain_points = []
        all_language = []
        all_objections = []

        for sub_intel in report["subreddit_intel"]:
            data = sub_intel.get("intelligence", {})
            all_pain_points.extend(data.get("pain_points", []))
            all_language.extend(data.get("customer_language", []))
            all_objections.extend(data.get("buying_objections", []))

        report["summary"] = {
            "top_pain_points": all_pain_points[:10],
            "top_customer_language": all_language[:15],
            "top_objections": all_objections[:8],
        }

        logger.info("Full market research pass complete")
        return report

    async def _save_intel(self, subreddit: str, intel: dict):
        """Persist research intel to database"""
        try:
            with db.session() as session:
                for pain in intel.get("pain_points", []):
                    entry = ResearchIntel(
                        platform=Platform.REDDIT,
                        intel_type="pain_point",
                        content=pain.get("pain", str(pain)),
                        frequency=1,
                        priority=pain.get("emotional_intensity", 5) if isinstance(pain, dict) else 5,
                        can_use_in_ad_copy=True,
                        can_use_in_content=True,
                    )
                    session.add(entry)

                for lang in intel.get("customer_language", []):
                    entry = ResearchIntel(
                        platform=Platform.REDDIT,
                        intel_type="language",
                        content=str(lang),
                        can_use_in_ad_copy=True,
                        can_use_in_content=True,
                    )
                    session.add(entry)

        except Exception as e:
            logger.error(f"Intel save failed: {e}")

    def get_research_report(self) -> dict:
        """Get aggregated research intel from DB"""
        with db.session() as session:
            all_intel = session.query(ResearchIntel).all()
            report = {"pain_points": [], "language": [], "objections": [], "triggers": []}
            for intel in all_intel:
                report[intel.intel_type + "s" if not intel.intel_type.endswith("s") else intel.intel_type].append({
                    "content": intel.content,
                    "frequency": intel.frequency,
                    "priority": intel.priority,
                })
            return report
