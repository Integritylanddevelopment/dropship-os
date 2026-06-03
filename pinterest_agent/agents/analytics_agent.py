"""
Pinterest AI Agent — Analytics Agent
Tracks pin/board performance, identifies top performers, computes scores,
generates actionable reports, and drives the optimize→repurpose loop.
"""
import json
from datetime import datetime, timedelta
from typing import Optional
from database import Database
from integrations.pinterest_api import PinterestAPI, PinterestAPIError


class AnalyticsAgent:
    """
    Analytics Agent: The intelligence layer.
    Identifies what's working, what's compounding, and what to double down on.
    """

    def __init__(self, pinterest: PinterestAPI, db: Database):
        self.pinterest = pinterest
        self.db = db

    # =========================================================
    # ANALYTICS COLLECTION
    # =========================================================
    def refresh_pin_analytics(
        self,
        days_back: int = 30,
        pin_limit: int = 50,
    ) -> dict:
        """
        Pull fresh analytics from Pinterest API for all published pins.
        Updates the database with latest performance data.
        """
        print(f"\n📡 Refreshing pin analytics (last {days_back} days)...")

        pins = self.db.get_pins(status="published", limit=pin_limit)
        if not pins:
            print("  ⚠️  No published pins found in database")
            return {"updated": 0, "errors": 0}

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        updated = 0
        errors = 0

        for pin in pins:
            pin_id = pin.get("id")
            if not pin_id or pin_id.startswith("dry_run"):
                continue

            try:
                analytics = self.pinterest.get_pin_analytics(
                    pin_id=pin_id,
                    start_date=start_date,
                    end_date=end_date,
                )

                # Extract metrics from response
                metrics = self._parse_pin_analytics(analytics)

                # Calculate performance score
                performance_score = self._calculate_performance_score(metrics)

                # Update database
                self.db.upsert_pin({
                    "id": pin_id,
                    "board_id": pin.get("board_id", ""),
                    "title": pin.get("title", ""),
                    "description": pin.get("description", ""),
                    "link": pin.get("link", ""),
                    "image_url": pin.get("image_url", ""),
                    "pin_type": pin.get("pin_type", "standard"),
                    "keyword_primary": pin.get("keyword_primary", ""),
                    "status": "published",
                    "published_at": pin.get("published_at", ""),
                    "created_at": pin.get("created_at", ""),
                    "impressions": metrics.get("impressions", pin.get("impressions", 0)),
                    "saves": metrics.get("saves", pin.get("saves", 0)),
                    "clicks": metrics.get("clicks", pin.get("clicks", 0)),
                    "outbound_clicks": metrics.get("outbound_clicks", pin.get("outbound_clicks", 0)),
                    "save_rate": metrics.get("save_rate", 0.0),
                    "click_rate": metrics.get("click_rate", 0.0),
                    "performance_score": performance_score,
                    "last_analytics_update": datetime.now().isoformat(),
                })
                updated += 1

            except PinterestAPIError as e:
                print(f"    ⚠️  Analytics error for pin {pin_id}: {e}")
                errors += 1

        print(f"  ✅ Updated {updated} pins | {errors} errors")
        return {"updated": updated, "errors": errors}

    def refresh_account_analytics(self, days_back: int = 7) -> dict:
        """Pull account-level analytics and save snapshot."""
        print(f"\n📊 Refreshing account analytics...")

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        try:
            account_analytics = self.pinterest.get_account_analytics(start_date, end_date)
            stats = self.db.get_summary_stats()

            # Calculate aggregates
            total_impressions = sum(
                v.get("IMPRESSION", {}).get("daily_metric_by_data_source", {}).get("ALL", {}).get("value", 0)
                for v in (account_analytics.get("all", {}).get("daily_metrics", []) or [])
            )

            snapshot = {
                "total_pins": stats["total_published_pins"],
                "total_boards": stats["active_boards"],
                "total_impressions": total_impressions or stats["total_impressions"],
                "total_saves": stats["total_saves"],
                "total_clicks": stats["total_clicks"],
                "total_outbound_clicks": 0,
                "avg_save_rate": 0.0,
                "avg_click_rate": 0.0,
                "top_pin_id": "",
                "top_board_id": "",
                "weekly_pin_count": len(self.db.get_pins(status="published", limit=20)),
                "notes": f"Auto-snapshot {end_date}",
            }
            self.db.save_analytics_snapshot(snapshot)
            print(f"  ✅ Account analytics snapshot saved")
            return snapshot

        except PinterestAPIError as e:
            print(f"  ⚠️  Could not retrieve account analytics: {e}")
            return {}

    # =========================================================
    # PERFORMANCE ANALYSIS
    # =========================================================
    def get_top_performers(
        self,
        metric: str = "saves",
        limit: int = 20,
    ) -> list[dict]:
        """Get top-performing pins by any metric."""
        return self.db.get_top_performing_pins(metric=metric, limit=limit)

    def identify_compounding_pins(self, min_age_days: int = 60) -> list[dict]:
        """
        Identify pins that are still generating traffic 60+ days after publishing.
        These are your evergreen compounding assets — make more variations of them.
        """
        cutoff_date = (datetime.now() - timedelta(days=min_age_days)).strftime("%Y-%m-%d")
        with self.db._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM pins
                WHERE status = 'published'
                AND published_at <= ?
                AND (saves > 5 OR outbound_clicks > 10)
                ORDER BY (saves + outbound_clicks) DESC
                LIMIT 20
            """, (cutoff_date,)).fetchall()
        return [dict(r) for r in rows]

    def identify_underperformers(
        self,
        min_age_days: int = 90,
        max_saves: int = 2,
    ) -> list[dict]:
        """Identify old pins with zero traction — candidates for refresh or deletion."""
        cutoff_date = (datetime.now() - timedelta(days=min_age_days)).strftime("%Y-%m-%d")
        with self.db._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM pins
                WHERE status = 'published'
                AND published_at <= ?
                AND saves <= ?
                AND outbound_clicks <= 5
                ORDER BY published_at ASC
                LIMIT 30
            """, (cutoff_date, max_saves)).fetchall()
        return [dict(r) for r in rows]

    def analyze_content_type_performance(self) -> dict:
        """Analyze which pin types generate the most saves and clicks."""
        with self.db._conn() as conn:
            rows = conn.execute("""
                SELECT
                    pin_type,
                    COUNT(*) as count,
                    AVG(saves) as avg_saves,
                    AVG(outbound_clicks) as avg_clicks,
                    AVG(impressions) as avg_impressions,
                    SUM(saves) as total_saves,
                    SUM(outbound_clicks) as total_clicks
                FROM pins
                WHERE status = 'published'
                GROUP BY pin_type
                ORDER BY avg_saves DESC
            """).fetchall()
        return {row["pin_type"]: dict(row) for row in rows}

    def analyze_keyword_performance(self) -> dict:
        """Analyze which keywords generate the most traffic and engagement."""
        with self.db._conn() as conn:
            rows = conn.execute("""
                SELECT
                    keyword_primary,
                    COUNT(*) as pin_count,
                    AVG(saves) as avg_saves,
                    AVG(outbound_clicks) as avg_clicks,
                    SUM(saves) as total_saves
                FROM pins
                WHERE status = 'published'
                AND keyword_primary != ''
                GROUP BY keyword_primary
                ORDER BY avg_saves DESC
                LIMIT 30
            """).fetchall()
        return [dict(r) for r in rows]

    def analyze_board_performance(self) -> list[dict]:
        """Analyze which boards generate the most engagement."""
        boards = self.db.get_boards()
        board_performance = []

        for board in boards:
            board_id = board.get("id")
            with self.db._conn() as conn:
                stats = conn.execute("""
                    SELECT
                        COUNT(*) as pin_count,
                        AVG(saves) as avg_saves,
                        AVG(outbound_clicks) as avg_clicks,
                        SUM(saves) as total_saves,
                        SUM(outbound_clicks) as total_clicks
                    FROM pins
                    WHERE board_id = ?
                    AND status = 'published'
                """, (board_id,)).fetchone()

            board_performance.append({
                **board,
                "pin_count": stats["pin_count"] or 0,
                "avg_saves": round(stats["avg_saves"] or 0, 2),
                "avg_clicks": round(stats["avg_clicks"] or 0, 2),
                "total_saves": stats["total_saves"] or 0,
                "total_clicks": stats["total_clicks"] or 0,
            })

        return sorted(board_performance, key=lambda x: x["avg_saves"], reverse=True)

    # =========================================================
    # SCORING
    # =========================================================
    def _calculate_performance_score(self, metrics: dict) -> float:
        """
        Calculate a composite performance score for a pin.
        Weighted: saves (40%) + outbound_clicks (40%) + impressions (20%)
        """
        saves = metrics.get("saves", 0)
        clicks = metrics.get("outbound_clicks", 0)
        impressions = metrics.get("impressions", 0)

        # Normalize (rough benchmarks)
        save_score = min(saves / 50, 1.0) * 10     # 50 saves = perfect save score
        click_score = min(clicks / 100, 1.0) * 10  # 100 clicks = perfect click score
        imp_score = min(impressions / 5000, 1.0) * 10  # 5000 impressions = perfect

        return round(
            save_score * 0.40 + click_score * 0.40 + imp_score * 0.20,
            2
        )

    def _parse_pin_analytics(self, analytics_response: dict) -> dict:
        """Parse Pinterest API analytics response into clean metrics dict."""
        metrics = {
            "impressions": 0,
            "saves": 0,
            "clicks": 0,
            "outbound_clicks": 0,
            "save_rate": 0.0,
            "click_rate": 0.0,
        }

        # Pinterest API v5 analytics structure
        all_data = analytics_response.get("all", {})
        daily_metrics = all_data.get("daily_metrics", [])

        for day in daily_metrics:
            metrics["impressions"] += day.get("IMPRESSION", 0)
            metrics["saves"] += day.get("SAVE", 0)
            metrics["clicks"] += day.get("PIN_CLICK", 0)
            metrics["outbound_clicks"] += day.get("OUTBOUND_CLICK", 0)

        if metrics["impressions"] > 0:
            metrics["save_rate"] = round(metrics["saves"] / metrics["impressions"] * 100, 3)
            metrics["click_rate"] = round(metrics["outbound_clicks"] / metrics["impressions"] * 100, 3)

        return metrics

    # =========================================================
    # REPORTING
    # =========================================================
    def generate_performance_report(
        self,
        days: int = 30,
        output_format: str = "text",
    ) -> str:
        """Generate a comprehensive performance report."""
        stats = self.db.get_summary_stats()
        top_pins = self.get_top_performers("saves", 5)
        type_performance = self.analyze_content_type_performance()
        board_performance = self.analyze_board_performance()[:5]
        keyword_performance = self.analyze_keyword_performance()[:10]
        compounding = self.identify_compounding_pins()
        underperformers = self.identify_underperformers()

        report = f"""
╔══════════════════════════════════════════════════════════════╗
║          PINTEREST PERFORMANCE REPORT — Last {days} Days          ║
║          Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}                      ║
╚══════════════════════════════════════════════════════════════╝

📊 ACCOUNT OVERVIEW:
  Published Pins:    {stats['total_published_pins']:>8,}
  Active Boards:     {stats['active_boards']:>8,}
  Total Saves:       {stats['total_saves']:>8,}
  Total Clicks:      {stats['total_clicks']:>8,}
  Total Impressions: {stats['total_impressions']:>8,}
  Queued Content:    {stats['queued_content']:>8,}

🏆 TOP 5 PINS BY SAVES:
"""
        for i, pin in enumerate(top_pins, 1):
            report += f"  {i}. {pin.get('title', 'N/A')[:45]:45} Saves: {pin.get('saves', 0):<6} Clicks: {pin.get('outbound_clicks', 0)}\n"

        report += "\n📌 PERFORMANCE BY PIN TYPE:\n"
        for pin_type, data in sorted(type_performance.items(), key=lambda x: x[1].get("avg_saves", 0), reverse=True):
            report += f"  {pin_type:<20} Avg Saves: {data.get('avg_saves', 0):.1f}  Avg Clicks: {data.get('avg_clicks', 0):.1f}  Count: {data.get('count', 0)}\n"

        report += "\n🗂️  TOP 5 BOARDS BY SAVES:\n"
        for board in board_performance:
            report += f"  {board.get('name', 'N/A')[:35]:35} Saves: {board.get('total_saves', 0):<8} Clicks: {board.get('total_clicks', 0)}\n"

        report += "\n🔑 TOP KEYWORDS BY PERFORMANCE:\n"
        for kw in keyword_performance[:5]:
            report += f"  {kw.get('keyword_primary', 'N/A'):<40} Avg Saves: {kw.get('avg_saves', 0):.1f}  Total: {kw.get('total_saves', 0)}\n"

        report += f"\n♻️  COMPOUNDING PINS (60+ days old, still generating traffic): {len(compounding)}\n"
        for pin in compounding[:3]:
            report += f"  → {pin.get('title', 'N/A')[:50]} | Published: {pin.get('published_at', 'N/A')[:10]} | Saves: {pin.get('saves', 0)}\n"

        report += f"\n⚠️  UNDERPERFORMERS (90+ days, <2 saves): {len(underperformers)} pins\n"
        report += "  → Consider refreshing or creating new variations of these\n"

        report += """
🎯 RECOMMENDED ACTIONS:
"""
        actions = self._generate_action_recommendations(stats, top_pins, type_performance, compounding, underperformers)
        for action in actions:
            report += f"  {action}\n"

        return report

    def _generate_action_recommendations(
        self,
        stats: dict,
        top_pins: list,
        type_perf: dict,
        compounding: list,
        underperformers: list,
    ) -> list[str]:
        """Generate actionable recommendations based on analytics data."""
        actions = []

        # Low pin count
        if stats["total_published_pins"] < 50:
            actions.append("🚀 Publish at least 50 total pins to build critical mass")

        # Compounding pins need more variations
        if compounding:
            actions.append(f"♻️  Create 5 fresh variations of your {len(compounding)} compounding pins — they're proven winners")

        # Underperformers
        if len(underperformers) > 10:
            actions.append(f"🗑️  Review {len(underperformers)} underperforming pins — update titles or delete")

        # Best pin type
        if type_perf:
            best_type = max(type_perf.items(), key=lambda x: x[1].get("avg_saves", 0))
            actions.append(f"📌 '{best_type[0]}' pins perform best — increase this type's share of your queue")

        # Queue health
        if stats["queued_content"] < 15:
            actions.append("⚠️  Queue under 15 pins — run content generation to maintain publishing cadence")

        if not actions:
            actions.append("✅ Performance looks healthy — focus on consistency and seasonal content")

        return actions

    def export_report_json(self) -> dict:
        """Export full analytics as JSON for dashboard consumption."""
        return {
            "generated_at": datetime.now().isoformat(),
            "summary": self.db.get_summary_stats(),
            "top_pins": [
                {k: v for k, v in pin.items() if k in ["id", "title", "saves", "outbound_clicks", "impressions", "performance_score"]}
                for pin in self.get_top_performers("saves", 10)
            ],
            "board_performance": self.analyze_board_performance(),
            "content_type_performance": self.analyze_content_type_performance(),
            "keyword_performance": self.analyze_keyword_performance()[:20],
            "compounding_pins": len(self.identify_compounding_pins()),
            "underperformers": len(self.identify_underperformers()),
            "history": self.db.get_analytics_history(30),
        }
