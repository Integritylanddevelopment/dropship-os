"""
automation/pinterest_browser.py — Pinterest browser automation
Handles login, pin creation, board management, research scraping.
Replaces with official Pinterest API v5 once credentials are configured.
"""

import asyncio
import json
import random
from typing import Optional
from pathlib import Path
from loguru import logger

from .browser import BasePlatformAutomation, HumanBehavior

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config


class PinterestBrowserAutomation(BasePlatformAutomation):
    """
    Browser-based Pinterest automation.
    All methods have API equivalents in api_stubs/pinterest_api.py.
    """

    BASE_URL = "https://www.pinterest.com"

    def __init__(self, profile_name: str = "pinterest_main"):
        super().__init__(profile_name)
        self._logged_in = False

    # ─────────────────────────────────────────────
    # AUTHENTICATION
    # ─────────────────────────────────────────────

    async def login(self, email: str, password: str) -> bool:
        """Log into Pinterest"""
        logger.info(f"Logging into Pinterest as {email}")

        await self.navigate("https://www.pinterest.com/login/")
        await asyncio.sleep(3)

        try:
            # Fill email
            await self.fill_field("#email", email)
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Fill password
            await self.fill_field("#password", password)
            await asyncio.sleep(1)

            # Submit
            await self.wait_and_click("button[type='submit']")
            await asyncio.sleep(4)

            # Verify
            if "pinterest.com" in self._page.url and "login" not in self._page.url:
                self._logged_in = True
                logger.info("✅ Logged into Pinterest")
                return True

            logger.error("Pinterest login failed")
            return False

        except Exception as e:
            logger.error(f"Pinterest login error: {e}")
            return False

    # ─────────────────────────────────────────────
    # RESEARCH: KEYWORD AND COMPETITOR ANALYSIS
    # ─────────────────────────────────────────────

    async def search_keyword(self, keyword: str) -> dict:
        """
        Search Pinterest for a keyword and analyze what comes up.
        Returns top pins data for competitive intel.
        """
        logger.info(f"Searching Pinterest for: {keyword}")

        search_url = f"https://www.pinterest.com/search/pins/?q={keyword.replace(' ', '+')}"
        await self.navigate(search_url)
        await asyncio.sleep(3)

        # Scroll to load pins
        for _ in range(3):
            await self.human.scroll_naturally(self._page, "down", 600)
            await asyncio.sleep(2)

        pins = []
        try:
            # Extract pin data from DOM
            pin_data = await self._page.evaluate("""
                () => {
                    const pins = [];
                    const pinElements = document.querySelectorAll('[data-test-id="pin"]');
                    pinElements.forEach((pin, i) => {
                        if (i >= 30) return;
                        const title = pin.querySelector('div[data-test-id="pin-title"]')?.innerText || '';
                        const desc = pin.querySelector('span')?.innerText || '';
                        const img = pin.querySelector('img')?.src || '';
                        const link = pin.querySelector('a')?.href || '';
                        if (title || desc) {
                            pins.push({ title, description: desc.slice(0, 200), image: img, link });
                        }
                    });
                    return pins;
                }
            """)
            pins = pin_data
        except Exception as e:
            logger.error(f"Pin extraction failed: {e}")

        return {
            "keyword": keyword,
            "url": search_url,
            "pins_found": len(pins),
            "top_pins": pins[:20],
        }

    async def get_keyword_suggestions(self, seed_keyword: str) -> list:
        """
        Use Pinterest's autocomplete to find related keyword suggestions.
        This is one of the best Pinterest SEO research tools.
        """
        logger.info(f"Getting keyword suggestions for: {seed_keyword}")

        await self.navigate("https://www.pinterest.com")
        await asyncio.sleep(2)

        suggestions = []
        try:
            # Click search bar
            search_bar = await self._page.query_selector("[data-test-id='search-box-input'], input[name='searchBoxInput']")
            if search_bar:
                await search_bar.click()
                await asyncio.sleep(0.5)
                await self.human.human_type(self._page, "[data-test-id='search-box-input'], input[name='searchBoxInput']", seed_keyword)
                await asyncio.sleep(2)

                # Extract autocomplete suggestions
                suggestion_data = await self._page.evaluate("""
                    () => {
                        const items = document.querySelectorAll('[data-test-id="typeahead-item"]');
                        const results = [];
                        items.forEach(item => {
                            const text = item.innerText.trim();
                            if (text) results.push(text);
                        });
                        return results;
                    }
                """)
                suggestions = suggestion_data or []

        except Exception as e:
            logger.error(f"Keyword suggestions failed: {e}")

        logger.info(f"Found {len(suggestions)} keyword suggestions for '{seed_keyword}'")
        return suggestions

    async def analyze_competitor_boards(self, competitor_username: str) -> dict:
        """Analyze a competitor's boards and pin strategy"""
        logger.info(f"Analyzing competitor: {competitor_username}")

        await self.navigate(f"https://www.pinterest.com/{competitor_username}/_boards/")
        await asyncio.sleep(3)

        boards = []
        try:
            board_data = await self._page.evaluate("""
                () => {
                    const boards = [];
                    const boardElements = document.querySelectorAll('[data-test-id="board"]');
                    boardElements.forEach((board, i) => {
                        if (i >= 20) return;
                        const name = board.querySelector('div[title]')?.getAttribute('title') ||
                                     board.querySelector('[data-test-id="board-name"]')?.innerText || '';
                        const count = board.querySelector('span')?.innerText || '';
                        if (name) boards.push({ name, pin_count: count });
                    });
                    return boards;
                }
            """)
            boards = board_data or []
        except Exception as e:
            logger.error(f"Board analysis failed: {e}")

        return {
            "username": competitor_username,
            "boards": boards,
            "board_count": len(boards),
        }

    async def research_trending_topics(self, category: str = None) -> list:
        """Get trending topics from Pinterest's trending section"""
        url = "https://www.pinterest.com/today/"
        if category:
            url = f"https://www.pinterest.com/today/#category={category}"

        await self.navigate(url)
        await asyncio.sleep(3)

        trends = []
        try:
            trend_data = await self._page.evaluate("""
                () => {
                    const items = [];
                    const elements = document.querySelectorAll('[data-test-id="trending-topic"], h3, [class*="trending"]');
                    elements.forEach(el => {
                        const text = el.innerText.trim();
                        if (text && text.length > 2 && text.length < 100) items.push(text);
                    });
                    return [...new Set(items)].slice(0, 20);
                }
            """)
            trends = trend_data or []
        except Exception as e:
            logger.error(f"Trending topics scrape failed: {e}")

        return trends

    # ─────────────────────────────────────────────
    # BOARD MANAGEMENT (requires login)
    # ─────────────────────────────────────────────

    async def create_board(
        self,
        name: str,
        description: str,
        is_secret: bool = False
    ) -> Optional[str]:
        """Create a new Pinterest board"""
        if not self._logged_in:
            logger.error("Not logged in")
            return None

        logger.info(f"Creating board: {name}")

        try:
            await self.navigate("https://www.pinterest.com/")
            await asyncio.sleep(2)

            # Click create button
            create_btn = await self._page.query_selector("[data-test-id='header-create-button'], button[aria-label='Create']")
            if create_btn:
                await create_btn.click()
                await asyncio.sleep(1)

            # Select "Board" option
            board_option = await self._page.query_selector("[data-test-id='create-board-button']")
            if board_option:
                await board_option.click()
                await asyncio.sleep(1)

            # Fill board name
            await self.fill_field("[name='boardName'], input[placeholder*='Name']", name)
            await asyncio.sleep(0.8)

            # Make secret if needed
            if is_secret:
                secret_toggle = await self._page.query_selector("[data-test-id='board-secret-toggle']")
                if secret_toggle:
                    await secret_toggle.click()

            # Submit
            create_submit = await self._page.query_selector("button:has-text('Create')")
            if create_submit:
                await create_submit.click()
                await asyncio.sleep(3)

                # Add description
                if description:
                    desc_field = await self._page.query_selector("textarea[placeholder*='description']")
                    if desc_field:
                        await self.fill_field("textarea[placeholder*='description']", description)
                        await asyncio.sleep(0.5)
                        save_btn = await self._page.query_selector("button:has-text('Save')")
                        if save_btn:
                            await save_btn.click()
                            await asyncio.sleep(2)

                board_url = self._page.url
                logger.info(f"✅ Board created: {board_url}")
                return board_url

        except Exception as e:
            logger.error(f"Board creation failed: {e}")
            await self.browser.screenshot()

        return None

    # ─────────────────────────────────────────────
    # PIN CREATION (requires login)
    # ─────────────────────────────────────────────

    async def create_pin(
        self,
        board_name: str,
        title: str,
        description: str,
        destination_url: str,
        image_path: str = None,
        image_url: str = None
    ) -> Optional[str]:
        """
        Create a new pin on a board.
        Provide either image_path (local file) or image_url (remote image).
        """
        if not self._logged_in:
            logger.error("Not logged in")
            return None

        logger.info(f"Creating pin: {title[:50]} → {board_name}")

        try:
            await self.navigate("https://www.pinterest.com/pin-creation-tool/")
            await asyncio.sleep(3)

            # Upload or set image
            if image_path and Path(image_path).exists():
                file_input = await self._page.query_selector("input[type='file']")
                if file_input:
                    await file_input.set_input_files(image_path)
                    await asyncio.sleep(3)
            elif image_url:
                # Use URL upload option
                url_option = await self._page.query_selector("button:has-text('Save from site'), [data-test-id='pin-builder-url-input']")
                if url_option:
                    await url_option.click()
                    await asyncio.sleep(1)
                    await self.fill_field("[data-test-id='pin-builder-url-input'], input[placeholder*='site']", image_url)
                    await asyncio.sleep(1)

            # Fill title
            title_field = await self._page.query_selector("[data-test-id='pin-builder-title'], input[placeholder*='title']")
            if title_field:
                await self.fill_field("[data-test-id='pin-builder-title'], input[placeholder*='title']", title[:100])
                await asyncio.sleep(0.8)

            # Fill description
            desc_field = await self._page.query_selector("[data-test-id='pin-builder-description'], textarea[placeholder*='description']")
            if desc_field:
                await self.fill_field(
                    "[data-test-id='pin-builder-description'], textarea[placeholder*='description']",
                    description[:500]
                )
                await asyncio.sleep(0.8)

            # Set destination URL
            link_field = await self._page.query_selector("[data-test-id='pin-builder-link'], input[placeholder*='Destination']")
            if link_field:
                await self.fill_field(
                    "[data-test-id='pin-builder-link'], input[placeholder*='Destination']",
                    destination_url
                )
                await asyncio.sleep(0.8)

            # Select board
            board_selector = await self._page.query_selector("[data-test-id='pin-builder-board-selector'], button[data-test-id='board-dropdown']")
            if board_selector:
                await board_selector.click()
                await asyncio.sleep(1)

                # Search for or select the board
                board_search = await self._page.query_selector("input[placeholder*='Search boards']")
                if board_search:
                    await self.fill_field("input[placeholder*='Search boards']", board_name)
                    await asyncio.sleep(1)

                board_option = await self._page.query_selector(f"[data-test-id='board-option']:has-text('{board_name}')")
                if board_option:
                    await board_option.click()
                    await asyncio.sleep(1)

            # Publish
            publish_btn = await self._page.query_selector("button[data-test-id='board-dropdown-save-button'], button:has-text('Publish')")
            if publish_btn:
                await publish_btn.click()
                await asyncio.sleep(4)

                pin_url = self._page.url
                if "/pin/" in pin_url:
                    logger.info(f"✅ Pin created: {pin_url}")
                    return pin_url

        except Exception as e:
            logger.error(f"Pin creation failed: {e}")
            await self.browser.screenshot()

        return None

    async def get_pin_analytics(self, pin_url: str) -> dict:
        """Get performance metrics for a pin"""
        if not self._logged_in:
            return {}

        try:
            await self.navigate(pin_url)
            await asyncio.sleep(2)

            analytics = await self._page.evaluate("""
                () => {
                    const stats = {};
                    const elements = document.querySelectorAll('[data-test-id*="stat"], [class*="analytics"]');
                    elements.forEach(el => {
                        const text = el.innerText;
                        if (text) stats[el.getAttribute('data-test-id') || 'unknown'] = text;
                    });
                    return stats;
                }
            """)
            return analytics or {}
        except Exception as e:
            logger.error(f"Pin analytics fetch failed: {e}")
            return {}
