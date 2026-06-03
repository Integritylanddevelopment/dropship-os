"""
Pinterest AI Agent — Database Layer (SQLite)
Stores pins, boards, keywords, analytics, content queue, and seasonal calendar.
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, Any
from contextlib import contextmanager


class Database:
    def __init__(self, db_path: str = "pinterest_agent.db"):
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript("""
                -- Boards table
                CREATE TABLE IF NOT EXISTS boards (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    pin_count INTEGER DEFAULT 0,
                    follower_count INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    keyword_cluster TEXT,
                    priority INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'active'
                );

                -- Pins table
                CREATE TABLE IF NOT EXISTS pins (
                    id TEXT PRIMARY KEY,
                    board_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    link TEXT,
                    image_url TEXT,
                    pin_type TEXT DEFAULT 'standard',
                    keyword_primary TEXT,
                    keyword_secondary TEXT,
                    content_angle TEXT,
                    status TEXT DEFAULT 'draft',
                    published_at TEXT,
                    scheduled_for TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    impressions INTEGER DEFAULT 0,
                    saves INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    outbound_clicks INTEGER DEFAULT 0,
                    save_rate REAL DEFAULT 0.0,
                    click_rate REAL DEFAULT 0.0,
                    performance_score REAL DEFAULT 0.0,
                    last_analytics_update TEXT,
                    FOREIGN KEY (board_id) REFERENCES boards(id)
                );

                -- Keywords table
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL UNIQUE,
                    cluster TEXT,
                    intent_type TEXT,
                    search_volume_estimate TEXT,
                    competition TEXT,
                    seasonal BOOLEAN DEFAULT 0,
                    evergreen BOOLEAN DEFAULT 1,
                    buyer_intent_score INTEGER DEFAULT 5,
                    save_potential_score INTEGER DEFAULT 5,
                    click_potential_score INTEGER DEFAULT 5,
                    traffic_potential_score INTEGER DEFAULT 5,
                    overall_score REAL DEFAULT 5.0,
                    discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_used TEXT
                );

                -- Content queue table
                CREATE TABLE IF NOT EXISTS content_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    link TEXT,
                    board_id TEXT,
                    board_name TEXT,
                    pin_type TEXT,
                    keyword_primary TEXT,
                    content_angle TEXT,
                    image_guidance TEXT,
                    landing_page_type TEXT,
                    priority INTEGER DEFAULT 5,
                    scheduled_for TEXT,
                    status TEXT DEFAULT 'queued',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                );

                -- Seasonal calendar table
                CREATE TABLE IF NOT EXISTS seasonal_calendar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    season TEXT NOT NULL,
                    event TEXT NOT NULL,
                    target_date TEXT NOT NULL,
                    publish_by TEXT NOT NULL,
                    lead_days INTEGER DEFAULT 45,
                    content_themes TEXT,
                    keyword_focus TEXT,
                    board_targets TEXT,
                    pin_types TEXT,
                    status TEXT DEFAULT 'upcoming',
                    notes TEXT
                );

                -- Opportunities table (scoring system)
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    niche TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    traffic_potential INTEGER DEFAULT 5,
                    buyer_intent INTEGER DEFAULT 5,
                    save_potential INTEGER DEFAULT 5,
                    click_potential INTEGER DEFAULT 5,
                    conversion_quality INTEGER DEFAULT 5,
                    keyword_opportunity INTEGER DEFAULT 5,
                    creative_fit INTEGER DEFAULT 5,
                    competition_level INTEGER DEFAULT 5,
                    evergreen_value INTEGER DEFAULT 5,
                    overall_score REAL DEFAULT 5.0,
                    recommended_action TEXT,
                    priority_rank INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Analytics snapshots
                CREATE TABLE IF NOT EXISTS analytics_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    total_pins INTEGER DEFAULT 0,
                    total_boards INTEGER DEFAULT 0,
                    total_impressions INTEGER DEFAULT 0,
                    total_saves INTEGER DEFAULT 0,
                    total_clicks INTEGER DEFAULT 0,
                    total_outbound_clicks INTEGER DEFAULT 0,
                    avg_save_rate REAL DEFAULT 0.0,
                    avg_click_rate REAL DEFAULT 0.0,
                    top_pin_id TEXT,
                    top_board_id TEXT,
                    weekly_pin_count INTEGER DEFAULT 0,
                    notes TEXT
                );

                -- Competitor intelligence
                CREATE TABLE IF NOT EXISTS competitor_intel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_url TEXT,
                    account_name TEXT,
                    follower_count INTEGER DEFAULT 0,
                    board_count INTEGER DEFAULT 0,
                    top_boards TEXT,
                    top_content_themes TEXT,
                    content_frequency TEXT,
                    keyword_patterns TEXT,
                    visual_style TEXT,
                    gaps_identified TEXT,
                    analyzed_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Lead magnet tracker
                CREATE TABLE IF NOT EXISTS lead_magnets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT,
                    topic TEXT,
                    landing_page_url TEXT,
                    opt_in_rate REAL DEFAULT 0.0,
                    total_leads INTEGER DEFAULT 0,
                    pin_ids TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

    # === BOARDS ===
    def upsert_board(self, board: dict) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO boards
                (id, name, description, category, pin_count, follower_count,
                 created_at, updated_at, keyword_cluster, priority, status)
                VALUES (:id, :name, :description, :category, :pin_count,
                        :follower_count, :created_at, :updated_at,
                        :keyword_cluster, :priority, :status)
            """, board)

    def get_boards(self, status: str = "active") -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM boards WHERE status = ? ORDER BY priority DESC", (status,)
            ).fetchall()
            return [dict(r) for r in rows]

    # === PINS ===
    def upsert_pin(self, pin: dict) -> None:
        with self._conn() as conn:
            fields = list(pin.keys())
            placeholders = [f":{f}" for f in fields]
            conn.execute(
                f"INSERT OR REPLACE INTO pins ({', '.join(fields)}) VALUES ({', '.join(placeholders)})",
                pin
            )

    def get_pins(self, status: str = None, board_id: str = None, limit: int = 100) -> list[dict]:
        with self._conn() as conn:
            query = "SELECT * FROM pins WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if board_id:
                query += " AND board_id = ?"
                params.append(board_id)
            query += f" ORDER BY created_at DESC LIMIT {limit}"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_top_performing_pins(self, metric: str = "saves", limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM pins WHERE status='published' ORDER BY {metric} DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # === KEYWORDS ===
    def upsert_keyword(self, keyword: dict) -> None:
        with self._conn() as conn:
            fields = list(keyword.keys())
            placeholders = [f":{f}" for f in fields]
            conn.execute(
                f"INSERT OR REPLACE INTO keywords ({', '.join(fields)}) VALUES ({', '.join(placeholders)})",
                keyword
            )

    def get_keywords(self, cluster: str = None, limit: int = 100) -> list[dict]:
        with self._conn() as conn:
            query = "SELECT * FROM keywords WHERE 1=1"
            params = []
            if cluster:
                query += " AND cluster = ?"
                params.append(cluster)
            query += " ORDER BY overall_score DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # === CONTENT QUEUE ===
    def add_to_queue(self, item: dict) -> int:
        with self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO content_queue
                (title, description, link, board_id, board_name, pin_type,
                 keyword_primary, content_angle, image_guidance, landing_page_type,
                 priority, scheduled_for, notes)
                VALUES (:title, :description, :link, :board_id, :board_name, :pin_type,
                        :keyword_primary, :content_angle, :image_guidance, :landing_page_type,
                        :priority, :scheduled_for, :notes)
            """, item)
            return cursor.lastrowid

    def get_queue(self, status: str = "queued", limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM content_queue WHERE status = ? ORDER BY priority DESC, scheduled_for ASC LIMIT ?",
                (status, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def update_queue_status(self, item_id: int, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE content_queue SET status = ? WHERE id = ?",
                (status, item_id)
            )

    # === SEASONAL CALENDAR ===
    def get_upcoming_seasonal(self, days_ahead: int = 90) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM seasonal_calendar
                WHERE publish_by >= date('now')
                AND publish_by <= date('now', ? || ' days')
                AND status = 'upcoming'
                ORDER BY publish_by ASC
            """, (str(days_ahead),)).fetchall()
            return [dict(r) for r in rows]

    def save_seasonal_event(self, event: dict) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO seasonal_calendar
                (season, event, target_date, publish_by, lead_days,
                 content_themes, keyword_focus, board_targets, pin_types, notes)
                VALUES (:season, :event, :target_date, :publish_by, :lead_days,
                        :content_themes, :keyword_focus, :board_targets, :pin_types, :notes)
            """, event)

    # === OPPORTUNITIES ===
    def save_opportunity(self, opp: dict) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO opportunities
                (niche, topic, traffic_potential, buyer_intent, save_potential,
                 click_potential, conversion_quality, keyword_opportunity,
                 creative_fit, competition_level, evergreen_value, overall_score,
                 recommended_action, priority_rank)
                VALUES (:niche, :topic, :traffic_potential, :buyer_intent, :save_potential,
                        :click_potential, :conversion_quality, :keyword_opportunity,
                        :creative_fit, :competition_level, :evergreen_value, :overall_score,
                        :recommended_action, :priority_rank)
            """, opp)

    def get_opportunities(self, niche: str = None) -> list[dict]:
        with self._conn() as conn:
            query = "SELECT * FROM opportunities WHERE 1=1"
            params = []
            if niche:
                query += " AND niche LIKE ?"
                params.append(f"%{niche}%")
            query += " ORDER BY overall_score DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # === ANALYTICS ===
    def save_analytics_snapshot(self, snapshot: dict) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO analytics_snapshots
                (total_pins, total_boards, total_impressions, total_saves,
                 total_clicks, total_outbound_clicks, avg_save_rate, avg_click_rate,
                 top_pin_id, top_board_id, weekly_pin_count, notes)
                VALUES (:total_pins, :total_boards, :total_impressions, :total_saves,
                        :total_clicks, :total_outbound_clicks, :avg_save_rate, :avg_click_rate,
                        :top_pin_id, :top_board_id, :weekly_pin_count, :notes)
            """, snapshot)

    def get_analytics_history(self, days: int = 30) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM analytics_snapshots
                WHERE snapshot_date >= datetime('now', ? || ' days')
                ORDER BY snapshot_date ASC
            """, (f"-{days}",)).fetchall()
            return [dict(r) for r in rows]

    def get_summary_stats(self) -> dict:
        with self._conn() as conn:
            pins = conn.execute("SELECT COUNT(*) as c, SUM(saves) as s, SUM(clicks) as cl, SUM(impressions) as i FROM pins WHERE status='published'").fetchone()
            boards = conn.execute("SELECT COUNT(*) as c FROM boards WHERE status='active'").fetchone()
            queue = conn.execute("SELECT COUNT(*) as c FROM content_queue WHERE status='queued'").fetchone()
            keywords = conn.execute("SELECT COUNT(*) as c FROM keywords").fetchone()
            return {
                "total_published_pins": pins["c"] or 0,
                "total_saves": pins["s"] or 0,
                "total_clicks": pins["cl"] or 0,
                "total_impressions": pins["i"] or 0,
                "active_boards": boards["c"] or 0,
                "queued_content": queue["c"] or 0,
                "tracked_keywords": keywords["c"] or 0,
            }
