import json
import os
import hashlib
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in (value or ""))
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "item"


class PostingManager:
    VERSION = 1
    DEFAULT_FEED_URL = "http://127.0.0.1:8889/api/library/approved"
    BRAND = {
        "business_name": "Integrity Products USA",
        "support_email": "support@integrityproductsusa.com",
        "phone": "945-312-6709",
    }
    PLATFORM_RULES = {
        "pinterest": {
            "requires": ["image_url", "landing_url"],
            "description": "Direct-link image posting is supported now.",
        },
        "youtube": {
            "requires": ["video_path", "landing_url"],
            "description": "Requires a finished product video and YouTube credentials.",
        },
        "tiktok": {
            "requires": ["video_path"],
            "description": "Requires a finished product video and TikTok OAuth.",
        },
        "meta": {
            "requires": ["image_url", "landing_url"],
            "description": "Current route can publish media, but account link readiness must be confirmed first.",
        },
    }
    WARMUP_LIMITS = {
        "pinterest": [1, 2, 3, 4, 5, 6, 8],
        "youtube": [1, 1, 1, 2, 2, 2, 3],
        "tiktok": [1, 1, 2, 2, 3, 4, 5],
        "meta": [1, 1, 2, 2, 3, 3, 4],
    }
    COOLDOWN_MINUTES = {
        "pinterest": 45,
        "youtube": 180,
        "tiktok": 120,
        "meta": 90,
    }
    ACTIVE_ACCOUNT_STATES = {"warming", "active"}

    def __init__(self, feed_url: str | None = None, data_dir: str | Path | None = None):
        self.root = Path(__file__).resolve().parent.parent
        self.data_dir = Path(data_dir or (self.root / "social_ai_agent" / "data" / "posting_manager"))
        self.state_path = self.data_dir / "state.json"
        self.feed_url = feed_url or os.getenv("SHIPSTACK_APPROVED_FEED_URL", self.DEFAULT_FEED_URL)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _default_state(self) -> dict:
        return {
            "version": self.VERSION,
            "brand": deepcopy(self.BRAND),
            "feed_url": self.feed_url,
            "last_sync_at": "",
            "last_sync_error": "",
            "accounts": [],
            "queue": [],
        }

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            state = self._default_state()
            self._save_state(state)
            return state
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            state = self._default_state()
        state.setdefault("version", self.VERSION)
        state.setdefault("brand", deepcopy(self.BRAND))
        state.setdefault("feed_url", self.feed_url)
        state.setdefault("last_sync_at", "")
        state.setdefault("last_sync_error", "")
        state.setdefault("accounts", [])
        state.setdefault("queue", [])
        return state

    def _save_state(self, state: dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def _item_id(self, product_id: str, ad: dict) -> str:
        payload = "|".join([
            product_id or "",
            ad.get("headline", "") or "",
            ad.get("subline", "") or "",
            ad.get("image_url", "") or "",
            ad.get("approved_at", "") or "",
        ])
        digest = hashlib.sha1(payload.encode("utf-8", errors="replace")).hexdigest()[:12]
        return f"{_slug(product_id)}_{digest}"

    def _grade_sort(self, item: dict) -> tuple:
        letter_rank = {"A": 0, "B": 1, "C": 2, "D": 3}.get((item.get("letter") or "").upper(), 9)
        status_rank = {
            "ready": 0,
            "posted": 1,
            "paused": 2,
            "removed_from_feed": 3,
        }.get(item.get("status", "ready"), 9)
        approved_at = item.get("approved_at", "")
        return (status_rank, 0 if item.get("feed_active", True) else 1, letter_rank, -(item.get("grade") or 0), approved_at)

    def _default_platform_posts(self, existing: dict | None = None) -> dict:
        current = deepcopy(existing or {})
        for platform in self.PLATFORM_RULES:
            current.setdefault(platform, {
                "state": "not_posted",
                "account_id": "",
                "attempted_at": "",
                "posted_at": "",
                "detail": "",
                "external_url": "",
            })
        return current

    def _ensure_system_accounts(self, state: dict, platform_status: dict | None) -> bool:
        changed = False
        platform_status = platform_status or {}
        for platform, info in platform_status.items():
            if not info.get("configured"):
                continue
            if any(acc.get("platform") == platform and acc.get("system_managed") for acc in state["accounts"]):
                continue
            account = {
                "id": f"{platform}_main",
                "platform": platform,
                "handle": f"integrityproductsusa_{platform}",
                "display_name": f"{platform.title()} main",
                "status": "warming",
                "warmup_day": 1,
                "daily_limit": 0,
                "cooldown_minutes": self.COOLDOWN_MINUTES.get(platform, 60),
                "link_ready": platform in {"pinterest", "youtube"},
                "board_id": info.get("board_id", ""),
                "notes": "Auto-created from configured credentials.",
                "system_managed": True,
                "created_at": _iso_now(),
                "updated_at": _iso_now(),
                "last_post_at": "",
                "activity": {},
            }
            state["accounts"].append(account)
            changed = True
        return changed

    def fetch_approved_feed(self) -> list:
        request = Request(self.feed_url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        return payload.get("products", [])

    def sync_approved_feed(self, platform_status: dict | None = None) -> dict:
        state = self._load_state()
        self._ensure_system_accounts(state, platform_status)
        products = self.fetch_approved_feed()
        queue_index = {item["id"]: item for item in state["queue"]}
        active_ids = set()
        new_count = 0
        updated_count = 0

        for product in products:
            approved_ads = sorted(product.get("approved_ads") or [], key=lambda ad: (-(ad.get("grade") or 0), ad.get("letter", "Z")))
            for ad in approved_ads:
                item_id = self._item_id(product.get("product_id", ""), ad)
                active_ids.add(item_id)
                existing = queue_index.get(item_id, {})
                item = {
                    "id": item_id,
                    "product_id": product.get("product_id", ""),
                    "title": product.get("title", ""),
                    "retail_price": product.get("retail_price", 0),
                    "landing_url": product.get("landing_url", ""),
                    "image_url": ad.get("image_url", ""),
                    "file": ad.get("file", ""),
                    "headline": ad.get("headline", ""),
                    "subline": ad.get("subline", ""),
                    "grade": ad.get("grade", 0),
                    "letter": ad.get("letter", ""),
                    "approved_at": ad.get("approved_at", ""),
                    "video_path": existing.get("video_path", ""),
                    "video_url": existing.get("video_url", ""),
                    "notes": existing.get("notes", ""),
                    "feed_active": True,
                    "created_at": existing.get("created_at", _iso_now()),
                    "updated_at": _iso_now(),
                    "platform_posts": self._default_platform_posts(existing.get("platform_posts")),
                    "history": existing.get("history", [])[-25:],
                    "status": existing.get("status", "ready"),
                }
                if item["status"] == "removed_from_feed":
                    item["status"] = "ready"
                if item["status"] not in {"ready", "posted", "paused"}:
                    item["status"] = "ready"
                item["preferred_platforms"] = self._preferred_platforms(item)
                if item_id in queue_index:
                    updated_count += 1
                else:
                    new_count += 1
                queue_index[item_id] = item

        removed_count = 0
        for item in queue_index.values():
            if item["id"] in active_ids:
                continue
            item["feed_active"] = False
            item["updated_at"] = _iso_now()
            if item.get("status") not in {"posted", "paused"}:
                item["status"] = "removed_from_feed"
            removed_count += 1

        queue = list(queue_index.values())
        queue.sort(key=self._grade_sort)
        state["queue"] = queue
        state["last_sync_at"] = _iso_now()
        state["last_sync_error"] = ""
        self._save_state(state)
        return {
            "ok": True,
            "feed_url": self.feed_url,
            "products": len(products),
            "new_items": new_count,
            "updated_items": updated_count,
            "removed_items": removed_count,
            "queue_items": len(queue),
            "last_sync_at": state["last_sync_at"],
        }

    def list_accounts(self, platform_status: dict | None = None) -> list:
        state = self._load_state()
        if self._ensure_system_accounts(state, platform_status):
            self._save_state(state)
        return sorted(state["accounts"], key=lambda acc: (acc.get("platform", ""), acc.get("handle", "")))

    def upsert_account(self, payload: dict, platform_status: dict | None = None) -> dict:
        platform = (payload.get("platform") or "").strip().lower()
        handle = (payload.get("handle") or "").strip()
        if platform not in self.PLATFORM_RULES:
            raise ValueError(f"Unsupported platform: {platform}")
        if not handle:
            raise ValueError("handle is required")

        state = self._load_state()
        self._ensure_system_accounts(state, platform_status)
        existing = None
        for account in state["accounts"]:
            if payload.get("id") and account.get("id") == payload["id"]:
                existing = account
                break
            if account.get("platform") == platform and account.get("handle") == handle:
                existing = account
                break

        now = _iso_now()
        platform_info = (platform_status or {}).get(platform, {})
        account = existing or {
            "id": payload.get("id") or f"{platform}_{_slug(handle)}",
            "created_at": now,
            "activity": {},
            "last_post_at": "",
        }
        account.update({
            "platform": platform,
            "handle": handle,
            "display_name": payload.get("display_name", account.get("display_name", handle)),
            "status": payload.get("status", account.get("status", "warming")),
            "warmup_day": max(1, int(payload.get("warmup_day", account.get("warmup_day", 1) or 1))),
            "daily_limit": max(0, int(payload.get("daily_limit", account.get("daily_limit", 0) or 0))),
            "cooldown_minutes": max(0, int(payload.get("cooldown_minutes", account.get("cooldown_minutes", self.COOLDOWN_MINUTES.get(platform, 60)) or 0))),
            "link_ready": bool(payload.get("link_ready", account.get("link_ready", platform in {"pinterest", "youtube"}))),
            "board_id": payload.get("board_id", account.get("board_id", platform_info.get("board_id", ""))),
            "notes": payload.get("notes", account.get("notes", "")),
            "system_managed": bool(payload.get("system_managed", account.get("system_managed", False))),
            "updated_at": now,
        })

        if existing is None:
            state["accounts"].append(account)
        state["accounts"] = sorted(state["accounts"], key=lambda acc: (acc.get("platform", ""), acc.get("handle", "")))
        self._save_state(state)
        return account

    def update_queue_item(self, payload: dict) -> dict:
        item_id = payload.get("item_id", "")
        if not item_id:
            raise ValueError("item_id is required")

        state = self._load_state()
        for item in state["queue"]:
            if item.get("id") != item_id:
                continue
            for key in ("video_path", "video_url", "notes"):
                if key in payload:
                    item[key] = payload.get(key, "") or ""
            if "status" in payload:
                requested = payload.get("status", "")
                if requested in {"ready", "paused", "posted", "removed_from_feed"}:
                    item["status"] = requested
            if "preferred_platforms" in payload and isinstance(payload["preferred_platforms"], list):
                item["preferred_platforms"] = [p for p in payload["preferred_platforms"] if p in self.PLATFORM_RULES]
            else:
                item["preferred_platforms"] = self._preferred_platforms(item)
            item["updated_at"] = _iso_now()
            self._save_state(state)
            return item
        raise ValueError(f"queue item not found: {item_id}")

    def list_queue(self) -> list:
        state = self._load_state()
        queue = list(state["queue"])
        queue.sort(key=self._grade_sort)
        return queue

    def status(self, platform_status: dict | None = None) -> dict:
        state = self._load_state()
        if self._ensure_system_accounts(state, platform_status):
            self._save_state(state)
        queue = state["queue"]
        accounts = state["accounts"]
        return {
            "ok": True,
            "feed_url": state.get("feed_url", self.feed_url),
            "last_sync_at": state.get("last_sync_at", ""),
            "last_sync_error": state.get("last_sync_error", ""),
            "queue": {
                "total": len(queue),
                "ready": sum(1 for item in queue if item.get("status") == "ready" and item.get("feed_active", True)),
                "posted": sum(1 for item in queue if item.get("status") == "posted"),
                "paused": sum(1 for item in queue if item.get("status") == "paused"),
                "removed_from_feed": sum(1 for item in queue if item.get("status") == "removed_from_feed"),
            },
            "accounts": {
                "total": len(accounts),
                "by_platform": {
                    platform: sum(1 for account in accounts if account.get("platform") == platform)
                    for platform in self.PLATFORM_RULES
                },
            },
            "platform_rules": deepcopy(self.PLATFORM_RULES),
            "platform_status": platform_status or {},
            "top_ready": [
                {
                    "item_id": item.get("id"),
                    "product_id": item.get("product_id"),
                    "title": item.get("title"),
                    "headline": item.get("headline"),
                    "grade": item.get("grade", 0),
                    "letter": item.get("letter", ""),
                    "preferred_platforms": item.get("preferred_platforms", []),
                }
                for item in queue
                if item.get("status") == "ready" and item.get("feed_active", True)
            ][:10],
        }

    def _preferred_platforms(self, item: dict) -> list:
        preferred = []
        if item.get("image_url") and item.get("landing_url"):
            preferred.extend(["pinterest", "meta"])
        if item.get("video_path"):
            preferred.extend(["youtube", "tiktok"])
        if item.get("video_url") and "youtube" not in preferred:
            preferred.extend(["youtube", "tiktok"])
        seen = []
        for platform in preferred:
            if platform not in seen:
                seen.append(platform)
        return seen

    def _effective_daily_limit(self, account: dict) -> int:
        explicit = int(account.get("daily_limit", 0) or 0)
        if explicit > 0:
            return explicit
        limits = self.WARMUP_LIMITS.get(account.get("platform", ""), [1, 2, 3])
        warmup_day = max(1, int(account.get("warmup_day", 1) or 1))
        return limits[min(warmup_day - 1, len(limits) - 1)]

    def _today_count(self, account: dict) -> int:
        today = _utc_now().date().isoformat()
        return int((account.get("activity") or {}).get(today, 0) or 0)

    def _account_can_post(self, account: dict, platform: str, item: dict, platform_status: dict, reserved: dict) -> tuple[bool, str]:
        if account.get("platform") != platform:
            return False, "wrong platform"
        if account.get("status") not in self.ACTIVE_ACCOUNT_STATES:
            return False, "account paused"
        if not (platform_status.get(platform) or {}).get("configured"):
            return False, "platform not configured"
        if platform == "pinterest" and not (account.get("board_id") or (platform_status.get(platform) or {}).get("board_id")):
            return False, "missing Pinterest board"
        if platform in {"meta", "tiktok"} and not account.get("link_ready"):
            return False, "account link readiness not confirmed"
        if not item.get("feed_active", True):
            return False, "ad removed from approved feed"
        if item.get("status") not in {"ready", "posted"}:
            return False, f"item status={item.get('status')}"
        if self._platform_state(item, platform) == "posted":
            return False, "already posted"
        for field in self.PLATFORM_RULES[platform]["requires"]:
            if not item.get(field):
                return False, f"missing {field}"
        daily_limit = self._effective_daily_limit(account)
        reserved_count = reserved.get(account.get("id"), 0)
        if self._today_count(account) + reserved_count >= daily_limit:
            return False, "daily warmup limit reached"
        cooldown_minutes = int(account.get("cooldown_minutes", 0) or 0)
        last_post = _parse_dt(account.get("last_post_at"))
        if cooldown_minutes > 0 and last_post:
            elapsed = (_utc_now() - last_post).total_seconds() / 60.0
            if elapsed < cooldown_minutes:
                return False, f"cooldown {cooldown_minutes - int(elapsed)}m remaining"
        return True, ""

    def _platform_state(self, item: dict, platform: str) -> str:
        return ((item.get("platform_posts") or {}).get(platform) or {}).get("state", "not_posted")

    def _pick_account(self, accounts: list, platform: str, item: dict, platform_status: dict, reserved: dict) -> tuple[dict | None, str]:
        candidates = [account for account in accounts if account.get("platform") == platform]
        if not candidates:
            return None, "no account registered"
        candidates.sort(key=lambda account: (
            0 if account.get("status") == "active" else 1,
            self._today_count(account) + reserved.get(account.get("id"), 0),
            account.get("handle", ""),
        ))
        reasons = []
        for account in candidates:
            ok, reason = self._account_can_post(account, platform, item, platform_status, reserved)
            if ok:
                return account, ""
            if reason:
                reasons.append(reason)
        return None, "; ".join(sorted(set(reasons))) if reasons else "no eligible account"

    def _build_payload(self, item: dict, platform: str, account: dict, platform_status: dict) -> dict:
        title = (item.get("headline") or item.get("title") or "")[:100]
        subline = item.get("subline", "")
        landing_url = item.get("landing_url", "")
        if platform == "pinterest":
            return {
                "title": title,
                "description": subline[:500],
                "image_url": item.get("image_url", ""),
                "link": landing_url,
                "board_id": account.get("board_id") or (platform_status.get("pinterest") or {}).get("board_id", ""),
            }
        if platform == "youtube":
            body = "\n\n".join(part for part in [subline, landing_url] if part)
            return {
                "video_path": item.get("video_path", ""),
                "title": title,
                "description": body,
                "tags": ["IntegrityProductsUSA", _slug(item.get("product_id", ""))],
            }
        if platform == "tiktok":
            caption = " ".join(part for part in [title, landing_url if account.get("link_ready") else ""] if part).strip()
            return {
                "video_path": item.get("video_path", ""),
                "title": title,
                "description": subline,
                "caption": caption[:150],
            }
        if platform == "meta":
            caption = "\n\n".join(part for part in [title, subline, landing_url] if part)
            return {
                "image_url": item.get("image_url", ""),
                "caption": caption[:2200],
            }
        return {}

    def plan_posts(self, platform_status: dict | None = None, platforms: list | None = None, limit: int = 10) -> dict:
        state = self._load_state()
        self._ensure_system_accounts(state, platform_status)
        accounts = state["accounts"]
        queue = sorted(state["queue"], key=self._grade_sort)
        selected_platforms = [p for p in (platforms or list(self.PLATFORM_RULES.keys())) if p in self.PLATFORM_RULES]
        reserved: dict[str, int] = {}
        candidates = []
        blocked = []

        for item in queue:
            if len(candidates) >= limit:
                break
            if item.get("status") != "ready" or not item.get("feed_active", True):
                continue
            item_platforms = item.get("preferred_platforms") or self._preferred_platforms(item)
            for platform in selected_platforms:
                if len(candidates) >= limit:
                    break
                if platform not in item_platforms:
                    continue
                account, reason = self._pick_account(accounts, platform, item, platform_status or {}, reserved)
                if account is None:
                    blocked.append({
                        "item_id": item.get("id"),
                        "platform": platform,
                        "title": item.get("title"),
                        "reason": reason,
                    })
                    continue
                payload = self._build_payload(item, platform, account, platform_status or {})
                if not payload:
                    blocked.append({
                        "item_id": item.get("id"),
                        "platform": platform,
                        "title": item.get("title"),
                        "reason": "payload build failed",
                    })
                    continue
                reserved[account["id"]] = reserved.get(account["id"], 0) + 1
                candidates.append({
                    "item_id": item.get("id"),
                    "product_id": item.get("product_id"),
                    "title": item.get("title"),
                    "headline": item.get("headline"),
                    "platform": platform,
                    "account_id": account.get("id"),
                    "account_handle": account.get("handle"),
                    "grade": item.get("grade", 0),
                    "letter": item.get("letter", ""),
                    "payload": payload,
                })

        if state != self._load_state():
            self._save_state(state)
        return {
            "ok": True,
            "planned": len(candidates),
            "candidates": candidates,
            "blocked": blocked[:50],
        }

    def run(self, dispatch_fn, platform_status: dict | None = None, platforms: list | None = None,
            limit: int = 10, dry_run: bool = True) -> dict:
        sync = self.sync_approved_feed(platform_status=platform_status)
        plan = self.plan_posts(platform_status=platform_status, platforms=platforms, limit=limit)
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "sync": sync,
                "planned": plan["planned"],
                "candidates": plan["candidates"],
                "blocked": plan["blocked"],
            }

        state = self._load_state()
        queue_index = {item["id"]: item for item in state["queue"]}
        accounts = {account["id"]: account for account in state["accounts"]}
        results = []

        for candidate in plan["candidates"]:
            item = queue_index.get(candidate["item_id"])
            account = accounts.get(candidate["account_id"])
            if not item or not account:
                continue
            response, status_code = dispatch_fn(candidate["platform"], candidate["payload"])
            success = status_code < 400 and response.get("status") == "posted"
            now = _iso_now()
            platform_post = item["platform_posts"].setdefault(candidate["platform"], {})
            platform_post.update({
                "state": "posted" if success else "failed",
                "account_id": candidate["account_id"],
                "attempted_at": now,
                "posted_at": now if success else "",
                "detail": response.get("error") or response.get("message") or response.get("status", ""),
                "external_url": response.get("pin_url")
                                or response.get("url")
                                or ((response.get("result") or {}).get("id", "")),
            })
            item["history"] = (item.get("history") or [])[-24:] + [{
                "platform": candidate["platform"],
                "account_id": candidate["account_id"],
                "attempted_at": now,
                "status": "posted" if success else "failed",
                "status_code": status_code,
                "detail": platform_post["detail"],
            }]
            item["updated_at"] = now
            if success:
                item["status"] = "posted" if all(
                    item["platform_posts"].get(platform_name, {}).get("state") == "posted"
                    or platform_name not in (item.get("preferred_platforms") or [])
                    for platform_name in self.PLATFORM_RULES
                ) else "ready"
                today = _utc_now().date().isoformat()
                account.setdefault("activity", {})
                account["activity"][today] = int(account["activity"].get(today, 0) or 0) + 1
                account["last_post_at"] = now
                account["updated_at"] = now
            results.append({
                "item_id": candidate["item_id"],
                "platform": candidate["platform"],
                "account_id": candidate["account_id"],
                "status": "posted" if success else "failed",
                "status_code": status_code,
                "response": response,
            })

        state["queue"] = sorted(queue_index.values(), key=self._grade_sort)
        state["accounts"] = sorted(accounts.values(), key=lambda acc: (acc.get("platform", ""), acc.get("handle", "")))
        self._save_state(state)
        return {
            "ok": True,
            "dry_run": False,
            "sync": sync,
            "planned": plan["planned"],
            "executed": len(results),
            "results": results,
            "blocked": plan["blocked"],
        }
