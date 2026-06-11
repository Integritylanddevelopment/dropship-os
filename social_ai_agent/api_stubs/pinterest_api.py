"""
api_stubs/pinterest_api.py — Official Pinterest API v5
STUB: Ready to activate once you add Pinterest credentials to .env

To activate:
1. Go to https://developers.pinterest.com
2. Create an app
3. Get your access token (OAuth 2.0)
4. Add credentials to .env
5. Change PINTEREST_MODE=api in .env

Docs: https://developers.pinterest.com/docs/api/v5/
"""

from loguru import logger
from typing import Optional
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class PinterestAPI:
    """
    Official Pinterest API v5 wrapper.
    Same interface as PinterestBrowserAutomation so you can swap seamlessly.
    """

    BASE_URL = "https://api.pinterest.com/v5"

    def __init__(self):
        self.access_token = config.pinterest_api.access_token
        self._headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _check_ready(self) -> bool:
        if not config.pinterest_api.is_configured:
            logger.error("Pinterest API not configured. Add credentials to .env")
            return False
        return True

    async def _get(self, endpoint: str, params: dict = None) -> dict:
        if not self._check_ready():
            return {}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.BASE_URL}{endpoint}",
                    headers=self._headers,
                    params=params,
                    timeout=15,
                )
                return resp.json()
        except Exception as e:
            logger.error(f"Pinterest API GET failed: {endpoint} — {e}")
            return {}

    async def _post(self, endpoint: str, data: dict) -> dict:
        if not self._check_ready():
            return {}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.BASE_URL}{endpoint}",
                    headers=self._headers,
                    json=data,
                    timeout=15,
                )
                return resp.json()
        except Exception as e:
            logger.error(f"Pinterest API POST failed: {endpoint} — {e}")
            return {}

    # ─────────────────────────────────────────────
    # BOARDS
    # ─────────────────────────────────────────────

    async def get_boards(self) -> list:
        """Get all boards for the authenticated user"""
        data = await self._get("/boards")
        return data.get("items", [])

    async def create_board(self, name: str, description: str = "", privacy: str = "PUBLIC") -> Optional[dict]:
        """Create a new board"""
        result = await self._post("/boards", {
            "name": name,
            "description": description,
            "privacy": privacy,
        })
        if result.get("id"):
            logger.info(f"✅ Board created via API: {result.get('id')}")
        return result

    async def get_board_pins(self, board_id: str, limit: int = 25) -> list:
        """Get pins from a board"""
        data = await self._get(f"/boards/{board_id}/pins", {"page_size": limit})
        return data.get("items", [])

    # ─────────────────────────────────────────────
    # PINS
    # ─────────────────────────────────────────────

    async def create_pin(
        self,
        board_id: str,
        title: str,
        description: str,
        link: str,
        image_url: str = None,
        alt_text: str = None,
    ) -> Optional[dict]:
        """Create a new pin via API"""
        payload = {
            "board_id": board_id,
            "title": title[:100],
            "description": description[:500],
            "link": link,
        }

        if image_url:
            payload["media_source"] = {
                "source_type": "image_url",
                "url": image_url,
            }

        if alt_text:
            payload["alt_text"] = alt_text

        result = await self._post("/pins", payload)
        if result.get("id"):
            logger.info(f"✅ Pin created via API: {result.get('id')}")
        return result

    async def get_pin_analytics(self, pin_id: str, metric_types: list = None) -> dict:
        """Get analytics for a pin"""
        if not metric_types:
            metric_types = ["IMPRESSION", "SAVE", "OUTBOUND_CLICK", "PIN_CLICK"]

        params = {
            "metric_types": ",".join(metric_types),
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
            "app_types": "ALL",
        }
        return await self._get(f"/pins/{pin_id}/analytics", params)

    # ─────────────────────────────────────────────
    # ACCOUNT & ANALYTICS
    # ─────────────────────────────────────────────

    async def get_user_account(self) -> dict:
        """Get authenticated user's account info"""
        return await self._get("/user_account")

    async def get_user_analytics(self, metric_types: list = None) -> dict:
        """Get overall account analytics"""
        if not metric_types:
            metric_types = ["IMPRESSION", "SAVE", "OUTBOUND_CLICK", "PIN_CLICK"]
        params = {
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
            "metric_types": ",".join(metric_types),
        }
        return await self._get("/user_account/analytics", params)

    async def search_pins(self, query: str, limit: int = 25) -> list:
        """Search for pins (requires search scope)"""
        data = await self._get("/search/pins", {"query": query, "page_size": limit})
        return data.get("items", [])

    # ─────────────────────────────────────────────
    # KEYWORD RESEARCH (Pinterest Ads API)
    # ─────────────────────────────────────────────

    async def get_keyword_suggestions(self, keyword: str, ad_account_id: str = None) -> list:
        """
        Get keyword suggestions from Pinterest Ads API.
        Requires ad account access.
        """
        if not ad_account_id:
            logger.warning("Keyword suggestions require an ad account ID")
            return []

        data = await self._get(
            f"/ad_accounts/{ad_account_id}/keywords/suggestions",
            {"keyword": keyword}
        )
        return data.get("keywords", [])

    async def get_trending_keywords(self, region: str = "US", limit: int = 50) -> list:
        """Get trending keywords in a region"""
        data = await self._get("/trends/keywords/search", {
            "region": region,
            "kind": "growing",
            "limit": limit,
        })
        return data.get("trends", [])
