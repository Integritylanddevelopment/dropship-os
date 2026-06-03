"""
Pinterest AI Agent — Publishing Agent
Handles all pin and board creation via Pinterest API.
Manages content queue, scheduling, rate limits, and publish tracking.
"""
import time
import json
from datetime import datetime, timedelta
from typing import Optional
from database import Database
from integrations.pinterest_api import PinterestAPI, PinterestAPIError


class PublishingAgent:
    """
    Publishing Agent: Deploys content from queue to Pinterest.
    Respects rate limits, tracks publish status, handles errors gracefully.
    """

    OPTIMAL_PUBLISH_TIMES = {
        "Monday":    ["08:00", "20:00"],
        "Tuesday":   ["08:00", "21:00"],
        "Wednesday": ["09:00", "20:00"],
        "Thursday":  ["08:00", "21:00"],
        "Friday":    ["08:00", "20:00"],
        "Saturday":  ["08:00", "20:00", "21:00"],
        "Sunday":    ["08:00", "20:00", "23:00"],
    }

    def __init__(self, pinterest: PinterestAPI, db: Database):
        self.pinterest = pinterest
        self.db = db

    # =========================================================
    # BOARD MANAGEMENT
    # =========================================================
    def sync_boards_from_pinterest(self) -> list[dict]:
        """Pull all boards from Pinterest API and sync to local database."""
        print("\n🔄 Syncing boards from Pinterest...")
        try:
            boards = self.pinterest.list_boards()
            for board in boards:
                self.db.upsert_board({
                    "id": board["id"],
                    "name": board.get("name", ""),
                    "description": board.get("description", ""),
                    "category": board.get("board_pins_modified", ""),
                    "pin_count": board.get("pin_count", 0),
                    "follower_count": board.get("follower_count", 0),
                    "created_at": board.get("created_at", datetime.now().isoformat()),
                    "updated_at": datetime.now().isoformat(),
                    "keyword_cluster": "",
                    "priority": 5,
                    "status": "active",
                })
            print(f"  ✅ Synced {len(boards)} boards from Pinterest")
            return boards
        except PinterestAPIError as e:
            print(f"  ❌ Failed to sync boards: {e}")
            return []

    def create_board(
        self,
        name: str,
        description: str,
        keyword_cluster: str = "",
        priority: int = 5,
        dry_run: bool = False,
    ) -> Optional[dict]:
        """Create a single board on Pinterest and save to database."""
        if dry_run:
            print(f"  [DRY RUN] Would create board: {name}")
            return {"id": f"dry_run_{name.replace(' ', '_')}", "name": name}

        try:
            board = self.pinterest.create_board(name, description)
            self.db.upsert_board({
                "id": board["id"],
                "name": board.get("name", name),
                "description": description,
                "category": "",
                "pin_count": 0,
                "follower_count": 0,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "keyword_cluster": keyword_cluster,
                "priority": priority,
                "status": "active",
            })
            print(f"  ✅ Created board: {name} (ID: {board['id']})")
            return board
        except PinterestAPIError as e:
            print(f"  ❌ Failed to create board '{name}': {e}")
            return None

    def create_boards_batch(
        self,
        board_configs: list[dict],
        dry_run: bool = False,
    ) -> list[dict]:
        """Create multiple boards from a list of board configurations."""
        print(f"\n🗂️  Creating {len(board_configs)} boards...")
        created = []
        for config in board_configs:
            board = self.create_board(
                name=config.get("name", ""),
                description=config.get("description", ""),
                keyword_cluster=config.get("keyword_cluster", ""),
                priority=config.get("priority", 5),
                dry_run=dry_run,
            )
            if board:
                created.append(board)
            time.sleep(0.5)  # Respect rate limits
        print(f"  ✅ Created {len(created)} boards")
        return created

    def update_board_description(
        self,
        board_id: str,
        new_description: str,
        dry_run: bool = False,
    ) -> bool:
        """Update a board description (for SEO optimization)."""
        if dry_run:
            print(f"  [DRY RUN] Would update board {board_id}: {new_description[:50]}...")
            return True
        try:
            self.pinterest.update_board(board_id, {"description": new_description})
            print(f"  ✅ Updated board {board_id}")
            return True
        except PinterestAPIError as e:
            print(f"  ❌ Failed to update board {board_id}: {e}")
            return False

    # =========================================================
    # PIN PUBLISHING
    # =========================================================
    def publish_pin(
        self,
        title: str,
        description: str,
        link: str,
        board_id: str,
        image_url: str,
        keyword_primary: str = "",
        pin_type: str = "standard",
        queue_id: int = None,
        dry_run: bool = False,
    ) -> Optional[dict]:
        """
        Publish a single pin to Pinterest.
        Returns the created pin data or None on failure.
        """
        if dry_run:
            print(f"  [DRY RUN] Would publish: {title[:50]}...")
            return {"id": "dry_run_pin", "title": title}

        # Validate required fields
        if not title or not board_id or not image_url or not link:
            print(f"  ⚠️  Skipping pin — missing required fields")
            print(f"      title: {'✓' if title else '✗'} | board: {'✓' if board_id else '✗'} | image: {'✓' if image_url else '✗'} | link: {'✓' if link else '✗'}")
            return None

        # Enforce title length limit
        if len(title) > 100:
            title = title[:97] + "..."

        # Enforce description length limit
        if len(description) > 500:
            description = description[:497] + "..."

        try:
            pin = self.pinterest.create_pin(
                board_id=board_id,
                title=title,
                description=description,
                link=link,
                image_url=image_url,
            )

            # Save to pins database
            self.db.upsert_pin({
                "id": pin["id"],
                "board_id": board_id,
                "title": title,
                "description": description,
                "link": link,
                "image_url": image_url,
                "pin_type": pin_type,
                "keyword_primary": keyword_primary,
                "status": "published",
                "published_at": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "impressions": 0,
                "saves": 0,
                "clicks": 0,
                "outbound_clicks": 0,
            })

            # Mark queue item as published
            if queue_id:
                self.db.update_queue_status(queue_id, "published")

            print(f"  ✅ Published: {title[:50]} → Board: {board_id}")
            return pin

        except PinterestAPIError as e:
            print(f"  ❌ Failed to publish '{title[:40]}': {e}")
            if queue_id:
                self.db.update_queue_status(queue_id, "failed")
            return None

    def publish_from_queue(
        self,
        max_pins: int = 10,
        board_id_filter: str = None,
        dry_run: bool = False,
        image_url_default: str = None,
    ) -> dict:
        """
        Publish queued pins that are ready (have title, description, link).
        Respects daily pin limits and rate limits.

        image_url_default: fallback image URL if pin doesn't have one
        """
        print(f"\n🚀 Publishing from queue (max: {max_pins} pins)...")

        queued = self.db.get_queue(status="queued", limit=max_pins * 2)

        # Filter to ready items (have all required fields)
        ready = []
        for item in queued:
            if (
                item.get("title")
                and item.get("description")
                and item.get("link")
                and item.get("board_id")
                and (image_url_default or item.get("image_url"))
            ):
                if board_id_filter is None or item.get("board_id") == board_id_filter:
                    ready.append(item)

        if not ready:
            print("  ⚠️  No ready-to-publish pins in queue (need: title, description, link, board_id, image)")
            return {"published": 0, "skipped": len(queued), "failed": 0}

        published = 0
        failed = 0
        skipped = 0

        for i, item in enumerate(ready[:max_pins]):
            print(f"\n  [{i+1}/{min(len(ready), max_pins)}] Publishing...")

            result = self.publish_pin(
                title=item["title"],
                description=item["description"],
                link=item["link"],
                board_id=item["board_id"],
                image_url=item.get("image_url") or image_url_default,
                keyword_primary=item.get("keyword_primary", ""),
                pin_type=item.get("pin_type", "standard"),
                queue_id=item["id"],
                dry_run=dry_run,
            )

            if result:
                published += 1
            else:
                failed += 1

            # Rate limiting between pins
            if not dry_run and i < len(ready) - 1:
                time.sleep(1.0)

        print(f"\n  📊 Publish summary: {published} published | {failed} failed | {skipped} skipped")
        return {"published": published, "skipped": skipped, "failed": failed}

    def batch_publish_products(
        self,
        products: list[dict],
        board_mapping: dict,
        dry_run: bool = False,
    ) -> dict:
        """
        Publish pins for multiple products across their appropriate boards.

        products: [{"name": "Product Name", "url": "https://...", "image_url": "https://...", "category": "kitchen"}]
        board_mapping: {"kitchen": "board_id_here", "home": "board_id_here"}
        """
        print(f"\n🏭 Batch publishing {len(products)} products...")
        results = {"published": 0, "failed": 0}

        for product in products:
            category = product.get("category", "general")
            board_id = board_mapping.get(category, board_mapping.get("general", ""))

            if not board_id:
                print(f"  ⚠️  No board mapped for category: {category}")
                continue

            result = self.publish_pin(
                title=product.get("pin_title", product.get("name", "")),
                description=product.get("pin_description", ""),
                link=product.get("url", ""),
                board_id=board_id,
                image_url=product.get("image_url", ""),
                keyword_primary=product.get("keyword_primary", ""),
                pin_type="product_feature",
                dry_run=dry_run,
            )

            if result:
                results["published"] += 1
            else:
                results["failed"] += 1

            time.sleep(0.5)

        return results

    # =========================================================
    # SCHEDULING
    # =========================================================
    def get_next_publish_slot(self, day: str = None) -> str:
        """Get the next optimal publish time for a given day."""
        if day is None:
            day = datetime.now().strftime("%A")
        slots = self.OPTIMAL_PUBLISH_TIMES.get(day, ["09:00"])
        # Return next available slot (simplified — full scheduler would check what's already scheduled)
        return f"{day} at {slots[0]}"

    def generate_publish_schedule(
        self,
        week_start: str = None,
        pins_per_day: dict = None,
    ) -> list[dict]:
        """Generate an optimal publish schedule for the week."""
        if pins_per_day is None:
            pins_per_day = {
                "Monday": 3, "Tuesday": 2, "Wednesday": 3,
                "Thursday": 2, "Friday": 3, "Saturday": 2, "Sunday": 2,
            }

        if week_start is None:
            week_start = datetime.now().strftime("%Y-%m-%d")

        schedule = []
        start_date = datetime.strptime(week_start, "%Y-%m-%d")

        for i, (day, count) in enumerate(pins_per_day.items()):
            publish_date = start_date + timedelta(days=i)
            times = self.OPTIMAL_PUBLISH_TIMES.get(day, ["09:00"])
            for j in range(count):
                time_slot = times[j % len(times)]
                schedule.append({
                    "day": day,
                    "date": publish_date.strftime("%Y-%m-%d"),
                    "time": time_slot,
                    "datetime": f"{publish_date.strftime('%Y-%m-%d')} {time_slot}",
                    "slot_number": j + 1,
                })

        return schedule

    # =========================================================
    # STATUS REPORTING
    # =========================================================
    def get_publish_status(self) -> dict:
        """Get current publishing status and queue overview."""
        queued = self.db.get_queue(status="queued")
        published = self.db.get_pins(status="published", limit=10)

        ready_to_publish = [
            item for item in queued
            if item.get("title") and item.get("description") and item.get("link") and item.get("board_id")
        ]

        return {
            "queued_total": len(queued),
            "ready_to_publish": len(ready_to_publish),
            "needs_completion": len(queued) - len(ready_to_publish),
            "recently_published": len(published),
            "next_optimal_time": self.get_next_publish_slot(),
            "recommendations": self._get_publishing_recommendations(queued, published),
        }

    def _get_publishing_recommendations(
        self,
        queued: list[dict],
        published: list[dict],
    ) -> list[str]:
        """Generate actionable publishing recommendations."""
        recs = []

        if len(queued) < 15:
            recs.append("⚠️  Low queue — generate more pin content to maintain 15+ pins/week cadence")

        incomplete = [q for q in queued if not q.get("link") or not q.get("image_url")]
        if incomplete:
            recs.append(f"📝 {len(incomplete)} queued pins need links/images added before publishing")

        if not published:
            recs.append("🚀 No published pins yet — start publishing your highest-priority queue items")

        lead_magnets = [q for q in queued if q.get("pin_type") == "lead_magnet"]
        if not lead_magnets:
            recs.append("🧲 Add at least 1 lead magnet pin this week to start building email list")

        if len(recs) == 0:
            recs.append("✅ Publishing pipeline looks healthy — keep the cadence going")

        return recs
