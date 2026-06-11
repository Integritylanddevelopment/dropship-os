#!/usr/bin/env python3
"""
main.py — Social AI Agent Command Center
Reddit + Pinterest organic growth, fully automated.

Usage:
  python main.py setup           # First-time setup for both platforms
  python main.py reddit          # Run Reddit agent
  python main.py pinterest       # Run Pinterest agent
  python main.py schedule        # Start automated scheduler
  python main.py research        # Run market research
  python main.py dashboard       # View stats and plan
  python main.py config          # Check configuration status
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from rich.text import Text
from rich.columns import Columns

console = Console()

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))
from config import config
from storage import db
from agents.reddit_agent import RedditAgent
from agents.pinterest_agent import PinterestAgent
from scheduler.task_scheduler import AgentScheduler


# ─────────────────────────────────────────────
# BANNER
# ─────────────────────────────────────────────

def print_banner():
    console.print(Panel.fit(
        "[bold cyan]Social AI Agent[/bold cyan]\n"
        "[dim]Reddit + Pinterest Organic Growth System[/dim]\n"
        f"[dim]Niche: {config.niche} | Business: {config.business_name}[/dim]",
        border_style="cyan"
    ))


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

@click.group()
def cli():
    """Social AI Agent — Reddit + Pinterest Organic Growth"""
    pass


@cli.command()
@click.option("--niche", default=None, help="Override niche (e.g. dropshipping, fitness)")
@click.option("--platform", type=click.Choice(["reddit", "pinterest", "both"]), default="both")
def setup(niche: str, platform: str):
    """First-time setup: discover subreddits, build keyword strategy, generate 30-day plan"""
    print_banner()

    async def _run():
        results = {}

        if platform in ["reddit", "both"]:
            console.print("\n[bold green]🔴 Setting up Reddit Agent...[/bold green]")
            agent = RedditAgent()
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
                task = progress.add_task("Running Reddit setup...", total=None)
                result = await agent.setup(niche_override=niche)
                progress.update(task, completed=True)
            results["reddit"] = result

            # Display subreddit tier report
            if result.get("subreddits"):
                table = Table(title="Top Subreddits Found", border_style="red")
                table.add_column("Subreddit", style="cyan")
                table.add_column("Score", justify="right")
                table.add_column("Tier")
                table.add_column("Best For")

                for sub in result["subreddits"][:10]:
                    name = sub.get("subreddit", sub.get("name", "?"))
                    score = str(sub.get("scores", {}).get("overall", "?"))
                    tier = sub.get("tier", "?")
                    best = sub.get("recommended_approach", "")[:40]
                    table.add_row(f"r/{name}", score, tier, best)

                console.print(table)

        if platform in ["pinterest", "both"]:
            console.print("\n[bold magenta]📌 Setting up Pinterest Agent...[/bold magenta]")
            agent = PinterestAgent()
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
                task = progress.add_task("Running Pinterest setup...", total=None)
                result = await agent.setup(niche_override=niche)
                progress.update(task, completed=True)
            results["pinterest"] = result

            # Display board strategy
            boards = result.get("board_strategy", {}).get("boards", [])
            if boards:
                table = Table(title="Pinterest Boards to Create", border_style="magenta")
                table.add_column("#", justify="right")
                table.add_column("Board Name", style="cyan")
                table.add_column("Type")
                table.add_column("Primary Keyword")

                for i, board in enumerate(boards[:15], 1):
                    table.add_row(
                        str(i),
                        board.get("name", ""),
                        board.get("board_type", ""),
                        board.get("primary_keyword", ""),
                    )
                console.print(table)

        # Save full setup results
        output_path = Path(__file__).parent / "data" / "setup_results.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        console.print(f"\n[green]✅ Setup complete. Results saved to: {output_path}[/green]")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. Review your subreddit list and board strategy above")
        console.print("  2. Run [cyan]python main.py reddit session[/cyan] to start your first Reddit session")
        console.print("  3. Run [cyan]python main.py pinterest daily[/cyan] to generate and queue your first pins")
        console.print("  4. Run [cyan]python main.py schedule[/cyan] to automate everything")

    asyncio.run(_run())


@cli.group()
def reddit():
    """Reddit agent commands"""
    pass


@reddit.command(name="session")
@click.option("--phase", type=click.Choice(["warmup", "active"]), default="warmup")
@click.option("--auto", is_flag=True, help="Actually post (requires login). Without this flag, dry-run only.")
def reddit_session(phase: str, auto: bool):
    """Run a Reddit session (comment + post based on phase)"""
    print_banner()

    async def _run():
        agent = RedditAgent(auto_mode=auto)
        console.print(f"\n[red]Running Reddit {phase} session (auto={auto})[/red]")

        if not auto:
            console.print("[yellow]DRY RUN — Content will be generated but NOT posted.[/yellow]")
            console.print("[yellow]Add --auto flag to actually post.[/yellow]\n")

        with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:
            task = progress.add_task(f"Running {phase} session...", total=None)
            if phase == "warmup":
                result = await agent.run_warmup_session()
            else:
                result = await agent.run_active_session()
            progress.update(task, completed=True)

        console.print(f"\n[green]Session complete:[/green]")
        console.print(f"  Comments: {result.get('comments_made', 0)}")
        console.print(f"  Posts: {result.get('posts_made', 0)}")

        if result.get("content_generated"):
            table = Table(title="Content Generated", border_style="red")
            table.add_column("Type")
            table.add_column("Subreddit")
            table.add_column("Preview")
            for item in result["content_generated"][:10]:
                table.add_row(
                    item.get("type", ""),
                    item.get("subreddit", ""),
                    (item.get("title") or item.get("comment_preview") or "")[:60],
                )
            console.print(table)

    asyncio.run(_run())


@reddit.command(name="plan")
def reddit_plan():
    """Generate a 7-day Reddit execution plan"""
    async def _run():
        agent = RedditAgent()
        plan = await agent.generate_weekly_plan()
        console.print_json(json.dumps(plan, indent=2, default=str))

    asyncio.run(_run())


@reddit.command(name="discover")
@click.option("--max", default=20, help="Max subreddits to analyze")
def reddit_discover(max: int):
    """Discover and score subreddits for your niche"""
    print_banner()

    async def _run():
        from research.subreddit_analyzer import SubredditAnalyzer
        analyzer = SubredditAnalyzer()

        console.print(f"\n[red]Discovering subreddits for: {config.niche}[/red]")
        with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:
            task = progress.add_task(f"Analyzing up to {max} subreddits...", total=None)
            results = await analyzer.run_full_discovery(max_subreddits=max)
            progress.update(task, completed=True)

        table = Table(title=f"Subreddit Rankings — {config.niche}", border_style="red")
        table.add_column("Rank", justify="right")
        table.add_column("Subreddit", style="cyan")
        table.add_column("Overall Score", justify="right")
        table.add_column("Audience")
        table.add_column("Lead Potential")
        table.add_column("Tier")

        for i, sub in enumerate(results[:15], 1):
            scores = sub.get("scores", {})
            table.add_row(
                str(i),
                f"r/{sub.get('subreddit', sub.get('name', '?'))}",
                str(scores.get("overall", "?")),
                str(scores.get("audience_quality", "?")),
                str(scores.get("lead_potential", "?")),
                sub.get("tier", "?"),
            )

        console.print(table)

    asyncio.run(_run())


@reddit.command(name="research")
@click.argument("subreddit")
def reddit_research(subreddit: str):
    """Deep market research on a subreddit"""
    async def _run():
        from research.market_research import MarketResearchEngine
        researcher = MarketResearchEngine()
        console.print(f"\n[red]Researching r/{subreddit}...[/red]")
        result = await researcher.research_subreddit(subreddit)
        intel = result.get("intelligence", {})
        console.print(f"\n[bold]Pain Points:[/bold]")
        for p in intel.get("pain_points", [])[:5]:
            console.print(f"  • {p.get('pain', p) if isinstance(p, dict) else p}")
        console.print(f"\n[bold]Customer Language:[/bold]")
        for l in intel.get("customer_language", [])[:8]:
            console.print(f"  • {l}")
        console.print(f"\n[bold]Ad Copy Hooks:[/bold]")
        for h in intel.get("ad_copy_hooks", [])[:5]:
            console.print(f"  • {h}")

    asyncio.run(_run())


# ─────────────────────────────────────────────
# PINTEREST COMMANDS
# ─────────────────────────────────────────────

@cli.group()
def pinterest():
    """Pinterest agent commands"""
    pass


@pinterest.command(name="daily")
@click.option("--pins", default=15, help="Number of pins to generate")
@click.option("--auto", is_flag=True, help="Actually publish pins")
def pinterest_daily(pins: int, auto: bool):
    """Run daily Pinterest publishing session"""
    print_banner()

    async def _run():
        agent = PinterestAgent(auto_mode=auto)

        if not auto:
            console.print("[yellow]DRY RUN — Pins generated but NOT published. Add --auto to publish.[/yellow]\n")

        console.print(f"[magenta]Generating {pins} pins...[/magenta]")
        result = await agent.run_daily_session(pins_today=pins)

        console.print(f"\n[green]Session complete:[/green]")
        console.print(f"  Pins generated: {result.get('pins_published', 0)}")

        if result.get("content_generated"):
            table = Table(title="Pins Generated", border_style="magenta")
            table.add_column("Title")
            table.add_column("Board")
            table.add_column("Keyword")
            table.add_column("Overlay")

            for pin in result["content_generated"][:10]:
                table.add_row(
                    pin.get("title", "")[:60],
                    pin.get("board", ""),
                    pin.get("keyword", ""),
                    pin.get("text_overlay", ""),
                )
            console.print(table)

    asyncio.run(_run())


@pinterest.command(name="keywords")
def pinterest_keywords():
    """Generate keyword cluster strategy for your niche"""
    async def _run():
        agent = PinterestAgent()
        console.print(f"[magenta]Building keyword strategy for: {config.niche}[/magenta]")
        result = await agent.run_keyword_research()
        console.print_json(json.dumps(result, indent=2, default=str))

    asyncio.run(_run())


@pinterest.command(name="boards")
@click.option("--auto", is_flag=True, help="Actually create the boards")
def pinterest_boards(auto: bool):
    """Generate and optionally create your board strategy"""
    async def _run():
        agent = PinterestAgent(auto_mode=auto)
        boards_data = await agent._get_boards_from_db()
        if not boards_data:
            # Generate from AI
            strategy = await generator_import()
            boards_data = strategy.get("boards", [])[:20]

        result = await agent.create_boards(boards_data)

        table = Table(title="Board Strategy", border_style="magenta")
        table.add_column("Board Name")
        table.add_column("Status")

        for board in result:
            status_color = "green" if board.get("status") == "created" else "yellow"
            table.add_row(board.get("name", ""), f"[{status_color}]{board.get('status', '')}[/{status_color}]")

        console.print(table)

    async def generator_import():
        from content.generator import generator
        return await generator.generate_board_strategy(config.niche, config.target_products)

    asyncio.run(_run())


@pinterest.command(name="plan")
def pinterest_plan():
    """Generate 7-day Pinterest publishing plan"""
    async def _run():
        agent = PinterestAgent()
        plan = await agent.generate_weekly_plan()
        console.print_json(json.dumps(plan, indent=2, default=str))

    asyncio.run(_run())


@pinterest.command(name="seasonal")
def pinterest_seasonal():
    """Generate seasonal content calendar"""
    async def _run():
        agent = PinterestAgent()
        calendar = await agent.generate_seasonal_calendar()
        console.print_json(json.dumps(calendar, indent=2, default=str))

    asyncio.run(_run())


# ─────────────────────────────────────────────
# MARKET RESEARCH
# ─────────────────────────────────────────────

@cli.command()
@click.option("--subreddits", default=None, help="Comma-separated subreddits to research")
@click.option("--keywords", default=None, help="Comma-separated keywords to research")
def research(subreddits: str, keywords: str):
    """Run full market intelligence research pass"""
    print_banner()

    async def _run():
        from research.market_research import MarketResearchEngine
        researcher = MarketResearchEngine()

        sub_list = [s.strip() for s in subreddits.split(",")] if subreddits else ["dropshipping", "ecommerce", "entrepreneur"]
        kw_list = [k.strip() for k in keywords.split(",")] if keywords else config.target_products

        console.print(f"\n[cyan]Running market research on:[/cyan]")
        console.print(f"  Subreddits: {sub_list}")
        console.print(f"  Keywords: {kw_list}")

        with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:
            task = progress.add_task("Running research pass...", total=None)
            result = await researcher.run_full_research_pass(sub_list, kw_list)
            progress.update(task, completed=True)

        summary = result.get("summary", {})

        if summary.get("top_pain_points"):
            console.print("\n[bold]Top Pain Points:[/bold]")
            for p in summary["top_pain_points"][:8]:
                content = p.get("content", str(p)) if isinstance(p, dict) else str(p)
                console.print(f"  • {content[:100]}")

        if summary.get("top_customer_language"):
            console.print("\n[bold]Customer Language (use in copy):[/bold]")
            for l in summary["top_customer_language"][:10]:
                console.print(f"  • {l}")

        output_path = Path(__file__).parent / "data" / "research_results.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        console.print(f"\n[green]Full research saved to: {output_path}[/green]")

    asyncio.run(_run())


# ─────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────

@cli.command()
@click.option("--auto", is_flag=True, help="Enable live posting (without this, generates content only)")
def schedule(auto: bool):
    """Start the automated scheduler (runs 24/7)"""
    print_banner()

    if not auto:
        console.print("[yellow]CONTENT GENERATION MODE — Will generate content but not post.[/yellow]")
        console.print("[yellow]Add --auto flag to enable live posting.[/yellow]\n")

    scheduler = AgentScheduler(auto_mode=auto)

    console.print("[cyan]Starting scheduler...[/cyan]")
    scheduler.start()

    table = Table(title="Scheduled Jobs", border_style="cyan")
    table.add_column("Job")
    table.add_column("Schedule")
    for job in scheduler.get_jobs():
        table.add_row(job["name"], str(job.get("next_run", "?")))
    console.print(table)

    console.print("\n[green]Scheduler running. Press Ctrl+C to stop.[/green]")

    try:
        loop = asyncio.get_event_loop()
        loop.run_forever()
    except KeyboardInterrupt:
        scheduler.stop()
        console.print("\n[yellow]Scheduler stopped.[/yellow]")


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@cli.command()
def dashboard():
    """View agent stats, recent activity, and weekly plan"""
    print_banner()

    from storage.models import RedditAction, PinterestPin, Subreddit, ResearchIntel
    from storage.database import db

    with db.session() as session:
        reddit_actions = session.query(RedditAction).count()
        pinterest_pins = session.query(PinterestPin).count()
        subreddits = session.query(Subreddit).count()
        intel_entries = session.query(ResearchIntel).count()

    table = Table(title="Agent Activity Summary", border_style="cyan")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Reddit Actions Logged", str(reddit_actions))
    table.add_row("Pinterest Pins Generated", str(pinterest_pins))
    table.add_row("Subreddits Tracked", str(subreddits))
    table.add_row("Research Intel Entries", str(intel_entries))
    console.print(table)

    console.print("\n[bold]Available Commands:[/bold]")
    commands = [
        ("python main.py setup", "First-time setup"),
        ("python main.py reddit session", "Reddit session (warmup)"),
        ("python main.py reddit discover", "Find + score subreddits"),
        ("python main.py reddit research <subreddit>", "Deep subreddit research"),
        ("python main.py reddit plan", "7-day Reddit plan"),
        ("python main.py pinterest daily", "Generate today's pins"),
        ("python main.py pinterest keywords", "Keyword strategy"),
        ("python main.py pinterest boards", "Board strategy"),
        ("python main.py pinterest seasonal", "Seasonal calendar"),
        ("python main.py research", "Full market research"),
        ("python main.py schedule --auto", "Start autonomous scheduler"),
    ]

    for cmd, desc in commands:
        console.print(f"  [cyan]{cmd}[/cyan]  [dim]{desc}[/dim]")


# ─────────────────────────────────────────────
# CONFIG CHECK
# ─────────────────────────────────────────────

@cli.command(name="config")
def check_config():
    """Check configuration and API status"""
    print_banner()

    status = config.status()
    table = Table(title="Configuration Status", border_style="cyan")
    table.add_column("Component")
    table.add_column("Status")

    for key, value in status.items():
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)

    console.print("\n[bold]Next step if something is ⚠️ :[/bold]")
    console.print("  1. Copy [cyan].env.example[/cyan] to [cyan].env[/cyan]")
    console.print("  2. Fill in your API keys")
    console.print("  3. Run this command again to verify")


if __name__ == "__main__":
    cli()
