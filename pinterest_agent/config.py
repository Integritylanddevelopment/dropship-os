"""
Pinterest AI Agent — Configuration Management
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class PinterestConfig:
    # === API KEYS ===
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    pinterest_access_token: str = field(default_factory=lambda: os.getenv("PINTEREST_ACCESS_TOKEN", ""))
    pinterest_ad_account_id: Optional[str] = field(default_factory=lambda: os.getenv("PINTEREST_AD_ACCOUNT_ID"))

    # === BUSINESS SETTINGS ===
    business_name: str = field(default_factory=lambda: os.getenv("BUSINESS_NAME", "Drop Shipping Store"))
    website_url: str = field(default_factory=lambda: os.getenv("WEBSITE_URL", "https://yourstore.com"))
    primary_niche: str = field(default_factory=lambda: os.getenv("PRIMARY_NICHE", "home organization, kitchen gadgets, lifestyle products"))
    brand_voice: str = field(default_factory=lambda: os.getenv("BRAND_VOICE", "helpful, aspirational, value-focused"))

    # === PUBLISHING SETTINGS ===
    daily_pin_limit: int = field(default_factory=lambda: int(os.getenv("DAILY_PIN_LIMIT", "25")))
    weekly_pin_target: int = field(default_factory=lambda: int(os.getenv("WEEKLY_PIN_TARGET", "15")))
    fresh_pin_ratio: float = field(default_factory=lambda: float(os.getenv("FRESH_PIN_RATIO", "0.8")))  # 80% fresh content
    repurpose_ratio: float = 0.2  # 20% repurposed

    # === CONTENT SETTINGS ===
    default_pin_width: int = 1000
    default_pin_height: int = 1500
    max_title_length: int = 100
    max_description_length: int = 500

    # === DATABASE ===
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "pinterest_agent.db"))

    # === DASHBOARD ===
    dashboard_host: str = field(default_factory=lambda: os.getenv("DASHBOARD_HOST", "0.0.0.0"))
    dashboard_port: int = field(default_factory=lambda: int(os.getenv("DASHBOARD_PORT", "8080")))

    # === PINTEREST API ===
    pinterest_api_base: str = "https://api.pinterest.com/v5"

    def validate(self) -> list[str]:
        """Return list of missing required config values."""
        missing = []
        if not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        if not self.pinterest_access_token:
            missing.append("PINTEREST_ACCESS_TOKEN")
        if not self.website_url or self.website_url == "https://yourstore.com":
            missing.append("WEBSITE_URL (set to your actual domain)")
        return missing


def load_config() -> PinterestConfig:
    config = PinterestConfig()
    missing = config.validate()
    if missing:
        print("\n⚠️  Missing configuration:")
        for item in missing:
            print(f"   - {item}")
        print("\n→ Copy .env.example to .env and fill in your values.\n")
    return config
