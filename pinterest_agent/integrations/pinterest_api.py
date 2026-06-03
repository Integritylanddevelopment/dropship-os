"""
Pinterest AI Agent — Pinterest API v5 Integration
Handles all Pinterest API calls: boards, pins, analytics, user account.
"""
import requests
import time
import json
from typing import Optional, Any
from datetime import datetime


class PinterestAPIError(Exception):
    def __init__(self, status_code: int, message: str, endpoint: str = ""):
        self.status_code = status_code
        self.endpoint = endpoint
        super().__init__(f"Pinterest API Error {status_code} on {endpoint}: {message}")


class PinterestAPI:
    BASE_URL = "https://api.pinterest.com/v5"
    RATE_LIMIT_DELAY = 0.5  # seconds between requests

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self._last_request_time = 0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        self._rate_limit()
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.request(method, url, **kwargs)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"⚠️  Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            return self._request(method, endpoint, **kwargs)

        if response.status_code not in (200, 201, 204):
            error_msg = response.text
            try:
                error_msg = response.json().get("message", response.text)
            except Exception:
                pass
            raise PinterestAPIError(response.status_code, error_msg, endpoint)

        if response.status_code == 204:
            return {}

        return response.json()

    # =========================================================
    # USER ACCOUNT
    # =========================================================
    def get_user_account(self) -> dict:
        """Get authenticated user's Pinterest account info."""
        return self._request("GET", "/user_account")

    def get_account_analytics(
        self,
        start_date: str,
        end_date: str,
        metrics: list[str] = None
    ) -> dict:
        """
        Get account-level analytics.
        metrics: ENGAGEMENT, ENGAGEMENT_RATE, IMPRESSION, OUTBOUND_CLICK,
                 OUTBOUND_CLICK_RATE, PIN_CLICK, PIN_CLICK_RATE, SAVE, SAVE_RATE
        """
        if metrics is None:
            metrics = ["IMPRESSION", "SAVE", "PIN_CLICK", "OUTBOUND_CLICK"]
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "metric_types": ",".join(metrics),
        }
        return self._request("GET", "/user_account/analytics", params=params)

    # =========================================================
    # BOARDS
    # =========================================================
    def list_boards(self, page_size: int = 50) -> list[dict]:
        """List all boards for the authenticated user."""
        boards = []
        bookmark = None
        while True:
            params = {"page_size": page_size}
            if bookmark:
                params["bookmark"] = bookmark
            data = self._request("GET", "/boards", params=params)
            boards.extend(data.get("items", []))
            bookmark = data.get("bookmark")
            if not bookmark:
                break
        return boards

    def get_board(self, board_id: str) -> dict:
        """Get a specific board by ID."""
        return self._request("GET", f"/boards/{board_id}")

    def create_board(
        self,
        name: str,
        description: str = "",
        privacy: str = "PUBLIC"
    ) -> dict:
        """
        Create a new Pinterest board.
        privacy: PUBLIC or SECRET
        """
        payload = {
            "name": name,
            "description": description,
            "privacy": privacy,
        }
        return self._request("POST", "/boards", json=payload)

    def update_board(self, board_id: str, updates: dict) -> dict:
        """Update board name or description."""
        return self._request("PATCH", f"/boards/{board_id}", json=updates)

    def delete_board(self, board_id: str) -> dict:
        """Delete a board (use with caution)."""
        return self._request("DELETE", f"/boards/{board_id}")

    def list_board_pins(self, board_id: str, page_size: int = 50) -> list[dict]:
        """List all pins on a specific board."""
        pins = []
        bookmark = None
        while True:
            params = {"page_size": page_size}
            if bookmark:
                params["bookmark"] = bookmark
            data = self._request("GET", f"/boards/{board_id}/pins", params=params)
            pins.extend(data.get("items", []))
            bookmark = data.get("bookmark")
            if not bookmark:
                break
        return pins

    # =========================================================
    # PINS
    # =========================================================
    def create_pin(
        self,
        board_id: str,
        title: str,
        description: str,
        link: str,
        image_url: str = None,
        alt_text: str = None,
        dominant_color: str = None,
    ) -> dict:
        """
        Create a new Pinterest pin.
        image_url: Direct URL to the image (must be publicly accessible)
        """
        payload = {
            "board_id": board_id,
            "title": title,
            "description": description,
            "link": link,
        }
        if image_url:
            payload["media_source"] = {
                "source_type": "image_url",
                "url": image_url,
            }
        if alt_text:
            payload["alt_text"] = alt_text
        if dominant_color:
            payload["dominant_color"] = dominant_color

        return self._request("POST", "/pins", json=payload)

    def create_pin_from_local(
        self,
        board_id: str,
        title: str,
        description: str,
        link: str,
        image_base64: str,
        content_type: str = "image/jpeg",
    ) -> dict:
        """Create a pin using a base64-encoded image."""
        payload = {
            "board_id": board_id,
            "title": title,
            "description": description,
            "link": link,
            "media_source": {
                "source_type": "image_base64",
                "content_type": content_type,
                "data": image_base64,
            },
        }
        return self._request("POST", "/pins", json=payload)

    def get_pin(self, pin_id: str) -> dict:
        """Get a specific pin by ID."""
        return self._request("GET", f"/pins/{pin_id}")

    def update_pin(self, pin_id: str, updates: dict) -> dict:
        """Update a pin's title, description, or link."""
        return self._request("PATCH", f"/pins/{pin_id}", json=updates)

    def delete_pin(self, pin_id: str) -> dict:
        """Delete a pin."""
        return self._request("DELETE", f"/pins/{pin_id}")

    def save_pin_to_board(self, pin_id: str, board_id: str) -> dict:
        """Save an existing pin to a board."""
        payload = {"board_id": board_id}
        return self._request("POST", f"/pins/{pin_id}/save", json=payload)

    # =========================================================
    # PIN ANALYTICS
    # =========================================================
    def get_pin_analytics(
        self,
        pin_id: str,
        start_date: str,
        end_date: str,
        metrics: list[str] = None,
    ) -> dict:
        """
        Get analytics for a specific pin.
        metrics: IMPRESSION, SAVE, PIN_CLICK, OUTBOUND_CLICK, VIDEO_MRC_VIEW, etc.
        """
        if metrics is None:
            metrics = ["IMPRESSION", "SAVE", "PIN_CLICK", "OUTBOUND_CLICK"]
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "metric_types": ",".join(metrics),
            "app_types": "ALL",
        }
        return self._request("GET", f"/pins/{pin_id}/analytics", params=params)

    def get_pins_analytics_bulk(
        self,
        pin_ids: list[str],
        start_date: str,
        end_date: str,
    ) -> dict:
        """Get analytics for multiple pins. Returns dict keyed by pin_id."""
        results = {}
        for pid in pin_ids:
            try:
                results[pid] = self.get_pin_analytics(pid, start_date, end_date)
            except PinterestAPIError as e:
                results[pid] = {"error": str(e)}
        return results

    # =========================================================
    # PINTEREST TRENDS (Business accounts)
    # =========================================================
    def get_trending_keywords(
        self,
        region: str = "US",
        trend_type: str = "weekly",
        limit: int = 50,
    ) -> list[dict]:
        """
        Get trending keywords on Pinterest.
        trend_type: weekly, monthly, yearly, growing
        """
        params = {
            "region": region,
            "trend_type": trend_type,
            "limit": limit,
            "include_keywords": True,
            "normalize_against_group": False,
        }
        try:
            data = self._request("GET", "/trends/keywords", params=params)
            return data.get("trends", [])
        except PinterestAPIError:
            # Trends API requires special access
            return []

    def get_keyword_suggestions(self, query: str, limit: int = 20) -> list[str]:
        """
        Suggest related keywords for a given query.
        Uses the keywords/get endpoint for suggestions.
        """
        params = {
            "query": query,
            "limit": limit,
        }
        try:
            data = self._request("GET", "/keywords/get", params=params)
            return [kw["keyword"] for kw in data.get("items", [])]
        except PinterestAPIError:
            return []

    # =========================================================
    # UTILITY
    # =========================================================
    def test_connection(self) -> bool:
        """Test that the API token is valid."""
        try:
            user = self.get_user_account()
            print(f"✅ Pinterest API connected as: {user.get('username', 'Unknown')}")
            return True
        except PinterestAPIError as e:
            print(f"❌ Pinterest API connection failed: {e}")
            return False

    def get_board_id_by_name(self, board_name: str) -> Optional[str]:
        """Find a board ID by name (case-insensitive)."""
        boards = self.list_boards()
        for board in boards:
            if board.get("name", "").lower() == board_name.lower():
                return board["id"]
        return None

    def format_date(self, dt: datetime = None) -> str:
        """Format a datetime as YYYY-MM-DD for API calls."""
        if dt is None:
            dt = datetime.now()
        return dt.strftime("%Y-%m-%d")
