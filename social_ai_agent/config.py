"""
config.py — Central configuration for the Social AI Agent System
All API credentials are stubbed. Swap browser automation for API calls
by flipping REDDIT_MODE / PINTEREST_MODE to "api" in your .env file.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
(DATA_DIR / "browser_profiles").mkdir(exist_ok=True)


# ─────────────────────────────────────────────
# API CREDENTIAL STUBS
# ─────────────────────────────────────────────

@dataclass
class RedditAPIConfig:
    """
    STUB: Reddit API via PRAW.
    Get credentials at: https://www.reddit.com/prefs/apps
    Docs: https://praw.readthedocs.io
    """
    client_id: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_SECRET", ""))
    username: str = field(default_factory=lambda: os.getenv("REDDIT_USERNAME", ""))
    password: str = field(default_factory=lambda: os.getenv("REDDIT_PASSWORD", ""))
    user_agent: str = field(default_factory=lambda: os.getenv("REDDIT_USER_AGENT", "SocialAIAgent/1.0"))

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.username and self.password)

    @property
    def mode(self) -> str:
        return os.getenv("REDDIT_MODE", "browser")


@dataclass
class PinterestAPIConfig:
    """
    STUB: Pinterest API v5.
    Get credentials at: https://developers.pinterest.com
    Docs: https://developers.pinterest.com/docs/api/v5/
    """
    access_token: str = field(default_factory=lambda: os.getenv("PINTEREST_ACCESS_TOKEN", ""))
    app_id: str = field(default_factory=lambda: os.getenv("PINTEREST_APP_ID", ""))
    app_secret: str = field(default_factory=lambda: os.getenv("PINTEREST_APP_SECRET", ""))

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token and self.app_id)

    @property
    def mode(self) -> str:
        return os.getenv("PINTEREST_MODE", "api")


@dataclass
class AIConfig:
    """AI content generation — supports OpenAI and Anthropic"""
    provider: str = field(default_factory=lambda: os.getenv("AI_PROVIDER", "anthropic"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model_openai: str = field(default_factory=lambda: os.getenv("MODEL_OPENAI", "gpt-4o"))
    model_anthropic: str = field(default_factory=lambda: os.getenv("MODEL_ANTHROPIC", "claude-opus-4-5"))
    max_tokens: int = 2000
    temperature: float = 0.72

    @property
    def is_configured(self) -> bool:
        if self.provider == "openai":
            return bool(self.openai_api_key)
        return bool(self.anthropic_api_key)


@dataclass
class BrowserConfig:
    """Playwright browser settings — human-like timing baked in"""
    headless: bool = field(default_factory=lambda: os.getenv("BROWSER_HEADLESS", "false").lower() == "true")
    slow_mo: int = field(default_factory=lambda: int(os.getenv("BROWSER_SLOW_MO", "1200")))
    timeout: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 800
    user_data_dir: str = str(DATA_DIR / "browser_profiles")
    # Rotate through these to avoid detection
    user_agents: list = field(default_factory=lambda: [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ])


# ─────────────────────────────────────────────
# STRATEGY CONFIG
# ─────────────────────────────────────────────

@dataclass
class RedditStrategyConfig:
    """Controls Reddit agent behavior based on the full strategy framework"""
    # Warmup phase (first 30 days — no promotion)
    warmup_days: int = 30
    warmup_daily_comments: int = 3
    warmup_daily_posts: int = 0
    warmup_karma_target: int = 500

    # Active phase
    active_daily_comments: int = 8
    active_daily_posts: int = 2
    promotion_karma_threshold: int = 1000

    # Subreddit management
    max_subreddits_tracked: int = 50
    max_active_subreddits: int = 10
    subreddit_rotation_days: int = 7

    # Content rules
    min_comment_length: int = 150
    max_comment_length: int = 600
    min_post_length: int = 200

    # Research
    posts_to_analyze: int = 100
    comment_depth: int = 3

    # Tier definitions
    tier1_subreddits: list = field(default_factory=lambda: [])   # Research only
    tier2_subreddits: list = field(default_factory=lambda: [])   # Credibility building
    tier3_subreddits: list = field(default_factory=lambda: [])   # High engagement
    tier4_subreddits: list = field(default_factory=lambda: [])   # Buyer intent


@dataclass
class PinterestStrategyConfig:
    """Controls Pinterest agent behavior"""
    # Publishing cadence
    daily_pins: int = 15
    pins_per_board_per_day: int = 3
    fresh_pin_ratio: float = 0.7   # 70% fresh, 30% repins
    seasonal_lead_days: int = 45   # Pin seasonal content 45 days early

    # Content
    pin_title_max: int = 100
    pin_description_max: int = 500
    target_board_count: int = 20
    keywords_per_pin: int = 5
    long_tail_per_cluster: int = 10

    # Performance thresholds
    min_saves_for_boost: int = 10
    min_clicks_for_scale: int = 5
    low_performer_cutoff_days: int = 30

    # Competitor research
    competitor_pins_to_analyze: int = 50


# ─────────────────────────────────────────────
# MASTER CONFIG
# ─────────────────────────────────────────────

@dataclass
class Config:
    reddit_api: RedditAPIConfig = field(default_factory=RedditAPIConfig)
    pinterest_api: PinterestAPIConfig = field(default_factory=PinterestAPIConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    reddit_strategy: RedditStrategyConfig = field(default_factory=RedditStrategyConfig)
    pinterest_strategy: PinterestStrategyConfig = field(default_factory=PinterestStrategyConfig)

    # Business profile
    niche: str = field(default_factory=lambda: os.getenv("BUSINESS_NICHE", "dropshipping"))
    business_name: str = field(default_factory=lambda: os.getenv("BUSINESS_NAME", "My Store"))
    website_url: str = field(default_factory=lambda: os.getenv("WEBSITE_URL", "https://example.com"))
    target_products: list = field(default_factory=lambda: [
        p.strip() for p in os.getenv("TARGET_PRODUCTS", "").split(",") if p.strip()
    ])

    def status(self) -> dict:
        return {
            "reddit_api": "✅ Ready" if self.reddit_api.is_configured else "⚠️  Use browser mode",
            "reddit_mode": self.reddit_api.mode,
            "pinterest_api": "✅ Ready" if self.pinterest_api.is_configured else "⚠️  Use browser mode",
            "pinterest_mode": self.pinterest_api.mode,
            "ai": "✅ Ready" if self.ai.is_configured else "❌ Add API key to .env",
            "business": self.business_name,
            "niche": self.niche,
        }

    def save_to_file(self, path: str = str(BASE_DIR / "config_override.json")):
        with open(path, "w") as f:
            json.dump({
                "niche": self.niche,
                "business_name": self.business_name,
                "website_url": self.website_url,
                "target_products": self.target_products,
            }, f, indent=2)
        print(f"Config saved to {path}")


# Singleton
config = Config()
