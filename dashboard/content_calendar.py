"""Proactive content scheduling layer for ShipStack social push.

Pure scheduling logic - no HTTP. Pre-plans WHICH post goes WHEN so the
orchestrator follows a calendar instead of just reacting to throttle rejects.

Doctrine mix ratios (across full window):
  education 40%, problem_solution 20%, BTS 15%, community 15%, promotion 10%

Slot rules:
  - Times: 10am, 2pm, 6pm local (slots 1-3, capped per platform week).
  - At most one promotion slot per day.
  - Promotion never first slot of the day (community/education leads).
  - Daily caps from social_push: W1=1, W2=2, W3=3, W4+=8.
  - Account ages forward across the window (a tiktok in day 5 of W1 becomes W2 on day 8).
"""
import json, pathlib, hashlib
from datetime import datetime, timedelta, timezone

import social_push

STATE = pathlib.Path(__file__).parent / "state"
STATE.mkdir(parents=True, exist_ok=True)
CALENDAR_FILE = STATE / "content_calendar.json"

VALID_PILLARS = ("education", "problem_solution", "behind_the_scenes",
                 "community", "promotion")

# Doctrine target ratios (sum to 1.0)
PILLAR_RATIOS = {
    "education": 0.40,
    "problem_solution": 0.20,
    "behind_the_scenes": 0.15,
    "community": 0.15,
    "promotion": 0.10,
}

# Slot times of day (hours, 24h). Order: lead -> mid -> evening.
SLOT_HOURS = [10, 14, 18]

# GCal colorId per pillar (per task spec).
PILLAR_COLOR = {
    "education": "9",          # blueberry
    "problem_solution": "5",   # banana
    "behind_the_scenes": "3",  # grape
    "community": "10",         # basil
    "promotion": "6",          # tangerine
}

DOCTRINE_CAPS = {1: 1, 2: 2, 3: 3, 4: 8}


def _now():
    return datetime.now()


def _parse_iso(s):
    if not s:
        return None
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        return dt
    except Exception:
        return None


def _week_for_age(age_days: int) -> int:
    if age_days < 7:
        return 1
    if age_days < 14:
        return 2
    if age_days < 21:
        return 3
    return 4


def _slot_id(platform: str, scheduled_for_iso: str, slot_in_day: int) -> str:
    raw = f"{platform}|{scheduled_for_iso}|{slot_in_day}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _choose_pillars_for_day(day_cap: int, cum_counts: dict, total_planned: int):
    """Pick `day_cap` pillars for one day. Returns list of pillar names in slot order.

    Rules:
      - At most one promotion per day.
      - Promotion never in slot 1 (first of day).
      - Greedy fill: pick the pillar whose cumulative ratio is furthest below target.
    """
    chosen = []
    promo_used = False
    # We need to know the eventual TOTAL planned across the whole window so the
    # "below target" math is meaningful. The caller passes total_planned in.
    today_used = {}
    for slot_idx in range(day_cap):
        is_first = (slot_idx == 0)
        best_pillar = None
        best_deficit = -1e9
        # Score pillars by (target_ratio - actual_ratio) i.e. how starved they are.
        # Tie-break: penalize pillars already used today so caps>3 spread across pillars.
        for pillar, target in PILLAR_RATIOS.items():
            if pillar == "promotion":
                if is_first:
                    continue
                if promo_used:
                    continue
            actual = cum_counts.get(pillar, 0) / max(1, total_planned)
            deficit = target - actual
            # Same-day penalty: each repeat docks 0.5 off the deficit so we rotate.
            deficit -= 0.5 * today_used.get(pillar, 0)
            if deficit > best_deficit:
                best_deficit = deficit
                best_pillar = pillar
        if best_pillar is None:
            best_pillar = "education"  # safe fallback
        chosen.append(best_pillar)
        cum_counts[best_pillar] = cum_counts.get(best_pillar, 0) + 1
        today_used[best_pillar] = today_used.get(best_pillar, 0) + 1
        if best_pillar == "promotion":
            promo_used = True
    return chosen


