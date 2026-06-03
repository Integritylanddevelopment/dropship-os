"""
Pinterest AI Agent — Master Orchestrator
The brain of the operation. Coordinates all sub-agents to execute the
complete Pinterest organic growth strategy for drop shipping.
"""
import json
import sys
import time
import threading
import http.server
import webbrowser
from datetime import datetime
from pathlib import Path
from config import PinterestConfig
from database import Database
from integrations.pinterest_api import PinterestAPI, PinterestAPIError
from integrations.claude_client import ClaudeClient
from agents.research_agent import ResearchAgent
from agents.content_agent import ContentAgent
from agents.publishing_agent import PublishingAgent
from agents.analytics_agent import AnalyticsAgent


class PinterestOrchestrator:
    """
    Master Pinterest AI Agent.

    Coordinates research → content → boards → publishing → analytics → optimize
    in one unified system that finds the cheapest attention for the highest-margin products.
    """

    DEFAULT_SEED_KEYWORDS = [
        "home organization ideas",
        "kitchen gadgets",
        "gift ideas for women",
        "bedroom decor",
        "useful products",
        "home gym equipment",
        "cozy home decor",
        "bathroom organization",
        "morning routine products",
        "under $50 finds",
    ]

    DEFAULT_OPPORTUNITIES = [
        {"topic": "Home Organization Products", "context": "Storage solutions for small spaces"},
        {"topic": "Kitchen Gadgets Under $30", "context": "Problem-solving kitchen tools"},
        {"topic": "Gift Ideas for Women", "context": "Unique thoughtful gifts for any occasion"},
        {"topic": "Home Gym Equipment", "context": "Affordable fitness equipment for small spaces"},
        {"topic": "Bedroom Aesthetic Products", "context": "Decor for trendy room aesthetics"},
        {"topic": "Bathroom Organization Solutions", "context": "Under sink and small bathroom storage"},
        {"topic": "Cozy Home Products", "context": "Lifestyle products for warm, inviting spaces"},
        {"topic": "Problem-Solution Gadgets", "context": "Products that solve everyday annoyances"},
        {"topic": "Outdoor Patio Products", "context": "Backyard and balcony entertaining"},
        {"topic": "Lead Magnet — Home Buyer's Guide", "context": "Free guide to capture email leads"},
    ]

    def __init__(self, config: PinterestConfig):
        self.config = config
        self.db = Database(config.db_path)

        # Initialize integrations
        self.pinterest = PinterestAPI(config.pinterest_access_token)
        self.claude = ClaudeClient(config.anthropic_api_key)

        # Initialize agents
        self.research = ResearchAgent(self.pinterest, self.claude, self.db)
        self.content = ContentAgent(self.claude, self.db)
        self.publisher = PublishingAgent(self.pinterest, self.db)
        self.analytics = AnalyticsAgent(self.pinterest, self.db)

        print(f"""
╔══════════════════════════════════════════════════════╗
║     🎯 PINTEREST AI AGENT — ENTERPRISE EDITION       ║
║     Drop Shipping Growth System                      ║
║     Business: {config.business_name[:35]:35} ║
║     Niche:    {config.primary_niche[:35]:35} ║
╚══════════════════════════════════════════════════════╝
        """)

    # =========================================================
    # SETUP
    # =========================================================
    def run_setup(self):
        """
        Full account setup: test connection, sync boards, seed keywords,
        generate initial board structure, build seasonal calendar.
        """
        print("\n🔧 Running initial setup...")

        # Step 1: Test Pinterest API
        print("\n[1/6] Testing Pinterest API connection...")
        if self.config.pinterest_access_token:
            connected = self.pinterest.test_connection()
        else:
            print("  ⚠️  No Pinterest access token — running in content-generation mode only")
            connected = False

        # Step 2: Test Claude API
        print("\n[2/6] Testing Claude AI connection...")
        try:
            test = self.claude._call("Say 'Pinterest Agent Ready' in 3 words or less", max_tokens=20)
            print(f"  ✅ Claude API connected: {test}")
        except Exception as e:
            print(f"  ❌ Claude API error: {e}")
            print("  → Check ANTHROPIC_API_KEY in your .env file")
            return

        # Step 3: Sync existing boards from Pinterest
        if connected:
            print("\n[3/6] Syncing boards from Pinterest...")
            self.publisher.sync_boards_from_pinterest()
        else:
            print("\n[3/6] Skipped board sync (no API connection)")

        # Step 4: Generate board structure recommendation
        print("\n[4/6] Generating board structure...")
        boards = self.content.generate_board_structure(
            niche=self.config.primary_niche,
            website_url=self.config.website_url,
            num_boards=12,
        )
        print(f"  Generated {len(boards)} recommended boards")

        # Step 5: Seed keyword database
        print("\n[5/6] Seeding keyword database...")
        self.research.discover_keywords(
            seed_keywords=self.DEFAULT_SEED_KEYWORDS[:5],  # Start with 5 to avoid API cost
            niche=self.config.primary_niche,
        )

        # Step 6: Build seasonal calendar
        print("\n[6/6] Building seasonal content calendar...")
        self.research.build_seasonal_calendar(
            niche=self.config.primary_niche,
            year=datetime.now().year,
        )

        print("""
╔══════════════════════════════════════════════╗
║  ✅ SETUP COMPLETE                           ║
╠══════════════════════════════════════════════╣
║  Next Steps:                                 ║
║  1. Run: python main.py boards               ║
║  2. Run: python main.py content              ║
║  3. Run: python main.py publish --dry-run    ║
║  4. Run: python main.py dashboard            ║
╚══════════════════════════════════════════════╝
        """)

    # =========================================================
    # RESEARCH
    # =========================================================
    def run_research(self, niche: str = None, keywords: str = None):
        """Run the full research cycle: keywords, opportunities, seasonal."""
        target_niche = niche or self.config.primary_niche
        seed_kws = keywords.split(",") if keywords else self.DEFAULT_SEED_KEYWORDS

        print(f"\n🔍 RESEARCH CYCLE — {target_niche}")

        # Keyword discovery
        print("\n[Phase 1] Keyword Discovery")
        discovered = self.research.discover_keywords(seed_kws[:5], target_niche)

        # Opportunity scoring
        print("\n[Phase 2] Opportunity Scoring")
        scored = self.research.score_opportunities(
            self.DEFAULT_OPPORTUNITIES,
            niche=target_niche,
        )

        # Seasonal priorities
        print("\n[Phase 3] Seasonal Intelligence")
        upcoming = self.research.get_upcoming_priorities(days_ahead=60)

        # Print research report
        report = self.research.generate_research_report(target_niche)
        print(report)

        # Save report to file
        report_path = f"research_report_{datetime.now().strftime('%Y%m%d')}.txt"
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\n📄 Report saved to: {report_path}")

    # =========================================================
    # CONTENT GENERATION
    # =========================================================
    def run_content_generation(
        self,
        niche: str = None,
        count: int = 10,
        product_list: list[dict] = None,
    ):
        """Generate content: pins, boards, lead magnets for the queue."""
        target_niche = niche or self.config.primary_niche
        boards = self.db.get_boards()

        print(f"\n✍️  CONTENT GENERATION CYCLE — {target_niche}")

        if not product_list:
            # Use example products — replace with your actual product catalog
            product_list = [
                {
                    "name": "Bamboo Kitchen Drawer Organizer",
                    "description": "Expandable bamboo drawer organizer with adjustable dividers for utensils, tools, and kitchen accessories. Fits most standard drawer sizes.",
                    "url": f"{self.config.website_url}/products/bamboo-drawer-organizer",
                    "keyword": "kitchen drawer organizer",
                    "niche": "kitchen organization",
                },
                {
                    "name": "Under-Desk Cable Management Box",
                    "description": "Hide all cords and power strips under your desk with this sleek cable management box. Works for home office, gaming setup, and entertainment centers.",
                    "url": f"{self.config.website_url}/products/cable-management-box",
                    "keyword": "desk cable organizer",
                    "niche": "home office organization",
                },
                {
                    "name": "Adjustable Resistance Band Set",
                    "description": "5-piece resistance band set with door anchor, handles, and ankle straps. Full-body workout at home with 10-50 lbs resistance levels.",
                    "url": f"{self.config.website_url}/products/resistance-band-set",
                    "keyword": "resistance bands home workout",
                    "niche": "home fitness",
                },
            ]

        # Generate pins for each product
        for product in product_list[:3]:  # Limit to 3 products per run
            board_id = ""
            board_name = ""
            # Find best matching board
            for board in boards:
                if any(word in board.get("name", "").lower()
                       for word in product.get("niche", "").lower().split()):
                    board_id = board.get("id", "")
                    board_name = board.get("name", "")
                    break

            self.content.generate_pin_batch(
                product_name=product["name"],
                product_description=product["description"],
                target_url=product["url"],
                primary_keyword=product["keyword"],
                niche=target_niche,
                pin_count=min(count // len(product_list), 5),
                board_id=board_id,
                board_name=board_name,
            )

        # Generate weekly plan
        print("\n[Content Phase 2] Generating weekly plan...")
        keywords = [kw["keyword"] for kw in self.db.get_keywords(limit=10)]
        if not keywords:
            keywords = self.DEFAULT_SEED_KEYWORDS[:5]

        weekly_plan = self.content.generate_weekly_plan(
            niche=target_niche,
            boards=boards,
            keywords=keywords,
            pin_count=15,
        )

        # Generate lead magnet
        print("\n[Content Phase 3] Generating lead magnet...")
        lead_magnet = self.content.generate_lead_magnet(
            niche=target_niche,
            audience="home and lifestyle shoppers who want to upgrade their space on a budget",
            product_category="home organization and lifestyle products",
        )
        print(f"  Lead Magnet: {lead_magnet.get('name', 'Generated')}")
        print(f"  Type: {lead_magnet.get('type', 'N/A')}")
        print(f"  Product Bridge: {lead_magnet.get('product_bridge', 'N/A')[:80]}")

        # Queue summary
        queue_summary = self.content.get_queue_summary()
        print(f"""
╔══════════════════════════════════════════════╗
║  ✅ CONTENT GENERATION COMPLETE              ║
╠══════════════════════════════════════════════╣
║  Total Queued:    {queue_summary['total_queued']:>5} pins               ║
║  Ready to Publish: {len(queue_summary.get('ready_to_publish', [])):>4} pins               ║
╚══════════════════════════════════════════════╝
        """)

    # =========================================================
    # BOARD MANAGEMENT
    # =========================================================
    def run_board_management(self, dry_run: bool = False):
        """Create, sync, and optimize all boards."""
        print(f"\n🗂️  BOARD MANAGEMENT CYCLE {'(DRY RUN)' if dry_run else ''}")

        # Sync existing boards
        print("\n[1/3] Syncing existing boards from Pinterest...")
        if self.config.pinterest_access_token:
            self.publisher.sync_boards_from_pinterest()

        # Get planned boards from database
        planned_boards = self.db.get_boards(status="planned")
        print(f"\n[2/3] Creating {len(planned_boards)} planned boards...")

        if planned_boards and not dry_run:
            for board in planned_boards:
                result = self.publisher.create_board(
                    name=board["name"],
                    description=board["description"],
                    keyword_cluster=board.get("keyword_cluster", ""),
                    priority=board.get("priority", 5),
                    dry_run=dry_run,
                )
                if result and not dry_run:
                    # Update status from planned to active
                    with self.db._conn() as conn:
                        conn.execute(
                            "UPDATE boards SET status='active', id=? WHERE id=?",
                            (result["id"], board["id"])
                        )
                time.sleep(0.5)
        elif planned_boards and dry_run:
            for board in planned_boards:
                print(f"  [DRY RUN] Would create: {board['name']}")

        # Print board audit
        print("\n[3/3] Board audit...")
        all_boards = self.db.get_boards()
        print(f"\n  Active boards: {len(all_boards)}")
        for board in all_boards[:10]:
            desc_len = len(board.get("description", ""))
            status = "✅" if desc_len > 50 else "⚠️"
            print(f"  {status} {board['name'][:40]:40} | Desc: {desc_len} chars | Pins: {board.get('pin_count', 0)}")

        # Repurpose top performers
        print("\n[Bonus] Repurposing top-performing pins...")
        self.content.repurpose_top_performers(top_count=5, variations_per_pin=3)

    # =========================================================
    # PUBLISHING
    # =========================================================
    def run_publishing(
        self,
        board_id: str = None,
        count: int = 10,
        dry_run: bool = False,
        image_url_default: str = None,
    ):
        """Publish queued pins to Pinterest."""
        print(f"\n🚀 PUBLISHING CYCLE {'(DRY RUN)' if dry_run else ''}")

        # Get publish status
        status = self.publisher.get_publish_status()
        print(f"\n  Queue status:")
        print(f"  → Total queued:     {status['queued_total']}")
        print(f"  → Ready to publish: {status['ready_to_publish']}")
        print(f"  → Needs completion: {status['needs_completion']}")

        if status["recommendations"]:
            print("\n  Recommendations:")
            for rec in status["recommendations"]:
                print(f"    {rec}")

        if status["ready_to_publish"] == 0:
            print("\n  ⚠️  No pins ready to publish.")
            print("  → Run: python main.py content to generate content")
            print("  → Then add image URLs and target URLs to queued pins")
            return

        # Publish from queue
        result = self.publisher.publish_from_queue(
            max_pins=count,
            board_id_filter=board_id,
            dry_run=dry_run,
            image_url_default=image_url_default,
        )

        print(f"""
╔══════════════════════════════════════════════╗
║  ✅ PUBLISHING COMPLETE                      ║
╠══════════════════════════════════════════════╣
║  Published: {result['published']:>5}                         ║
║  Failed:    {result['failed']:>5}                         ║
║  Skipped:   {result['skipped']:>5}                         ║
╚══════════════════════════════════════════════╝
        """)

    # =========================================================
    # ANALYTICS
    # =========================================================
    def run_analytics(self, output: str = "text"):
        """Pull analytics and generate performance report."""
        print("\n📊 ANALYTICS CYCLE")

        # Refresh analytics from Pinterest
        print("\n[1/2] Pulling fresh analytics from Pinterest...")
        self.analytics.refresh_pin_analytics(days_back=30)
        self.analytics.refresh_account_analytics(days_back=7)

        # Generate report
        print("\n[2/2] Generating performance report...")
        if output == "json":
            data = self.analytics.export_report_json()
            report_path = f"analytics_{datetime.now().strftime('%Y%m%d')}.json"
            with open(report_path, "w") as f:
                json.dump(data, f, indent=2)
            print(f"  📄 JSON report saved to: {report_path}")
        else:
            report = self.analytics.generate_performance_report()
            print(report)
            report_path = f"analytics_{datetime.now().strftime('%Y%m%d')}.txt"
            with open(report_path, "w") as f:
                f.write(report)
            print(f"\n  📄 Report saved to: {report_path}")

    # =========================================================
    # SEASONAL PLANNING
    # =========================================================
    def run_seasonal_planning(self):
        """Build and display the seasonal content calendar."""
        print("\n📅 SEASONAL PLANNING CYCLE")

        # Rebuild calendar
        calendar = self.research.build_seasonal_calendar(
            niche=self.config.primary_niche,
        )

        # Show upcoming priorities
        upcoming = self.research.get_upcoming_priorities(days_ahead=90)

        print(f"\n📅 SEASONAL CALENDAR — Next 90 Days:")
        print(f"{'Event':<30} {'Target Date':<15} {'Publish By':<15} {'Lead Days'}")
        print("-" * 70)
        for event in upcoming:
            print(f"{event.get('event', ''):<30} {event.get('target_date', ''):<15} {event.get('publish_by', ''):<15} {event.get('lead_days', 45)}")

        # Generate pins for upcoming seasonal events
        if upcoming:
            print(f"\n⚡ Generating seasonal content for next event: {upcoming[0].get('event', '')}")
            self.run_content_generation(niche=f"{self.config.primary_niche} {upcoming[0].get('event', '')}")

    # =========================================================
    # OPPORTUNITY SCORING
    # =========================================================
    def run_opportunity_scoring(self, niche: str = None):
        """Score all current opportunities and display ranking."""
        target_niche = niche or self.config.primary_niche
        print(f"\n📊 OPPORTUNITY SCORING — {target_niche}")

        scored = self.research.score_opportunities(
            self.DEFAULT_OPPORTUNITIES,
            niche=target_niche,
        )

        print(f"\n{'Rank':<5} {'Topic':<40} {'Score':<7} {'Buyer Intent':<14} {'Action'}")
        print("-" * 100)
        for opp in scored:
            print(
                f"  {opp.get('priority_rank', '-'):<4} "
                f"{opp.get('topic', ''):<40} "
                f"{opp.get('overall_score', 0):.1f}    "
                f"{opp.get('buyer_intent', 0)}/10         "
                f"{opp.get('recommended_action', '')[:40]}"
            )

        # Show fast wins
        fast_wins = self.research.identify_fast_wins(target_niche)
        if fast_wins:
            print(f"\n⚡ FAST WINS ({len(fast_wins)} identified):")
            for fw in fast_wins:
                print(f"  → {fw.get('topic', '')}: {fw.get('recommended_action', '')}")

    # =========================================================
    # FULL CYCLE
    # =========================================================
    def run_full_cycle(self, niche: str = None, dry_run: bool = False):
        """
        Execute the complete Pinterest growth cycle:
        Research → Content → Boards → Publish → Analytics → Optimize
        """
        target_niche = niche or self.config.primary_niche
        print(f"""
╔══════════════════════════════════════════════════════╗
║  🔄 FULL PINTEREST GROWTH CYCLE                      ║
║  Niche: {target_niche[:45]:45} ║
║  Mode: {'DRY RUN' if dry_run else 'LIVE   '}                                       ║
╚══════════════════════════════════════════════════════╝
        """)

        start_time = time.time()

        # Phase 1: Research
        print("\n" + "="*60)
        print("  PHASE 1: RESEARCH")
        print("="*60)
        self.run_research(niche=target_niche)

        # Phase 2: Boards
        print("\n" + "="*60)
        print("  PHASE 2: BOARD MANAGEMENT")
        print("="*60)
        self.run_board_management(dry_run=dry_run)

        # Phase 3: Content
        print("\n" + "="*60)
        print("  PHASE 3: CONTENT GENERATION")
        print("="*60)
        self.run_content_generation(niche=target_niche)

        # Phase 4: Publish
        print("\n" + "="*60)
        print("  PHASE 4: PUBLISHING")
        print("="*60)
        self.run_publishing(count=15, dry_run=dry_run)

        # Phase 5: Analytics
        print("\n" + "="*60)
        print("  PHASE 5: ANALYTICS")
        print("="*60)
        self.run_analytics()

        # Phase 6: Seasonal
        print("\n" + "="*60)
        print("  PHASE 6: SEASONAL PLANNING")
        print("="*60)
        self.run_seasonal_planning()

        elapsed = time.time() - start_time
        print(f"""
╔══════════════════════════════════════════════════════╗
║  ✅ FULL CYCLE COMPLETE                              ║
║  Time elapsed: {elapsed:.0f}s                                  ║
║  Next cycle: Run again in 7 days                     ║
╚══════════════════════════════════════════════════════╝
        """)

    # =========================================================
    # DASHBOARD
    # =========================================================
    def launch_dashboard(self):
        """Launch the web dashboard for monitoring and control."""
        dashboard_path = Path(__file__).parent / "dashboard" / "index.html"

        if not dashboard_path.exists():
            print("  ⚠️  Dashboard file not found at dashboard/index.html")
            return

        # Generate fresh analytics data for dashboard
        print("\n📊 Preparing dashboard data...")
        analytics_data = self.analytics.export_report_json()
        data_path = Path(__file__).parent / "dashboard" / "data.json"
        with open(data_path, "w") as f:
            json.dump(analytics_data, f, indent=2)

        # Serve dashboard
        port = self.config.dashboard_port
        dashboard_dir = str(Path(__file__).parent / "dashboard")

        print(f"\n🌐 Launching dashboard at: http://localhost:{port}")
        print("   Press Ctrl+C to stop\n")

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=dashboard_dir, **kwargs)
            def log_message(self, format, *args):
                pass  # Suppress server logs

        try:
            with http.server.HTTPServer(("", port), Handler) as httpd:
                webbrowser.open(f"http://localhost:{port}")
                httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Dashboard stopped.")
