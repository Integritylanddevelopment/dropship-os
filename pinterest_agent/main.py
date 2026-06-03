#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║     PINTEREST AI AGENT — ENTERPRISE EDITION          ║
║     Drop Shipping Organic Growth System              ║
║     ─────────────────────────────────────────────── ║
║     Built for: Alex Alexander                        ║
║     Strategy: Gary V Content Volume + SEO Search     ║
╚══════════════════════════════════════════════════════╝

USAGE:
  python main.py setup                     # First-time setup
  python main.py research                  # Run keyword research
  python main.py content                   # Generate pin content
  python main.py boards                    # Manage board structure
  python main.py boards --dry-run          # Preview board changes
  python main.py publish --count 15        # Publish 15 pins
  python main.py publish --dry-run         # Preview publishing
  python main.py analytics                 # Performance report
  python main.py seasonal                  # Seasonal planning
  python main.py score                     # Score opportunities
  python main.py full-cycle                # Run everything
  python main.py dashboard                 # Launch web dashboard
"""
import argparse
import sys
from config import load_config
from orchestrator import PinterestOrchestrator


def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║   📌 PINTEREST AI AGENT  |  Drop Shipping System     ║
╚══════════════════════════════════════════════════════╝
    """)


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        prog="pinterest-agent",
        description="Pinterest AI Agent — Enterprise Drop Shipping Growth System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Agent command to run")

    # Setup command
    subparsers.add_parser("setup", help="First-time setup: test connections, seed data, build boards")

    # Research command
    research_p = subparsers.add_parser("research", help="Run keyword and market research")
    research_p.add_argument("--niche", type=str, help="Niche to research (overrides config)")
    research_p.add_argument("--keywords", type=str, help="Comma-separated seed keywords")

    # Content command
    content_p = subparsers.add_parser("content", help="Generate pin content and fill the queue")
    content_p.add_argument("--niche", type=str, help="Niche for content generation")
    content_p.add_argument("--count", type=int, default=15, help="Number of pins to generate")

    # Boards command
    boards_p = subparsers.add_parser("boards", help="Create and optimize board structure")
    boards_p.add_argument("--dry-run", action="store_true", help="Preview changes without executing")

    # Publish command
    publish_p = subparsers.add_parser("publish", help="Publish queued pins to Pinterest")
    publish_p.add_argument("--board", type=str, help="Filter by board ID")
    publish_p.add_argument("--count", type=int, default=10, help="Max pins to publish")
    publish_p.add_argument("--dry-run", action="store_true", help="Preview without publishing")
    publish_p.add_argument("--image-url", type=str, help="Default image URL for pins without images")

    # Analytics command
    analytics_p = subparsers.add_parser("analytics", help="Pull analytics and generate report")
    analytics_p.add_argument("--output", type=str, choices=["text", "json"], default="text")

    # Seasonal command
    subparsers.add_parser("seasonal", help="Build seasonal content calendar and generate content")

    # Score command
    score_p = subparsers.add_parser("score", help="Score content opportunities")
    score_p.add_argument("--niche", type=str, help="Niche to score")

    # Full cycle command
    full_p = subparsers.add_parser("full-cycle", help="Run the complete research→publish→analyze cycle")
    full_p.add_argument("--niche", type=str, help="Niche override")
    full_p.add_argument("--dry-run", action="store_true", help="Preview all actions")

    # Dashboard command
    subparsers.add_parser("dashboard", help="Launch web dashboard")

    # Parse args
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n💡 Quick start: python main.py setup")
        sys.exit(0)

    args = parser.parse_args()

    # Load config and initialize agent
    config = load_config()
    agent = PinterestOrchestrator(config)

    # Route to command
    try:
        if args.command == "setup":
            agent.run_setup()

        elif args.command == "research":
            agent.run_research(
                niche=getattr(args, "niche", None),
                keywords=getattr(args, "keywords", None),
            )

        elif args.command == "content":
            agent.run_content_generation(
                niche=getattr(args, "niche", None),
                count=getattr(args, "count", 15),
            )

        elif args.command == "boards":
            agent.run_board_management(
                dry_run=getattr(args, "dry_run", False),
            )

        elif args.command == "publish":
            agent.run_publishing(
                board_id=getattr(args, "board", None),
                count=getattr(args, "count", 10),
                dry_run=getattr(args, "dry_run", False),
                image_url_default=getattr(args, "image_url", None),
            )

        elif args.command == "analytics":
            agent.run_analytics(
                output=getattr(args, "output", "text"),
            )

        elif args.command == "seasonal":
            agent.run_seasonal_planning()

        elif args.command == "score":
            agent.run_opportunity_scoring(
                niche=getattr(args, "niche", None),
            )

        elif args.command == "full-cycle":
            agent.run_full_cycle(
                niche=getattr(args, "niche", None),
                dry_run=getattr(args, "dry_run", False),
            )

        elif args.command == "dashboard":
            agent.launch_dashboard()

        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\n\n⛔ Agent stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Agent error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
