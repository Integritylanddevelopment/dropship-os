"""
Pinterest AI Agent — Content Agent
Generates all Pinterest content: pin titles, descriptions, boards, blog outlines,
lead magnets, and content variations. The creative engine of the system.
"""
import json
from datetime import datetime
from typing import Optional
from database import Database
from integrations.claude_client import ClaudeClient


PIN_TYPES = [
    "product_feature",
    "problem_solution",
    "educational",
    "roundup",
    "checklist",
    "lead_magnet",
    "seasonal",
    "comparison",
    "before_after",
    "lifestyle",
]

CONTENT_ANGLES = [
    "benefit_led",
    "problem_solution",
    "price_point",
    "seasonal",
    "identity_aspiration",
    "list_format",
    "comparison",
    "urgency",
    "social_proof",
]


class ContentAgent:
    """
    Content Agent: Generates Pinterest-native content at scale.
    One product → 10 pins. One blog post → 12 pins. One keyword → 20 angles.
    """

    def __init__(self, claude: ClaudeClient, db: Database):
        self.claude = claude
        self.db = db

    # =========================================================
    # PIN GENERATION
    # =========================================================
    def generate_pin_batch(
        self,
        product_name: str,
        product_description: str,
        target_url: str,
        primary_keyword: str,
        niche: str,
        pin_count: int = 10,
        board_id: str = None,
        board_name: str = None,
        save_to_queue: bool = True,
    ) -> list[dict]:
        """
        Generate a batch of unique pin variations for a single product.
        Saves all to the content queue automatically.
        """
        print(f"\n✍️  Generating {pin_count} pins for: {product_name}")

        pins = self.claude.generate_pin_variations(
            product_name=product_name,
            product_description=product_description,
            target_url=target_url,
            primary_keyword=primary_keyword,
            pin_count=pin_count,
            niche=niche,
        )

        if save_to_queue and pins:
            for pin in pins:
                queue_item = {
                    "title": pin.get("title", ""),
                    "description": pin.get("description", ""),
                    "link": target_url,
                    "board_id": board_id or "",
                    "board_name": board_name or "",
                    "pin_type": pin.get("pin_type", "product_feature"),
                    "keyword_primary": pin.get("keyword_primary", primary_keyword),
                    "content_angle": pin.get("content_angle", ""),
                    "image_guidance": pin.get("image_guidance", ""),
                    "landing_page_type": pin.get("landing_page_type", "product_page"),
                    "priority": self._calculate_priority(pin),
                    "scheduled_for": None,
                    "notes": f"Auto-generated for product: {product_name}",
                }
                self.db.add_to_queue(queue_item)

        print(f"  ✅ Generated {len(pins)} pin variations → added to content queue")
        return pins

    def generate_weekly_plan(
        self,
        niche: str,
        boards: list[dict],
        keywords: list[str],
        pin_count: int = 15,
        save_to_queue: bool = True,
    ) -> list[dict]:
        """
        Generate a complete weekly content plan across all boards.
        Returns pins organized by day of the week.
        """
        print(f"\n📅 Generating weekly content plan: {pin_count} pins for {niche}")

        plan = self.claude.generate_weekly_content_plan(
            niche=niche,
            boards=boards,
            keywords=keywords,
            pin_count=pin_count,
        )

        if save_to_queue and plan:
            for pin in plan:
                # Find board ID from board name
                board_id = ""
                for board in boards:
                    if board.get("name", "").lower() == pin.get("board_name", "").lower():
                        board_id = board.get("id", "")
                        break

                queue_item = {
                    "title": pin.get("title", ""),
                    "description": pin.get("description", ""),
                    "link": "",  # Will be filled when publishing
                    "board_id": board_id,
                    "board_name": pin.get("board_name", ""),
                    "pin_type": pin.get("pin_type", "product_feature"),
                    "keyword_primary": pin.get("keyword_primary", ""),
                    "content_angle": pin.get("content_angle", ""),
                    "image_guidance": pin.get("image_guidance", ""),
                    "landing_page_type": pin.get("landing_page_type", "product_page"),
                    "priority": pin.get("priority", 5),
                    "scheduled_for": self._get_next_weekday(pin.get("day", "Monday")),
                    "notes": f"Weekly plan - {pin.get('day', 'TBD')}",
                }
                self.db.add_to_queue(queue_item)

        print(f"  ✅ Weekly plan generated: {len(plan)} pins queued")
        return plan

    def repurpose_top_performers(
        self,
        top_count: int = 10,
        variations_per_pin: int = 3,
    ) -> list[dict]:
        """
        Take top-performing published pins and generate fresh variations.
        This is the compounding strategy — amplify what already works.
        """
        print(f"\n♻️  Repurposing top {top_count} performers into fresh variations")

        top_pins = self.db.get_top_performing_pins(metric="saves", limit=top_count)
        new_pins = []

        for pin in top_pins:
            print(f"  → Repurposing: {pin['title'][:50]}...")
            try:
                variations = self.claude.generate_pin_variations(
                    product_name=pin.get("title", ""),
                    product_description=pin.get("description", ""),
                    target_url=pin.get("link", ""),
                    primary_keyword=pin.get("keyword_primary", ""),
                    pin_count=variations_per_pin,
                    niche="lifestyle products",
                )
                for v in variations:
                    queue_item = {
                        "title": v.get("title", ""),
                        "description": v.get("description", ""),
                        "link": pin.get("link", ""),
                        "board_id": pin.get("board_id", ""),
                        "board_name": "",
                        "pin_type": v.get("pin_type", "product_feature"),
                        "keyword_primary": v.get("keyword_primary", ""),
                        "content_angle": v.get("content_angle", ""),
                        "image_guidance": v.get("image_guidance", ""),
                        "landing_page_type": v.get("landing_page_type", "product_page"),
                        "priority": 8,  # Repurposed winners get high priority
                        "scheduled_for": None,
                        "notes": f"Repurposed from pin {pin.get('id')} (saves: {pin.get('saves', 0)})",
                    }
                    self.db.add_to_queue(queue_item)
                    new_pins.append(v)
            except Exception as e:
                print(f"    ⚠️  Error repurposing pin: {e}")

        print(f"  ✅ Created {len(new_pins)} fresh variations from top performers")
        return new_pins

    # =========================================================
    # BOARD CONTENT
    # =========================================================
    def generate_board_structure(
        self,
        niche: str,
        website_url: str,
        num_boards: int = 12,
        save_to_db: bool = True,
    ) -> list[dict]:
        """Generate complete board architecture and save to database."""
        print(f"\n🗂️  Generating board structure for: {niche}")

        boards = self.claude.generate_board_structure(
            niche=niche,
            website_url=website_url,
            num_boards=num_boards,
        )

        if save_to_db:
            for board in boards:
                self.db.upsert_board({
                    "id": f"pending_{board['name'].replace(' ', '_').lower()}",
                    "name": board.get("name", ""),
                    "description": board.get("description", ""),
                    "category": board.get("keyword_cluster", ""),
                    "pin_count": 0,
                    "follower_count": 0,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "keyword_cluster": board.get("keyword_cluster", ""),
                    "priority": board.get("priority", 5),
                    "status": "planned",
                })

        print(f"  ✅ Generated {len(boards)} boards → saved to database")
        return boards

    def optimize_board_descriptions(
        self,
        boards: list[dict],
        keywords: list[str],
        niche: str,
    ) -> list[dict]:
        """Optimize existing board descriptions for Pinterest SEO."""
        print(f"\n🔧 Optimizing {len(boards)} board descriptions")
        optimized = []
        for board in boards:
            try:
                relevant_kws = [kw for kw in keywords if kw.lower() in board.get("name", "").lower()][:5]
                if not relevant_kws:
                    relevant_kws = keywords[:3]

                new_description = self.claude.generate_board_description(
                    board_name=board.get("name", ""),
                    keywords=relevant_kws,
                    niche=niche,
                )
                board["optimized_description"] = new_description
                optimized.append(board)
                print(f"  ✅ {board.get('name', 'Unknown')[:40]}")
            except Exception as e:
                print(f"  ⚠️  Error optimizing {board.get('name')}: {e}")

        return optimized

    # =========================================================
    # LEAD MAGNETS
    # =========================================================
    def generate_lead_magnet(
        self,
        niche: str,
        audience: str,
        product_category: str,
        save_to_db: bool = True,
    ) -> dict:
        """Generate a complete lead magnet concept with pin promotion strategy."""
        print(f"\n🧲 Generating lead magnet for: {niche}")

        magnet = self.claude.generate_lead_magnet(
            niche=niche,
            audience=audience,
            product_category=product_category,
        )

        if save_to_db:
            # Save to lead magnets table
            with self.db._conn() as conn:
                conn.execute("""
                    INSERT INTO lead_magnets (name, type, topic, status)
                    VALUES (?, ?, ?, 'planned')
                """, (
                    magnet.get("name", ""),
                    magnet.get("type", ""),
                    niche,
                ))

            # Add the promotion pin to queue
            queue_item = {
                "title": magnet.get("pin_title", ""),
                "description": magnet.get("pin_description", ""),
                "link": "",  # To be filled with landing page URL
                "board_id": "",
                "board_name": "",
                "pin_type": "lead_magnet",
                "keyword_primary": magnet.get("keyword_primary", ""),
                "content_angle": "free_resource",
                "image_guidance": magnet.get("image_guidance", ""),
                "landing_page_type": "lead_magnet",
                "priority": 9,  # Lead magnets are high priority
                "scheduled_for": None,
                "notes": f"Lead magnet: {magnet.get('name')}",
            }
            self.db.add_to_queue(queue_item)

        print(f"  ✅ Lead magnet generated: {magnet.get('name', 'Unknown')}")
        return magnet

    # =========================================================
    # BLOG CONTENT
    # =========================================================
    def generate_blog_outline(
        self,
        topic: str,
        primary_keyword: str,
        secondary_keywords: list[str],
        niche: str,
        save_pins_to_queue: bool = True,
    ) -> dict:
        """
        Generate a blog post outline optimized for Pinterest traffic.
        Automatically generates pin angles for the post.
        """
        print(f"\n📝 Generating blog outline: {topic}")

        outline = self.claude.generate_blog_outline(
            topic=topic,
            primary_keyword=primary_keyword,
            secondary_keywords=secondary_keywords,
            pin_count=8,
        )

        # Generate pin variations from the blog post angles
        if save_pins_to_queue and "pin_angles" in outline:
            print(f"  → Generating {len(outline['pin_angles'])} pin variations from this blog post")
            for angle in outline["pin_angles"]:
                queue_item = {
                    "title": self.claude.generate_pin_title(
                        product=topic,
                        keyword=primary_keyword,
                        angle=angle,
                        pin_type="educational",
                    ),
                    "description": "",
                    "link": "",  # To be filled with blog post URL when published
                    "board_id": "",
                    "board_name": "",
                    "pin_type": "educational",
                    "keyword_primary": primary_keyword,
                    "content_angle": angle,
                    "image_guidance": f"Create an image for: {angle}",
                    "landing_page_type": "blog_post",
                    "priority": 7,
                    "scheduled_for": None,
                    "notes": f"Blog post pins: {topic}",
                }
                self.db.add_to_queue(queue_item)

        print(f"  ✅ Blog outline complete with {len(outline.get('pin_angles', []))} pin angles")
        return outline

    # =========================================================
    # CONTENT AUDIT
    # =========================================================
    def audit_existing_pins(self, board_id: str = None) -> dict:
        """Audit existing pins and recommend improvements."""
        pins = self.db.get_pins(board_id=board_id, limit=50)
        if not pins:
            return {"message": "No pins found to audit", "recommendations": []}

        issues = []
        recommendations = []

        for pin in pins:
            pin_issues = []

            # Check title length
            title = pin.get("title", "")
            if len(title) < 20:
                pin_issues.append("Title too short — add keyword and benefit")
            elif len(title) > 100:
                pin_issues.append("Title too long — trim to 100 chars")

            # Check description
            description = pin.get("description", "")
            if not description:
                pin_issues.append("Missing description — huge SEO gap")
            elif len(description) < 100:
                pin_issues.append("Description too short — add keywords and value prop")

            # Check for keyword
            if not pin.get("keyword_primary"):
                pin_issues.append("No primary keyword tracked")

            if pin_issues:
                issues.append({
                    "pin_id": pin.get("id"),
                    "title": title[:50],
                    "issues": pin_issues,
                })

        return {
            "total_pins_audited": len(pins),
            "pins_with_issues": len(issues),
            "issue_rate": f"{(len(issues)/len(pins)*100):.0f}%",
            "issues": issues[:20],  # Top 20 issues
            "recommendations": [
                "Add descriptions to all pins missing them",
                "Ensure all titles lead with a searchable keyword",
                "Fill in primary keyword field for all pins",
            ]
        }

    # =========================================================
    # UTILITIES
    # =========================================================
    def _calculate_priority(self, pin: dict) -> int:
        """Calculate pin priority based on type and content angle."""
        priority_map = {
            "lead_magnet": 9,
            "product_feature": 8,
            "problem_solution": 8,
            "roundup": 7,
            "educational": 7,
            "checklist": 7,
            "comparison": 7,
            "seasonal": 8,
            "before_after": 6,
            "lifestyle": 6,
        }
        return priority_map.get(pin.get("pin_type", ""), 5)

    def _get_next_weekday(self, day_name: str) -> str:
        """Get the next occurrence of a given day name."""
        from datetime import timedelta
        days = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
                "Friday": 4, "Saturday": 5, "Sunday": 6}
        today = datetime.now()
        target = days.get(day_name, 0)
        days_ahead = target - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    def get_queue_summary(self) -> dict:
        """Get a summary of the content queue."""
        queued = self.db.get_queue(status="queued")
        by_type = {}
        by_board = {}
        for item in queued:
            pt = item.get("pin_type", "unknown")
            by_type[pt] = by_type.get(pt, 0) + 1
            bn = item.get("board_name", "unassigned")
            by_board[bn] = by_board.get(bn, 0) + 1

        return {
            "total_queued": len(queued),
            "by_pin_type": by_type,
            "by_board": by_board,
            "ready_to_publish": [
                item for item in queued
                if item.get("title") and item.get("description") and item.get("link")
            ]
        }

    def format_pin_for_display(self, pin: dict) -> str:
        """Format a pin for CLI display."""
        return f"""
┌─────────────────────────────────────────────────────┐
│ 📌 {pin.get('title', 'No title')[:50]:50} │
├─────────────────────────────────────────────────────┤
│ Type: {pin.get('pin_type', 'N/A'):<15} Keyword: {pin.get('keyword_primary', 'N/A')[:20]:<20} │
│ Board: {pin.get('board_name', 'N/A')[:45]:45} │
│ Angle: {pin.get('content_angle', 'N/A')[:45]:45} │
├─────────────────────────────────────────────────────┤
│ Description: {pin.get('description', '')[:80]:80} │
├─────────────────────────────────────────────────────┤
│ Image: {pin.get('image_guidance', 'N/A')[:45]:45} │
│ Landing: {pin.get('landing_page_type', 'N/A'):<20} Priority: {pin.get('priority', 5):<5}        │
└─────────────────────────────────────────────────────┘"""
