"""Stage 6 Social Push orchestrator. Queue-only. No real HTTP posting.

Doctrine enforcement (per social_doctrine.md):
  1. Account ramp: week 1 cap=1, week 2 cap=2, week 3 cap=3, week 4+ cap=8 posts/day.
     Computed from per-platform account_created_at in state/account_state.json.
  2. Content mix: target ratios education 40 / problem_solution 20 / BTS 15 /
     community 15 / promotion 10 (rolling 5-post window per platform).
     Reject if window violates targets or has >=3 promotion entries in last 5.
     Missing pillar on a kit -> defaulted to 'promotion'.
  3. Engagement debt: require >=3 engagements_since_last_post before next post on
     a platform. First post on a brand-new platform passes automatically.
  4. Lightweight forbidden caption check (warn-only): 'doctrine_warn' status if a
     known spammy phrase appears 2+ times.

A rejected queue_post still writes the entry to social_queue.json so the dashboard
can show the rejection_reason, but DOES NOT update last_5_pillars or reset
engagement debt -- only successful queue/ready entries do that.
"""
import os, json, pathlib
from datetime import datetime, timezone

STATE = pathlib.Path(__file__).parent / "state"
STATE.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = STATE / "social_queue.json"
ACCOUNT_FILE = STATE / "account_state.json"

DRIVERS = {
    "tiktok": {
        "name": "TikTok",
        "env_var": "TIKTOK_ACCESS_TOKEN",
        "connect_url": "https://developers.tiktok.com/apps",
    },
    "instagram_reels": {
        "name": "Instagram Reels",
        "env_var": "IG_GRAPH_TOKEN",
        "connect_url": "https://developers.facebook.com/apps/",
    },
    "youtube_shorts": {
        "name": "YouTube Shorts",
        "env_var": "YT_API_KEY",
        "connect_url": "https://console.cloud.google.com/apis/credentials",
    },
    "pinterest": {
        "name": "Pinterest",
        "env_var": "PINTEREST_ACCESS_TOKEN",
        "connect_url": "https://developers.pinterest.com/apps/",
    },
}

VALID_PILLARS = ("education", "problem_solution", "behind_the_scenes",
                 "community", "promotion")

# Doctrine targets per 5-post rolling window. Caps = max entries allowed in last 5
# given the doctrine ratio: education 40% -> up to 4/5; promotion 10% -> up to 1/5
# but we hard-cap promotion at <3 in last 5 (doctrine rule). Other non-promo
# pillars limited to ratio * 5 rounded up.
PILLAR_MAX_IN_5 = {
    "education": 5,          # 40% target, no hard cap (lots of education is fine)
    "problem_solution": 4,   # 20% -> generous cap
    "behind_the_scenes": 3,  # 15% -> 3/5
    "community": 3,          # 15% -> 3/5
    "promotion": 2,          # 10% target, doctrine: <3 in last 5 -> cap at 2
}

SPAM_PHRASES = ("buy now", "limited time", "act fast", "click link in bio")


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(s):
    if not s:
        return None
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _default_account_state():
    now = _now_iso()
    return {
        p: {
            "account_created_at": now,
            "engagements_since_last_post": 0,
            "last_5_pillars": [],
        }
        for p in DRIVERS.keys()
    }


def _load_account_state():
    if not ACCOUNT_FILE.exists():
        st = _default_account_state()
        ACCOUNT_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")
        return st
    try:
        st = json.loads(ACCOUNT_FILE.read_text(encoding="utf-8"))
        if not isinstance(st, dict):
            st = {}
    except Exception:
        st = {}
    changed = False
    for p in DRIVERS.keys():
        if p not in st or not isinstance(st[p], dict):
            st[p] = {
                "account_created_at": _now_iso(),
                "engagements_since_last_post": 0,
                "last_5_pillars": [],
            }
            changed = True
        else:
            if "account_created_at" not in st[p]:
                st[p]["account_created_at"] = _now_iso(); changed = True
            if "engagements_since_last_post" not in st[p]:
                st[p]["engagements_since_last_post"] = 0; changed = True
            if "last_5_pillars" not in st[p] or not isinstance(st[p]["last_5_pillars"], list):
                st[p]["last_5_pillars"] = []; changed = True
    if changed:
        ACCOUNT_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    return st


