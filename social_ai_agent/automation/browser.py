"""
automation/browser.py — Base browser automation layer (Playwright)
Handles human-like behavior: random delays, scroll patterns, mouse movements.
Swap for official APIs by changing mode in config.
"""

import asyncio
import random
from typing import Optional
from pathlib import Path
from loguru import logger

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Run: playwright install chromium")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config


class HumanBehavior:
    """Injects realistic human-like timing and patterns into automation"""

    @staticmethod
    async def random_delay(min_ms: int = 500, max_ms: int = 2500):
        """Random delay between actions"""
        delay = random.uniform(min_ms / 1000, max_ms / 1000)
        await asyncio.sleep(delay)

    @staticmethod
    async def reading_pause(text_length: int = 500):
        """Pause as if reading — scales with content length"""
        reading_time = min(text_length * 0.003, 8.0)
        reading_time = max(reading_time, 1.5)
        jitter = random.uniform(0.8, 1.3)
        await asyncio.sleep(reading_time * jitter)

    @staticmethod
    async def typing_delay():
        """Pause between typing bursts"""
        await asyncio.sleep(random.uniform(0.05, 0.18))

    @staticmethod
    async def human_type(page: "Page", selector: str, text: str):
        """Type text character by character with realistic timing"""
        await page.click(selector)
        await asyncio.sleep(random.uniform(0.3, 0.8))

        for i, char in enumerate(text):
            await page.keyboard.type(char)
            # Occasional pause (thinking)
            if i % random.randint(15, 40) == 0 and i > 0:
                await asyncio.sleep(random.uniform(0.3, 1.2))
            else:
                await asyncio.sleep(random.uniform(0.04, 0.14))

    @staticmethod
    async def scroll_naturally(page: "Page", direction: str = "down", distance: int = None):
        """Scroll in a natural pattern"""
        if distance is None:
            distance = random.randint(200, 600)

        if direction == "down":
            await page.mouse.wheel(0, distance)
        else:
            await page.mouse.wheel(0, -distance)

        await asyncio.sleep(random.uniform(0.5, 1.5))

    @staticmethod
    async def move_mouse_naturally(page: "Page", target_x: int = None, target_y: int = None):
        """Move mouse to element with slight curve"""
        vw = config.browser.viewport_width
        vh = config.browser.viewport_height
        x = target_x or random.randint(100, vw - 100)
        y = target_y or random.randint(100, vh - 100)

        # Move through an intermediate point
        mid_x = x + random.randint(-50, 50)
        mid_y = y + random.randint(-50, 50)

        await page.mouse.move(mid_x, mid_y)
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await page.mouse.move(x, y)


class BrowserManager:
    """
    Manages Playwright browser lifecycle.
    Uses persistent context to maintain session/cookies across runs.
    """

    def __init__(self, profile_name: str = "default"):
        self.profile_name = profile_name
        self.profile_dir = Path(config.browser.user_data_dir) / profile_name
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def start(self) -> "Page":
        """Launch browser with persistent context"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")

        logger.info(f"Starting browser (profile: {self.profile_name}, headless: {config.browser.headless})")

        self._playwright = await async_playwright().start()

        # Use persistent context to maintain login state
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=config.browser.headless,
            slow_mo=config.browser.slow_mo,
            viewport={"width": config.browser.viewport_width, "height": config.browser.viewport_height},
            user_agent=random.choice(config.browser.user_agents),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_https_errors=True,
        )

        # Remove webdriver fingerprint
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """)

        self._page = await self._context.new_page()

        # Block tracking and ads to reduce fingerprinting noise
        await self._page.route("**/*", self._handle_route)

        logger.info("Browser started successfully")
        return self._page

    async def _handle_route(self, route):
        """Block unnecessary requests"""
        blocked = ["google-analytics", "doubleclick", "facebook.com/tr", "hotjar"]
        if any(b in route.request.url for b in blocked):
            await route.abort()
        else:
            await route.continue_()

    async def get_page(self) -> "Page":
        if self._page:
            return self._page
        return await self.start()

    async def new_tab(self) -> "Page":
        """Open a new tab"""
        if not self._context:
            await self.start()
        return await self._context.new_page()

    async def close(self):
        """Clean shutdown"""
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def screenshot(self, path: str = None):
        """Take a screenshot for debugging"""
        if self._page:
            if not path:
                path = str(Path(config.browser.user_data_dir) / f"screenshot_{self.profile_name}.png")
            await self._page.screenshot(path=path)
            return path

    async def is_logged_in(self, url: str, logged_in_selector: str) -> bool:
        """Check if we're logged in to a platform"""
        try:
            page = await self.get_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=config.browser.timeout)
            await asyncio.sleep(2)
            element = await page.query_selector(logged_in_selector)
            return element is not None
        except Exception as e:
            logger.error(f"Login check failed: {e}")
            return False


class BasePlatformAutomation:
    """Base class for platform-specific automation"""

    def __init__(self, profile_name: str):
        self.browser = BrowserManager(profile_name)
        self.human = HumanBehavior()
        self._page = None

    async def __aenter__(self):
        self._page = await self.browser.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.browser.close()

    async def navigate(self, url: str, wait: str = "domcontentloaded"):
        """Navigate with human-like behavior"""
        await self._page.goto(url, wait_until=wait, timeout=config.browser.timeout)
        await self.human.random_delay(800, 2000)

    async def wait_and_click(self, selector: str, timeout: int = 10000):
        """Wait for element and click with human timing"""
        await self._page.wait_for_selector(selector, timeout=timeout)
        await self.human.random_delay(300, 800)
        await self._page.click(selector)
        await self.human.random_delay(500, 1200)

    async def fill_field(self, selector: str, text: str):
        """Fill a form field with human-like typing"""
        await self.human.human_type(self._page, selector, text)

    async def safe_goto(self, url: str) -> bool:
        """Navigate with error handling"""
        try:
            await self.navigate(url)
            return True
        except Exception as e:
            logger.error(f"Navigation failed: {url} — {e}")
            return False
