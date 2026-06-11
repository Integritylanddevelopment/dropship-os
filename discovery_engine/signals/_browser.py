"""Playwright-based browser fetcher for sources that block stdlib HTTP."""
import atexit, random, time
from typing import Optional
from . import _common

_PLAYWRIGHT = None
_BROWSER = None
_CONTEXT = None
_LAUNCHED = False

_VIEWPORT = {"width": 1366, "height": 768}
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

def _ensure_browser():
    global _PLAYWRIGHT, _BROWSER, _CONTEXT, _LAUNCHED
    if _LAUNCHED:
        return _BROWSER is not None
    _LAUNCHED = True
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[_browser] playwright not installed", flush=True)
        return False
    try:
        _PLAYWRIGHT = sync_playwright().start()
        _BROWSER = _PLAYWRIGHT.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-dev-shm-usage"],
        )
        _CONTEXT = _BROWSER.new_context(
            viewport=_VIEWPORT, user_agent=_UA, locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        _CONTEXT.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        atexit.register(_shutdown)
        return True
    except Exception as e:
        print(f"[_browser] launch failed: {e}", flush=True)
        _BROWSER = None
        _CONTEXT = None
        return False

def _shutdown():
    global _BROWSER, _CONTEXT, _PLAYWRIGHT
    try:
        if _CONTEXT: _CONTEXT.close()
    except: pass
    try:
        if _BROWSER: _BROWSER.close()
    except: pass
    try:
        if _PLAYWRIGHT: _PLAYWRIGHT.stop()
    except: pass
    _CONTEXT = None; _BROWSER = None; _PLAYWRIGHT = None

def fetch_rendered(url: str, wait_for: Optional[str] = None,
                   wait_for_text: Optional[str] = None,
                   timeout: int = 20000, scroll: bool = False) -> str:
    """Fetch with full JS rendering. Returns rendered HTML or ''."""
    if not _ensure_browser():
        return ""
    _common.throttle(_common._host_from_url(url))
    page = None
    try:
        page = _CONTEXT.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        if wait_for:
            try: page.wait_for_selector(wait_for, timeout=timeout)
            except: pass
        if wait_for_text:
            try:
                page.wait_for_function(
                    f"document.body && document.body.innerText.includes({wait_for_text!r})",
                    timeout=timeout)
            except: pass
        if scroll:
            for _ in range(4):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                time.sleep(0.5 + random.random() * 0.5)
        return page.content()
    except Exception as e:
        print(f"[_browser] fetch failed for {url}: {e}", flush=True)
        return ""
    finally:
        if page:
            try: page.close()
            except: pass

def is_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        return False