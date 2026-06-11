"""
storage/models.py — SQLAlchemy database models
Tracks all agent activity: subreddits, posts, comments, pins, boards, research intel
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    JSON, ForeignKey, Enum
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class Platform(str, enum.Enum):
    REDDIT = "reddit"
    PINTEREST = "pinterest"


class ContentType(str, enum.Enum):
    POST = "post"
    COMMENT = "comment"
    PIN = "pin"
    BOARD = "board"


class AccountPhase(str, enum.Enum):
    WARMUP = "warmup"
    ACTIVE = "active"
    PROMOTION = "promotion"


class SubredditTier(str, enum.Enum):
    RESEARCH = "research"
    CREDIBILITY = "credibility"
    ENGAGEMENT = "engagement"
    BUYER_INTENT = "buyer_intent"
    PROMOTION = "promotion"


class ActionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ─────────────────────────────────────────────
# REDDIT MODELS
# ─────────────────────────────────────────────

class RedditAccount(Base):
    __tablename__ = "reddit_accounts"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    account_created_date = Column(DateTime, nullable=True)
    karma_post = Column(Integer, default=0)
    karma_comment = Column(Integer, default=0)
    phase = Column(Enum(AccountPhase), default=AccountPhase.WARMUP)
    is_active = Column(Boolean, default=True)
    warmup_start_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    actions = relationship("RedditAction", back_populates="account")

    @property
    def total_karma(self):
        return self.karma_post + self.karma_comment

    @property
    def days_since_warmup(self):
        if self.warmup_start_date:
            return (datetime.utcnow() - self.warmup_start_date).days
        return 0


class Subreddit(Base):
    __tablename__ = "subreddits"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=True)
    subscriber_count = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    posts_per_day = Column(Float, default=0)
    tier = Column(Enum(SubredditTier), nullable=True)

    # Scoring (1-10 each)
    score_audience_quality = Column(Float, default=0)
    score_pain_intensity = Column(Float, default=0)
    score_relevance = Column(Float, default=0)
    score_post_opportunity = Column(Float, default=0)
    score_comment_opportunity = Column(Float, default=0)
    score_promotion_tolerance = Column(Float, default=0)
    score_lead_potential = Column(Float, default=0)
    score_authority_potential = Column(Float, default=0)
    score_ease_of_entry = Column(Float, default=0)
    score_overall = Column(Float, default=0)

    # Moderation intel
    moderation_strictness = Column(Integer, default=5)   # 1-10
    self_promo_allowed = Column(Boolean, default=False)
    link_posts_allowed = Column(Boolean, default=True)
    image_posts_allowed = Column(Boolean, default=True)
    rules_summary = Column(Text, nullable=True)

    # Strategy tags
    best_post_times = Column(JSON, default=list)
    top_performing_formats = Column(JSON, default=list)
    key_pain_points = Column(JSON, default=list)
    buyer_signals = Column(JSON, default=list)
    competitor_mentions = Column(JSON, default=list)

    is_tracked = Column(Boolean, default=True)
    last_analyzed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    actions = relationship("RedditAction", back_populates="subreddit")
    research_entries = relationship("ResearchIntel", back_populates="subreddit")


class RedditAction(Base):
    __tablename__ = "reddit_actions"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("reddit_accounts.id"))
    subreddit_id = Column(Integer, ForeignKey("subreddits.id"), nullable=True)

    action_type = Column(Enum(ContentType), nullable=False)
    content_title = Column(String(500), nullable=True)
    content_body = Column(Text, nullable=True)
    content_url = Column(String(500), nullable=True)
    parent_post_id = Column(String(100), nullable=True)  # For comments
    reddit_post_id = Column(String(100), nullable=True)   # ID once posted

    status = Column(Enum(ActionStatus), default=ActionStatus.PENDING)
    scheduled_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Performance
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    profile_visits = Column(Integer, default=0)

    is_promotional = Column(Boolean, default=False)
    content_format = Column(String(50), nullable=True)   # question, experience, case_study, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("RedditAccount", back_populates="actions")
    subreddit = relationship("Subreddit", back_populates="actions")


# ─────────────────────────────────────────────
# PINTEREST MODELS
# ─────────────────────────────────────────────

class PinterestBoard(Base):
    __tablename__ = "pinterest_boards"

    id = Column(Integer, primary_key=True)
    board_id = Column(String(100), nullable=True)       # Pinterest's board ID
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    is_secret = Column(Boolean, default=False)

    # SEO
    primary_keyword = Column(String(200), nullable=True)
    secondary_keywords = Column(JSON, default=list)

    # Performance
    follower_count = Column(Integer, default=0)
    pin_count = Column(Integer, default=0)
    monthly_views = Column(Integer, default=0)

    board_tier = Column(String(50), nullable=True)      # core, supporting, seasonal
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_pinned_at = Column(DateTime, nullable=True)

    pins = relationship("PinterestPin", back_populates="board")


class PinterestPin(Base):
    __tablename__ = "pinterest_pins"

    id = Column(Integer, primary_key=True)
    board_id = Column(Integer, ForeignKey("pinterest_boards.id"), nullable=True)
    pin_id = Column(String(100), nullable=True)         # Pinterest's pin ID

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    destination_url = Column(String(500), nullable=True)
    image_path = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)

    # Keywords
    primary_keyword = Column(String(200), nullable=True)
    keywords = Column(JSON, default=list)

    # Content classification
    pin_format = Column(String(50), nullable=True)      # standard, idea, product, etc.
    funnel_stage = Column(String(50), nullable=True)    # awareness, consideration, conversion
    content_type = Column(String(50), nullable=True)    # blog, product, lead_magnet, etc.

    # Scheduling
    status = Column(Enum(ActionStatus), default=ActionStatus.PENDING)
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)

    # Performance
    impressions = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    outbound_clicks = Column(Integer, default=0)
    closeups = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)

    is_seasonal = Column(Boolean, default=False)
    season_target = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    board = relationship("PinterestBoard", back_populates="pins")


class PinterestKeyword(Base):
    __tablename__ = "pinterest_keywords"

    id = Column(Integer, primary_key=True)
    keyword = Column(String(300), unique=True, nullable=False)
    cluster = Column(String(200), nullable=True)
    intent_type = Column(String(50), nullable=True)   # inspiration, problem, comparison, buyer
    search_volume = Column(String(50), nullable=True)  # high/medium/low
    competition = Column(String(50), nullable=True)
    is_long_tail = Column(Boolean, default=False)
    is_seasonal = Column(Boolean, default=False)
    season = Column(String(50), nullable=True)
    priority_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# SHARED RESEARCH MODELS
# ─────────────────────────────────────────────

class ResearchIntel(Base):
    __tablename__ = "research_intel"

    id = Column(Integer, primary_key=True)
    platform = Column(Enum(Platform), nullable=False)
    subreddit_id = Column(Integer, ForeignKey("subreddits.id"), nullable=True)

    intel_type = Column(String(100), nullable=False)  # pain_point, language, objection, trigger, competitor
    content = Column(Text, nullable=False)
    source_url = Column(String(500), nullable=True)
    source_post_id = Column(String(100), nullable=True)
    frequency = Column(Integer, default=1)       # How many times this came up
    sentiment = Column(String(20), nullable=True) # positive, negative, neutral
    priority = Column(Integer, default=5)         # 1-10

    # Actionable tags
    can_use_in_ad_copy = Column(Boolean, default=False)
    can_use_in_content = Column(Boolean, default=False)
    can_use_in_product = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    subreddit = relationship("Subreddit", back_populates="research_entries")


class ContentIdea(Base):
    __tablename__ = "content_ideas"

    id = Column(Integer, primary_key=True)
    platform = Column(Enum(Platform), nullable=False)
    title = Column(String(500), nullable=False)
    body_draft = Column(Text, nullable=True)
    content_format = Column(String(100), nullable=True)
    target_subreddit = Column(String(100), nullable=True)
    target_board = Column(String(100), nullable=True)
    keywords = Column(JSON, default=list)
    pain_points_addressed = Column(JSON, default=list)
    priority_score = Column(Float, default=5.0)
    status = Column(String(50), default="idea")   # idea, drafted, scheduled, published
    created_at = Column(DateTime, default=datetime.utcnow)


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"

    id = Column(Integer, primary_key=True)
    platform = Column(Enum(Platform), nullable=False)
    week_start = Column(DateTime, nullable=False)
    week_end = Column(DateTime, nullable=False)
    planned_actions = Column(JSON, default=dict)    # {monday: [...], tuesday: [...]}
    completed_actions = Column(Integer, default=0)
    total_actions = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True)
    platform = Column(Enum(Platform), nullable=False)
    metric_date = Column(DateTime, nullable=False)
    metric_type = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    context = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