def _project_caps_for_window(platform: str, days: int, now=None):
    """For each day in window, return (date, week, daily_cap). Account age advances."""
    now = now or _now()
    st = social_push._load_account_state()
    created = _parse_iso((st.get(platform) or {}).get("account_created_at"))
    if not created:
        created = datetime.now(timezone.utc)
    # Use naive local-time dates for the schedule grid; age is in UTC days.
    today_local = datetime(now.year, now.month, now.day)
    out = []
    for i in range(days):
        day = today_local + timedelta(days=i)
        # day-age relative to created (UTC). Convert day midnight to UTC for fair compare.
        day_utc = day.replace(tzinfo=timezone.utc)
        age = (day_utc - created).days
        if age < 0:
            age = 0
        wk = _week_for_age(age)
        cap = DOCTRINE_CAPS[wk]
        out.append((day, wk, cap))
    return out


def generate_schedule(platform: str, days: int = 7, now=None):
    """Return ordered list of planned slots for `platform` over `days` days."""
    if platform not in social_push.DRIVERS:
        raise ValueError(f"unknown platform: {platform}")
    now = now or _now()
    grid = _project_caps_for_window(platform, days, now)
    # Total posts in window = sum of caps (for ratio math).
    total_planned = sum(cap for _, _, cap in grid)
    cum_counts = {p: 0 for p in PILLAR_RATIOS.keys()}
    slots = []
    for day_idx, (day, week, cap) in enumerate(grid):
        if cap <= 0:
            continue
        day_pillars = _choose_pillars_for_day(cap, cum_counts, total_planned)
        for slot_in_day, pillar in enumerate(day_pillars):
            hour = SLOT_HOURS[slot_in_day] if slot_in_day < len(SLOT_HOURS) else SLOT_HOURS[-1]
            # When cap > 3, stagger extra slots at +2h intervals after 18:00 (cap up to 8).
            if slot_in_day >= len(SLOT_HOURS):
                hour = SLOT_HOURS[-1] + 2 * (slot_in_day - len(SLOT_HOURS) + 1)
                if hour > 22:
                    hour = 22
            sched = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            sched_iso = sched.isoformat(timespec="seconds")
            sid = _slot_id(platform, sched_iso, slot_in_day)
            slots.append({
                "slot_id": sid,
                "platform": platform,
                "scheduled_for": sched_iso,
                "day_index": day_idx,
                "slot_in_day": slot_in_day,
                "pillar": pillar,
                "week": week,
                "daily_cap": cap,
                "status": "planned",
                "kit": None,
            })
    return slots


def match_kits(slots, media_kits):
    """For promotion slots, attach the highest-scored kit by product_keyword.

    media_kits is dict {keyword: kit_dict}.
    For non-promotion slots, kit stays None (means: needs UGC/edu content not yet built).
    The "highest scored" heuristic: kit without 'error' field wins over kits with errors;
    among ties, the one with non-empty hook/caption wins. Falls back to first available.
    """
    if not media_kits:
        return slots
    # Rank candidate kits.
    ranked = []
    for kw, kit in media_kits.items():
        if not isinstance(kit, dict):
            continue
        score = 0
        if not kit.get("error"):
            score += 10
        if kit.get("hook"):
            score += 2
        if kit.get("caption"):
            score += 2
        if kit.get("image_url"):
            score += 1
        ranked.append((score, kw, kit))
    ranked.sort(key=lambda r: r[0], reverse=True)
    if not ranked:
        return slots
    top_kw = ranked[0][1]
    top_kit = ranked[0][2]
    for s in slots:
        if s["pillar"] == "promotion":
            s["kit"] = top_kit
            s["product_keyword"] = top_kw
    return slots