def _save_account_state(st):
    ACCOUNT_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def is_connected(platform):
    d = DRIVERS.get(platform)
    if not d:
        return False
    v = os.environ.get(d["env_var"], "")
    return bool(v and v.strip())


def _load_queue():
    if not QUEUE_FILE.exists():
        return []
    try:
        data = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_queue(q):
    QUEUE_FILE.write_text(json.dumps(q, indent=2, default=str), encoding="utf-8")


def list_queue():
    return _load_queue()


def _week_of(platform, st=None):
    st = st if st is not None else _load_account_state()
    created = _parse_iso((st.get(platform) or {}).get("account_created_at"))
    if not created:
        return 1
    age_days = (datetime.now(timezone.utc) - created).days
    if age_days < 7:
        return 1
    if age_days < 14:
        return 2
    if age_days < 21:
        return 3
    return 4


def _load_doctrine_caps():
    return {1: 1, 2: 2, 3: 3, 4: 8}


def _daily_cap(platform, st=None):
    return _load_doctrine_caps()[_week_of(platform, st)]


def _posts_today(platform, q=None):
    q = q if q is not None else _load_queue()
    today = datetime.now().date().isoformat()  # local-naive to match queued_at format
    n = 0
    for e in q:
        if e.get("platform") != platform:
            continue
        # Only count successfully accepted entries against the cap
        if e.get("status") in ("throttled", "mix_violation", "engagement_debt"):
            continue
        qa = e.get("queued_at") or ""
        # queued_at format starts with YYYY-MM-DD
        if qa[:10] == today:
            n += 1
    return n


def _normalize_pillar(pillar):
    if not pillar or not isinstance(pillar, str):
        return "promotion"
    p = pillar.strip().lower().replace("-", "_").replace(" ", "_")
    if p in VALID_PILLARS:
        return p
    aliases = {
        "edu": "education",
        "bts": "behind_the_scenes",
        "behindthescenes": "behind_the_scenes",
        "problem": "problem_solution",
        "solution": "problem_solution",
        "promo": "promotion",
        "sale": "promotion",
        "community_engagement": "community",
    }
    return aliases.get(p, "promotion")


def _check_mix(platform, pillar, st=None):
    st = st if st is not None else _load_account_state()
    last5 = list((st.get(platform) or {}).get("last_5_pillars") or [])
    # simulate the new pillar being added (FIFO, max 5)
    sim = (last5 + [pillar])[-5:]
    counts = {}
    for p in sim:
        counts[p] = counts.get(p, 0) + 1
    # Hard rule: >=3 promotion in last 5 -> mix violation
    if counts.get("promotion", 0) >= 3:
        return (False, "promotion>=3/5", counts)
    # Soft caps per pillar
    for p, mx in PILLAR_MAX_IN_5.items():
        if counts.get(p, 0) > mx:
            return (False, f"{p}>{mx}/5", counts)
    return (True, "", counts)


def _check_engagement_debt(platform, st=None):
    st = st if st is not None else _load_account_state()
    a = st.get(platform) or {}
    last5 = list(a.get("last_5_pillars") or [])
    if not last5:
        # first post on this platform passes automatically
        return (True, 0)
    eng = int(a.get("engagements_since_last_post") or 0)
    if eng >= 3:
        return (True, 0)
    return (False, 3 - eng)


def _check_caption_spam(kit):
    cap = (kit.get("caption") or "") + " " + (kit.get("hook") or "")
    cap_l = cap.lower()
    hits = 0
    for phrase in SPAM_PHRASES:
        idx = 0
        while True:
            j = cap_l.find(phrase, idx)
            if j < 0:
                break
            hits += 1
            idx = j + len(phrase)
    return hits


