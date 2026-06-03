"""
Pinterest AI Agent — Research Agent
Handles keyword discovery, market intelligence, competitor analysis, opportunity scoring.
"""
import json
import time
import requests
from datetime import datetime
from typing import Optional
from database import Database
from integrations.claude_client import ClaudeClient
from integrations.pinterest_api import PinterestAPI


class ResearchAgent:
    """
    Research Agent: Finds where the cheapest attention meets the highest-margin products.
    Operates like a stock market research firm — tracking search demand vs. competition.
    """

    def __init__(self, pinterest: PinterestAPI, claude: ClaudeClient, db: Database):
        self.pinterest = pinterest
        self.claude = claude
        self.db = db

    # =========================================================
    # KEYWORD RESEARCH
    # =========================================================
    def discover_keywords(
        self,
        seed_keywords: list[str],
        niche: str,
        save_to_db: bool = True,
    ) -> list[dict]:
        """
        Expand seed keywords into full Pinterest keyword clusters using Claude.
        Saves all discovered keywords to the database.
        """
        print(f"\n🔍 Expanding {len(seed_keywords)} seed keywords for niche: {niche}")
        all_keywords = []

        for seed in seed_keywords:
            print(f"  → Expanding: {seed}")
            try:
                keywords = self.claude.expand_keyword_cluster(seed, niche)
                for kw in keywords:
                    kw["cluster"] = seed
                    if save_to_db:
                        self.db.upsert_keyword(kw)
                all_keywords.extend(keywords)
            except Exception as e:
                print(f"    ⚠️  Error expanding {seed}: {e}")

        print(f"  ✅ Discovered {len(all_keywords)} total keywords")
        return all_keywords

    def get_pinterest_trending(self, region: str = "US") -> list[dict]:
        """Pull Pinterest trending keywords for the region."""
        try:
            trends = self.pinterest.get_trending_keywords(region=region)
            print(f"  ✅ Retrieved {len(trends)} trending keywords from Pinterest")
            return trends
        except Exception as e:
            print(f"  ⚠️  Trending API unavailable (requires Pinterest business access): {e}")
            return []

    def scrape_pinterest_autocomplete(self, queries: list[str]) -> dict[str, list[str]]:
        """
        Simulate Pinterest autocomplete suggestions using Pinterest's suggest API.
        Returns dict of {query: [suggestion1, suggestion2, ...]}
        Note: Pinterest does not publicly expose their autocomplete API.
        This uses the keyword suggestions endpoint as a proxy.
        """
        results = {}
        for query in queries:
            try:
                suggestions = self.pinterest.get_keyword_suggestions(query)
                results[query] = suggestions
                time.sleep(0.3)
            except Exception:
                results[query] = []
        return results

    def rank_keywords_by_opportunity(
        self,
        keywords: list[dict],
        sort_by: str = "overall_score",
    ) -> list[dict]:
        """Rank keywords by opportunity score and return sorted list."""
        scored = []
        for kw in keywords:
            # Calculate overall score if not present
            if "overall_score" not in kw or kw["overall_score"] == 5.0:
                scores = [
                    kw.get("buyer_intent_score", 5),
                    kw.get("save_potential_score", 5),
                    kw.get("click_potential_score", 5),
                    kw.get("traffic_potential_score", 5),
                ]
                # Competition is inverted (low competition = high score)
                comp_map = {"low": 9, "medium": 6, "high": 3}
                comp_score = comp_map.get(kw.get("competition", "medium"), 6)
                scores.append(comp_score)
                kw["overall_score"] = sum(scores) / len(scores)
            scored.append(kw)

        return sorted(scored, key=lambda x: x.get(sort_by, 0), reverse=True)

    # =========================================================
    # OPPORTUNITY SCORING
    # =========================================================
    def score_opportunities(
        self,
        opportunities: list[dict],
        niche: str,
        save_to_db: bool = True,
    ) -> list[dict]:
        """
        Score each opportunity using the 10-dimension framework.
        Ranks them to identify where cheapest attention + highest margin intersect.
        """
        print(f"\n📊 Scoring {len(opportunities)} opportunities...")
        scored = []

        for i, opp in enumerate(opportunities):
            topic = opp.get("topic", "")
            print(f"  [{i+1}/{len(opportunities)}] Scoring: {topic}")
            try:
                result = self.claude.score_opportunity(
                    niche=niche,
                    topic=topic,
                    context=opp.get("context", ""),
                )
                result["priority_rank"] = i + 1
                if save_to_db:
                    self.db.save_opportunity(result)
                scored.append(result)
            except Exception as e:
                print(f"    ⚠️  Error scoring {topic}: {e}")

        # Sort by overall score
        scored.sort(key=lambda x: x.get("overall_score", 0), reverse=True)

        # Re-assign priority ranks after sorting
        for i, opp in enumerate(scored):
            opp["priority_rank"] = i + 1

        print(f"  ✅ Scored {len(scored)} opportunities")
        return scored

    def identify_fast_wins(self, niche: str) -> list[dict]:
        """Identify the fastest-win content opportunities based on stored data."""
        opportunities = self.db.get_opportunities(niche)
        fast_wins = []
        for opp in opportunities:
            # Fast win criteria: high buyer intent + low competition + high click potential
            if (
                opp.get("buyer_intent", 0) >= 8
                and opp.get("competition_level", 0) >= 7  # Inverted: 7+ = lower competition
                and opp.get("click_potential", 0) >= 7
            ):
                fast_wins.append(opp)
        return fast_wins[:10]

    # =========================================================
    # COMPETITOR INTELLIGENCE
    # =========================================================
    def analyze_competitor(
        self,
        competitor_url: str,
        save_to_db: bool = True,
    ) -> dict:
        """
        Analyze a competitor Pinterest account.
        Since Pinterest API doesn't expose competitor data, this uses
        available data patterns and Claude analysis.
        """
        print(f"\n🕵️  Analyzing competitor: {competitor_url}")

        # Build competitor data from URL pattern analysis
        competitor_data = {
            "url": competitor_url,
            "account_name": competitor_url.split("/")[-1].replace("_", " ").title(),
            "analysis_date": datetime.now().isoformat(),
            "note": "Manual competitor research required — Pinterest API restricts competitor data. Use Pinterest web interface to gather board names, pin counts, and top-performing pins."
        }

        # Generate strategic analysis using Claude
        analysis = self.claude.analyze_competitor_strategy(
            competitor_data=competitor_data,
            your_niche="drop shipping home, kitchen, lifestyle products"
        )

        if save_to_db:
            self.db._conn().__enter__().execute("""
                INSERT INTO competitor_intel
                (account_url, account_name, top_boards, top_content_themes,
                 keyword_patterns, gaps_identified, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                competitor_url,
                competitor_data["account_name"],
                json.dumps(analysis.get("working_themes", [])),
                json.dumps(analysis.get("working_themes", [])),
                json.dumps(analysis.get("keyword_patterns", [])),
                json.dumps(analysis.get("content_gaps", [])),
                datetime.now().isoformat(),
            ))

        return analysis

    # =========================================================
    # SEASONAL INTELLIGENCE
    # =========================================================
    def build_seasonal_calendar(
        self,
        niche: str,
        year: int = None,
        save_to_db: bool = True,
    ) -> list[dict]:
        """Generate and store the full seasonal content calendar."""
        if year is None:
            year = datetime.now().year

        print(f"\n📅 Building seasonal calendar for {year} in niche: {niche}")

        calendar = self.claude.generate_seasonal_calendar(niche, year)

        if save_to_db:
            for event in calendar:
                try:
                    self.db.save_seasonal_event(event)
                except Exception as e:
                    print(f"  ⚠️  Error saving event {event.get('event')}: {e}")

        print(f"  ✅ Generated {len(calendar)} seasonal events")
        return calendar

    def get_upcoming_priorities(self, days_ahead: int = 60) -> list[dict]:
        """Get seasonal events that need content published soon."""
        upcoming = self.db.get_upcoming_seasonal(days_ahead)
        print(f"\n⏰ Upcoming seasonal priorities (next {days_ahead} days):")
        for event in upcoming:
            print(f"  → {event['event']} | Publish by: {event['publish_by']}")
        return upcoming

    # =========================================================
    # MARKET SIGNAL ANALYSIS
    # =========================================================
    def extract_market_signals(self, niche: str) -> dict:
        """
        Analyze stored data to extract market signals:
        - Top performing keywords
        - Best opportunity areas
        - Seasonal priorities
        - Content gaps
        """
        keywords = self.db.get_keywords(limit=50)
        opportunities = self.db.get_opportunities(niche)

        top_keywords = self.rank_keywords_by_opportunity(keywords)[:10]
        top_opportunities = opportunities[:5]
        upcoming_seasonal = self.db.get_upcoming_seasonal(60)

        signals = {
            "generated_at": datetime.now().isoformat(),
            "niche": niche,
            "top_keywords": [
                {
                    "keyword": kw["keyword"],
                    "score": kw.get("overall_score", 5),
                    "intent": kw.get("intent_type", "unknown"),
                    "competition": kw.get("competition", "unknown"),
                }
                for kw in top_keywords
            ],
            "top_opportunities": [
                {
                    "topic": opp["topic"],
                    "overall_score": opp["overall_score"],
                    "buyer_intent": opp.get("buyer_intent", 5),
                    "recommended_action": opp.get("recommended_action", ""),
                }
                for opp in top_opportunities
            ],
            "upcoming_seasonal": [
                {
                    "event": ev["event"],
                    "publish_by": ev["publish_by"],
                    "days_until": ev.get("lead_days", 45),
                }
                for ev in upcoming_seasonal[:3]
            ],
            "summary": {
                "total_keywords": len(keywords),
                "total_opportunities": len(opportunities),
                "seasonal_events_upcoming": len(upcoming_seasonal),
            }
        }

        return signals

    def generate_research_report(self, niche: str) -> str:
        """Generate a formatted research report for the current niche."""
        signals = self.extract_market_signals(niche)
        report = f"""
╔══════════════════════════════════════════════════════╗
║         PINTEREST RESEARCH REPORT — {signals['niche'][:20]:20} ║
║         Generated: {signals['generated_at'][:10]}                    ║
╚══════════════════════════════════════════════════════╝

📊 DATABASE SUMMARY:
  Keywords tracked: {signals['summary']['total_keywords']}
  Opportunities scored: {signals['summary']['total_opportunities']}
  Seasonal events upcoming: {signals['summary']['seasonal_events_upcoming']}

🎯 TOP KEYWORD OPPORTUNITIES:
"""
        for i, kw in enumerate(signals["top_keywords"], 1):
            report += f"  {i:2}. {kw['keyword']:<45} Score: {kw['score']:.1f} | {kw['competition']} competition\n"

        report += "\n🏆 TOP CONTENT OPPORTUNITIES:\n"
        for i, opp in enumerate(signals["top_opportunities"], 1):
            report += f"  {i}. {opp['topic']:<40} Score: {opp['overall_score']:.1f}\n"
            report += f"     → {opp['recommended_action']}\n"

        if signals["upcoming_seasonal"]:
            report += "\n⏰ PUBLISH THESE NOW:\n"
            for ev in signals["upcoming_seasonal"]:
                report += f"  → {ev['event']:<35} | Publish by: {ev['publish_by']}\n"

        return report