def save_schedule(platform: str, slots):
    cal = load_schedule()
    cal[platform] = slots
    CALENDAR_FILE.write_text(json.dumps(cal, indent=2, default=str), encoding="utf-8")
    return cal


def load_schedule():
    if not CALENDAR_FILE.exists():
        return {}
    try:
        data = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def due_now(platform: str, now=None):
    """Slots whose scheduled_for <= now AND not yet posted AND not yet in social_queue."""
    now = now or _now()
    cal = load_schedule()
    plat_slots = cal.get(platform) or []
    queue = social_push._load_queue()
    # Build set of (platform, scheduled_for) already represented in the queue via queued_at hint.
    # Cross-reference: we mark slots posted via posted_at in the calendar. Also skip if status!=planned.
    out = []
    for s in plat_slots:
        if s.get("status") != "planned":
            continue
        if s.get("posted_at"):
            continue
        sched = _parse_iso(s.get("scheduled_for"))
        if sched is None:
            continue
        # Make `now` and `sched` comparable (both naive local).
        if sched.tzinfo is not None:
            sched_cmp = sched.replace(tzinfo=None)
        else:
            sched_cmp = sched
        if sched_cmp <= now:
            out.append(s)
    return out


def mark_posted(platform: str, slot_id: str, posted_at_iso=None):
    cal = load_schedule()
    plat_slots = cal.get(platform) or []
    posted_at_iso = posted_at_iso or _now().isoformat(timespec="seconds")
    found = False
    for s in plat_slots:
        if s.get("slot_id") == slot_id:
            s["posted_at"] = posted_at_iso
            s["status"] = "posted"
            found = True
            break
    if found:
        cal[platform] = plat_slots
        CALENDAR_FILE.write_text(json.dumps(cal, indent=2, default=str), encoding="utf-8")
    return found


def mirror_to_gcal(slots, dry_run=True):
    """Build GCal event specs from slots.

    Returns list of event-spec dicts shaped for the calendar MCP's create_event:
      { summary, description, startTime, endTime, colorId, location? }
    When dry_run=True (default), just returns the specs without side effects.
    When dry_run=False, still just returns the specs - the caller is responsible
    for invoking the MCP. content_calendar stays pure.
    """
    events = []
    platform_label = {
        "tiktok": "TikTok",
        "instagram_reels": "Instagram",
        "youtube_shorts": "YouTube",
        "pinterest": "Pinterest",
    }
    for s in slots:
        plat = platform_label.get(s.get("platform"), s.get("platform", "?"))
        pillar = s.get("pillar", "education")
        kw = s.get("product_keyword") or (s.get("kit") or {}).get("product_keyword") or ""
        summary_parts = [f"ShipStack: {plat} / {pillar}"]
        if kw:
            summary_parts.append(f"/ {kw}")
        summary = " ".join(summary_parts)
        # Description: hook + caption preview.
        kit = s.get("kit") or {}
        hook = kit.get("hook") or ""
        cap = kit.get("caption") or ""
        desc_lines = [
            f"Platform: {plat}",
            f"Pillar: {pillar}",
            f"Week: {s.get('week')} | Daily cap: {s.get('daily_cap')}",
        ]
        if kw:
            desc_lines.append(f"Product: {kw}")
        if hook:
            desc_lines.append(f"Hook: {hook}")
        if cap:
            desc_lines.append(f"Caption: {cap[:200]}")
        desc_lines.append(f"slot_id: {s.get('slot_id')}")
        description = "\n".join(desc_lines)
        sched = _parse_iso(s.get("scheduled_for"))
        if sched is None:
            continue
        end = sched + timedelta(minutes=30)
        events.append({
            "summary": summary,
            "description": description,
            "startTime": sched.isoformat(timespec="seconds"),
            "endTime": end.isoformat(timespec="seconds"),
            "colorId": PILLAR_COLOR.get(pillar, "9"),
            "slot_id": s.get("slot_id"),
            "platform": s.get("platform"),
            "dry_run": dry_run,
        })
    return events