def queue_post(platform, media_kit):
    if platform not in DRIVERS:
        raise ValueError("unknown platform: " + str(platform))
    st = _load_account_state()
    q = _load_queue()
    pillar = _normalize_pillar(media_kit.get("pillar") if isinstance(media_kit, dict) else None)
    now = datetime.now().isoformat(timespec="seconds")
    base = {
        "platform": platform,
        "kit": media_kit,
        "queued_at": now,
        "pillar": pillar,
    }
    # 1. RAMP -> derives cap
    week = _week_of(platform, st)
    cap = _load_doctrine_caps()[week]
    posts_today = _posts_today(platform, q)
    # 2. CAP
    if posts_today >= cap:
        entry = dict(base)
        entry["status"] = "throttled"
        entry["rejection_reason"] = f"daily cap hit: {posts_today}/{cap} (week {week})"
        q.append(entry); _save_queue(q)
        return entry
    # 3. MIX
    ok_mix, mix_reason, mix_counts = _check_mix(platform, pillar, st)
    if not ok_mix:
        entry = dict(base)
        entry["status"] = "mix_violation"
        entry["rejection_reason"] = f"mix violation: {mix_reason}"
        entry["mix_counts"] = mix_counts
        q.append(entry); _save_queue(q)
        return entry
    # 4. ENGAGEMENT DEBT
    ok_eng, shortfall = _check_engagement_debt(platform, st)
    if not ok_eng:
        entry = dict(base)
        entry["status"] = "engagement_debt"
        entry["rejection_reason"] = f"engagement_debt: {shortfall} more needed"
        q.append(entry); _save_queue(q)
        return entry
    # All hard checks passed. Set status based on connection + soft spam check.
    status = "ready" if is_connected(platform) else "queued"
    spam_hits = _check_caption_spam(media_kit if isinstance(media_kit, dict) else {})
    entry = dict(base)
    entry["status"] = status
    if spam_hits >= 2:
        entry["status"] = "doctrine_warn"
        entry["underlying_status"] = status
        entry["rejection_reason"] = f"doctrine_warn: spam phrases hit {spam_hits}x (queued anyway)"
    # Append & save queue first.
    q.append(entry); _save_queue(q)
    # On a successful accept, update account state: push pillar onto last_5, reset eng.
    a = st.get(platform) or {}
    last5 = list(a.get("last_5_pillars") or [])
    last5.append(pillar)
    last5 = last5[-5:]
    a["last_5_pillars"] = last5
    a["engagements_since_last_post"] = 0
    st[platform] = a
    _save_account_state(st)
    return entry


def log_engagement(platform, count=1):
    if platform not in DRIVERS:
        raise ValueError("unknown platform: " + str(platform))
    try:
        count = int(count)
    except Exception:
        count = 1
    if count < 0:
        count = 0
    st = _load_account_state()
    a = st.get(platform) or {}
    new_val = int(a.get("engagements_since_last_post") or 0) + count
    a["engagements_since_last_post"] = new_val
    st[platform] = a
    _save_account_state(st)
    return new_val


def account_status(platform):
    if platform not in DRIVERS:
        return None
    st = _load_account_state()
    a = st.get(platform) or {}
    week = _week_of(platform, st)
    cap = _load_doctrine_caps()[week]
    pt = _posts_today(platform)
    eng = int(a.get("engagements_since_last_post") or 0)
    last5 = list(a.get("last_5_pillars") or [])
    if not last5:
        debt_remaining = 0
    else:
        debt_remaining = max(0, 3 - eng)
    return {
        "platform": platform,
        "week": week,
        "daily_cap": cap,
        "posts_today": pt,
        "posts_remaining": max(0, cap - pt),
        "last_5_pillars": last5,
        "engagements_since_last_post": eng,
        "engagement_debt_remaining": debt_remaining,
        "account_created_at": a.get("account_created_at"),
    }


def all_account_status():
    return {p: account_status(p) for p in DRIVERS.keys()}


def platforms_status():
    q = _load_queue()
    counts = {}
    for e in q:
        p = e.get("platform")
        if p:
            counts[p] = counts.get(p, 0) + 1
    out = []
    for key, d in DRIVERS.items():
        out.append({
            "platform": key,
            "name": d["name"],
            "connected": is_connected(key),
            "env_var": d["env_var"],
            "connect_url": d["connect_url"],
            "queued_count": counts.get(key, 0),
        })
    return out
