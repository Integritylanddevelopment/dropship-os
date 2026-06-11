"""
research/subreddit_analyzer.py — Subreddit scoring and strategy engine
Discovers, scores, and tiers subreddits for the niche.
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
from storage import db, Subreddit, SubredditTier


# Default subreddit discovery seeds by niche type
SUBREDDIT_SEEDS = {
    "dropshipping": [
        "dropshipping", "ecommerce", "entrepreneur", "smallbusiness",
        "shopify", "fulfillment", "AmazonSeller", "Flipping",
        "passive_income", "WorkOnline", "SideHustle", "beermoney",
        "personalfinance", "financialindependence", "frugal",
        "onlinebusiness", "startups", "Entrepreneur",
    ],
    "general": [
        "entrepreneur", "smallbusiness", "marketing", "socialmedia",
        "ecommerce", "sales", "passive_income",
    ]
}


class SubredditAnalyzer:
    """
    Discovers and scores subreddits.
    Returns tier-ranked list with strategic recommendations.
    """

    def __init__(self):
        self.automation = RedditBrowserAutomation()
        self.niche = config.niche
        self.seeds = SUBREDDIT_SEEDS.get(self.niche, SUBREDDIT_SEEDS["general"])

    async def discover_subreddits(self, seed_subreddits: list = None) -> list:
        """
        Discover relevant subreddits from seeds.
        Uses Reddit's search to find community-related subreddits.
        """
        seeds = seed_subreddits or self.seeds
        discovered = set(seeds)

        logger.info(f"Discovering subreddits for niche: {self.niche}")

        # Search for related subreddits
        try:
            import httpx
            search_terms = [self.niche, "online business", "side income", "make money online"]

            for term in search_terms[:3]:
                url = f"https://www.reddit.com/subreddits/search.json?q={term}&limit=25"
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        url,
                        headers={"User-Agent": config.browser.user_agents[0]},
                        timeout=15
                    )
                    data = resp.json()
                    for sub in data.get("data", {}).get("children", []):
                        name = sub.get("data", {}).get("display_name", "")
                        if name:
                            discovered.add(name)

                await asyncio.sleep(2)  # Be polite

        except Exception as e:
            logger.error(f"Subreddit discovery error: {e}")

        logger.info(f"Discovered {len(discovered)} candidate subreddits")
        return list(discovered)

    async def analyze_subreddit(self, subreddit_name: str) -> Optional[dict]:
        """
        Full analysis of a single subreddit.
        Returns scored strategy data.
        """
        logger.info(f"Analyzing r/{subreddit_name}")

        try:
            # Get metadata
            info = await self.automation.scrape_subreddit_info(subreddit_name)
            await asyncio.sleep(1)

            # Get sample posts
            posts = await self.automation.scrape_subreddit_posts(subreddit_name, limit=50)
            await asyncio.sleep(1)

            # Get rules
            rules = await self.automation.scrape_subreddit_rules(subreddit_name)
            await asyncio.sleep(1)

            if not posts and not info.get("subscribers"):
                logger.warning(f"r/{subreddit_name} returned no data — skipping")
                return None

            # AI analysis
            analysis = await generator.analyze_subreddit_for_strategy(
                subreddit_name,
                posts,
                self.niche
            )

            # Combine data
            result = {
                **info,
                **analysis,
                "rules": rules,
                "post_sample_count": len(posts),
                "analyzed_at": datetime.utcnow().isoformat(),
            }

            return result

        except Exception as e:
            logger.error(f"Subreddit analysis failed for r/{subreddit_name}: {e}")
            return None

    async def run_full_discovery(self, max_subreddits: int = 30) -> list:
        """
        Discover + analyze + score + tier all relevant subreddits.
        Returns sorted list ready for strategy use.
        """
        logger.info(f"Starting full subreddit discovery (max: {max_subreddits})")

        # Step 1: Discover candidates
        candidates = await self.discover_subreddits()
        candidates = candidates[:max_subreddits]

        results = []
        for i, subreddit in enumerate(candidates):
            logger.info(f"[{i+1}/{len(candidates)}] Analyzing r/{subreddit}")
            analysis = await self.analyze_subreddit(subreddit)
            if analysis:
                results.append(analysis)

            # Save to DB
            if analysis:
                await self._save_to_db(subreddit, analysis)

            await asyncio.sleep(3)  # Rate limiting

        # Sort by overall score
        results.sort(key=lambda x: x.get("scores", {}).get("overall", 0), reverse=True)

        logger.info(f"Discovery complete: {len(results)} subreddits analyzed and scored")
        return results

    async def _save_to_db(self, subreddit_name: str, analysis: dict):
        """Persist subreddit analysis to database"""
        try:
            scores = analysis.get("scores", {})
            tier_map = {
                "research": SubredditTier.RESEARCH,
                "credibility": SubredditTier.CREDIBILITY,
                "engagement": SubredditTier.ENGAGEMENT,
                "buyer_intent": SubredditTier.BUYER_INTENT,
            }
            tier_str = analysis.get("tier", "research").lower()
            tier = tier_map.get(tier_str, SubredditTier.RESEARCH)

            with db.session() as session:
                existing = session.query(Subreddit).filter_by(name=subreddit_name).first()

                if existing:
                    sub = existing
                else:
                    sub = Subreddit(name=subreddit_name)
                    session.add(sub)

                sub.display_name = analysis.get("display_name", subreddit_name)
                sub.subscriber_count = analysis.get("subscribers", 0)
                sub.active_users = analysis.get("active_users", 0)
                sub.tier = tier
                sub.score_audience_quality = scores.get("audience_quality", 0)
                sub.score_pain_intensity = scores.get("pain_intensity", 0)
                sub.score_relevance = scores.get("relevance", 0)
                sub.score_post_opportunity = scores.get("post_opportunity", 0)
                sub.score_comment_opportunity = scores.get("comment_opportunity", 0)
                sub.score_promotion_tolerance = scores.get("promotion_tolerance", 0)
                sub.score_lead_potential = scores.get("lead_potential", 0)
                sub.score_authority_potential = scores.get("authority_potential", 0)
                sub.score_ease_of_entry = scores.get("ease_of_entry", 0)
                sub.score_overall = scores.get("overall", 0)
                sub.key_pain_points = analysis.get("key_pain_points", [])
                sub.buyer_signals = analysis.get("buyer_signals", [])
                sub.top_performing_formats = analysis.get("dominant_post_types", [])
                sub.rules_summary = str(analysis.get("rules", []))[:1000]
                sub.last_analyzed = datetime.utcnow()

        except Exception as e:
            logger.error(f"DB save failed for r/{subreddit_name}: {e}")

    def get_tier_report(self) -> dict:
        """Get current subreddit tier assignments from DB"""
        with db.session() as session:
            subs = session.query(Subreddit).order_by(Subreddit.score_overall.desc()).all()
            tiers = {
                "tier1_research": [],
                "tier2_credibility": [],
                "tier3_engagement": [],
                "tier4_buyer_intent": [],
                "untiered": [],
            }
            for sub in subs:
                entry = {
                    "name": sub.name,
                    "score": sub.score_overall,
                    "subscribers": sub.subscriber_count,
                }
                if sub.tier == SubredditTier.RESEARCH:
                    tiers["tier1_research"].append(entry)
                elif sub.tier == SubredditTier.CREDIBILITY:
                    tiers["tier2_credibility"].append(entry)
                elif sub.tier == SubredditTier.ENGAGEMENT:
                    tiers["tier3_engagement"].append(entry)
                elif sub.tier == SubredditTier.BUYER_INTENT:
                    tiers["tier4_buyer_intent"].append(entry)
                else:
                    tiers["untiered"].append(entry)
            return tiers
