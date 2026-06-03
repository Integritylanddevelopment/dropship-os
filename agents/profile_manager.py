"""
profile_manager.py — Social Profile Manager for ShipStack
Manages your own social media accounts: stores credentials, tracks posting
history, enforces rate limits, and distributes content across profiles.

Storage: SQLite via agents.db.ProfileDB (WAL mode, concurrent-safe)
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from agents.db import ProfileDB, init_db

BASE_DIR     = Path(__file__).parent.parent
SESSIONS_DIR = BASE_DIR / "data" / "profiles" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Ensure DB tables exist on first import
init_db()

_db = ProfileDB()


class ProfileManager:

    PLATFORMS = ["tiktok", "instagram", "youtube"]

    # Minimum gap between posts per profile (in minutes)
    RATE_LIMITS = {
        "tiktok":    180,   # 3 hours
        "instagram": 180,   # 3 hours
        "youtube":   360,   # 6 hours
    }

    def add_profile(
        self,
        platform: str,
        username: str,
        niche: str,
        proxy: Optional[str] = None,
        notes: str = "",
    ) -> dict:
        """Register a new social profile. Session captured separately via session_harvester."""
        platform = platform.lower()
        if platform not in self.PLATFORMS:
            raise ValueError(f"Platform must be one of {self.PLATFORMS}")

        result = _db.add(platform=platform, username=username, niche=niche,
                         proxy=proxy, notes=notes)
        if "error" not in result:
            print(f"[ProfileManager] Added profile: {result['id']} (@{username} on {platform})")
        return result

    def get_profile(self, profile_id: str) -> Optional[dict]:
        return _db.get(profile_id)

    def list_profiles(self, platform: Optional[str] = None, status: Optional[str] = None) -> list:
        return _db.list(platform=platform, status=status)

    def get_available_profiles(self, platform: str, limit: int = 10) -> list:
        """Return profiles that are active and haven't posted within their rate limit window."""
        rate_gap = self.RATE_LIMITS.get(platform.lower(), 180)
        return _db.get_available(platform=platform, rate_gap_minutes=rate_gap, limit=limit)

    def update_profile(self, profile_id: str, **kwargs) -> dict:
        """Update any profile fields (followers, status, last_posted, etc.)"""
        return _db.update(profile_id, **kwargs)

    def mark_posted(self, profile_id: str) -> dict:
        """Call this after a successful post to update timing and post count."""
        return _db.mark_posted(profile_id)

    def set_status(self, profile_id: str, status: str) -> dict:
        valid = ["warming_up", "active", "paused", "flagged"]
        if status not in valid:
            raise ValueError(f"Status must be one of {valid}")
        return _db.update(profile_id, status=status)

    def assign_calendar(self, profile_id: str, calendar_path: str) -> dict:
        """Assign a product's content calendar to this profile."""
        return _db.update(profile_id, assigned_calendar=calendar_path)

    def get_stats(self) -> dict:
        """Aggregate stats across all profiles."""
        profiles = _db.list()
        total_followers = sum(p.get("followers", 0) for p in profiles)
        by_platform = {}
        by_status   = {}

        for p in profiles:
            plat = p["platform"]
            stat = p["status"]
            by_platform[plat] = by_platform.get(plat, 0) + 1
            by_status[stat]   = by_status.get(stat, 0) + 1

        return {
            "total_profiles":  len(profiles),
            "total_followers": total_followers,
            "by_platform":     by_platform,
            "by_status":       by_status,
            "profiles":        profiles,
        }

    def distribute_calendar(self, calendar_path: str, platform: str, profiles_limit: int = 10) -> dict:
        """
        Round-robin: assign a content calendar across available profiles.
        Returns mapping of profile_id → posts assigned.
        """
        profiles = self.get_available_profiles(platform=platform, limit=profiles_limit)
        if not profiles:
            return {"error": f"No available {platform} profiles to distribute to"}

        with open(calendar_path) as f:
            calendar = json.load(f)

        posts = [p for p in calendar.get("posts", [])
                 if p["platform"] == platform and p["status"] == "queued"]

        if not posts:
            return {"error": "No queued posts found for this platform in the calendar"}

        # Round-robin distribution with ±30 min time stagger
        assignments = {p["id"]: [] for p in profiles}
        for i, post in enumerate(posts):
            profile = profiles[i % len(profiles)]
            stagger_mins = random.randint(-30, 30)
            original_time = datetime.fromisoformat(post["scheduled_time"])
            post["scheduled_time"] = (original_time + timedelta(minutes=stagger_mins)).isoformat()
            post["assigned_profile"] = profile["id"]
            assignments[profile["id"]].append(post["id"])

        # Save updated calendar
        with open(calendar_path, "w") as f:
            json.dump(calendar, f, indent=2)

        # Assign calendar path to each profile record
        for p in profiles:
            self.assign_calendar(p["id"], calendar_path)

        return {
            "platform":          platform,
            "profiles_used":     len(profiles),
            "posts_distributed": len(posts),
            "assignments":       assignments,
        }


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    pm = ProfileManager()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python profile_manager.py list [platform] [status]")
        print("  python profile_manager.py add <platform> <username> <niche>")
        print("  python profile_manager.py stats")
        print("  python profile_manager.py status <profile_id> <new_status>")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "list":
        platform = sys.argv[2] if len(sys.argv) > 2 else None
        status   = sys.argv[3] if len(sys.argv) > 3 else None
        profiles = pm.list_profiles(platform=platform, status=status)
        if not profiles:
            print("No profiles found.")
        for p in profiles:
            last = p["last_posted"][:16] if p.get("last_posted") else "never"
            print(f"  [{p['id']}] {p['platform']:10} @{p['username']:20} {p['status']:12} followers={p.get('followers',0)} last={last}")

    elif cmd == "add":
        if len(sys.argv) < 5:
            print("Usage: python profile_manager.py add <platform> <username> <niche>")
            sys.exit(1)
        result = pm.add_profile(sys.argv[2], sys.argv[3], sys.argv[4])
        print(json.dumps(result, indent=2))

    elif cmd == "stats":
        stats = pm.get_stats()
        print(f"Total profiles : {stats['total_profiles']}")
        print(f"Total followers: {stats['total_followers']:,}")
        print(f"By platform    : {stats['by_platform']}")
        print(f"By status      : {stats['by_status']}")

    elif cmd == "status":
        if len(sys.argv) < 4:
            print("Usage: python profile_manager.py status <profile_id> <new_status>")
            sys.exit(1)
        result = pm.set_status(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))
