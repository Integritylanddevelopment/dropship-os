"""
db.py — Unified Database Layer for ShipStack
=============================================
Replaces all JSON file storage with proper databases:

  SQLite      → profiles, AB tests, metrics, calendar
                (relational, concurrent-safe, zero setup)

  ChromaDB    → content pieces, spin results, hook patterns
                (semantic search — "find content like this winner")
                Uses Quinn's existing ChromaDB instance

  Qdrant      → learning engine long-term memory
                (cross-session, already on server at 192.168.1.123:6333)

Usage:
  from agents.db import ProfileDB, ContentDB, LearningDB
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SQLITE_PATH  = DATA_DIR / "shipstack.db"
CHROMA_PATH  = DATA_DIR / "chroma_db"
QDRANT_HOST  = os.getenv("QDRANT_HOST", "192.168.1.123")
QDRANT_PORT  = int(os.getenv("QDRANT_PORT", "6333"))

# ═══════════════════════════════════════════════════════════════════
# SQLite layer — profiles, AB tests, metrics
# ═══════════════════════════════════════════════════════════════════

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # concurrent reads + writes
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def db_conn():
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    with db_conn() as conn:
        conn.executescript("""
        -- ── Profiles ─────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS profiles (
            id              TEXT PRIMARY KEY,
            platform        TEXT NOT NULL,
            username        TEXT NOT NULL,
            niche           TEXT DEFAULT 'default',
            proxy           TEXT,
            notes           TEXT DEFAULT '',
            followers       INTEGER DEFAULT 0,
            following       INTEGER DEFAULT 0,
            posts           INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'warming_up',
            last_posted     TEXT,
            assigned_calendar TEXT,
            session_file    TEXT,
            created         TEXT NOT NULL,
            updated         TEXT NOT NULL,
            UNIQUE(platform, username)
        );

        -- ── AB Tests ──────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS ab_tests (
            test_id         TEXT PRIMARY KEY,
            product_slug    TEXT NOT NULL,
            platform        TEXT NOT NULL,
            content_type    TEXT NOT NULL,
            niche           TEXT DEFAULT 'default',
            status          TEXT DEFAULT 'active',
            created         TEXT NOT NULL,
            concluded       TEXT,
            winner_json     TEXT,
            base_content    TEXT
        );

        -- ── AB Variants ───────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS ab_variants (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id         TEXT NOT NULL REFERENCES ab_tests(test_id),
            label           TEXT NOT NULL,
            avatar_id       TEXT,
            avatar_name     TEXT,
            content         TEXT,
            impressions     INTEGER DEFAULT 0,
            clicks          INTEGER DEFAULT 0,
            saves           INTEGER DEFAULT 0,
            shares          INTEGER DEFAULT 0,
            comments        INTEGER DEFAULT 0,
            link_clicks     INTEGER DEFAULT 0,
            conversions     INTEGER DEFAULT 0,
            revenue         REAL DEFAULT 0.0,
            ctr             REAL DEFAULT 0.0,
            engagement_rate REAL DEFAULT 0.0,
            traffic_source  TEXT DEFAULT '{}',
            posted_at       TEXT,
            post_url        TEXT,
            updated         TEXT
        );

        -- ── Learning State ────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS learning_state (
            key             TEXT PRIMARY KEY,
            value_json      TEXT NOT NULL,
            updated         TEXT NOT NULL
        );

        -- ── Improvement Log ───────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS improvement_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            event_type      TEXT,
            message         TEXT
        );

        -- ── Content Calendar (bonus: replace JSON calendar too) ───────────
        CREATE TABLE IF NOT EXISTS calendar_posts (
            id              TEXT PRIMARY KEY,
            product_slug    TEXT NOT NULL,
            platform        TEXT NOT NULL,
            content_type    TEXT,
            scheduled_time  TEXT NOT NULL,
            content         TEXT,
            caption         TEXT,
            hashtags        TEXT DEFAULT '[]',
            status          TEXT DEFAULT 'queued',
            assigned_profile TEXT,
            ab_test_id      TEXT,
            sent_at         TEXT,
            post_url        TEXT,
            created         TEXT NOT NULL
        );

        -- ── Indexes ───────────────────────────────────────────────────────
        CREATE INDEX IF NOT EXISTS idx_profiles_platform ON profiles(platform);
        CREATE INDEX IF NOT EXISTS idx_profiles_status   ON profiles(status);
        CREATE INDEX IF NOT EXISTS idx_ab_tests_product  ON ab_tests(product_slug);
        CREATE INDEX IF NOT EXISTS idx_ab_tests_status   ON ab_tests(status);
        CREATE INDEX IF NOT EXISTS idx_ab_variants_test  ON ab_variants(test_id);
        CREATE INDEX IF NOT EXISTS idx_calendar_platform ON calendar_posts(platform, status);
        CREATE INDEX IF NOT EXISTS idx_calendar_scheduled ON calendar_posts(scheduled_time);
        """)
    print(f"[DB] SQLite initialized at {SQLITE_PATH}")


# ═══════════════════════════════════════════════════════════════════
# ProfileDB — replaces profile_manager.py JSON ops
# ═══════════════════════════════════════════════════════════════════

class ProfileDB:

    def add(self, platform: str, username: str, niche: str = "default",
            proxy: str = None, notes: str = "") -> dict:
        now = datetime.now().isoformat()
        prefix = {"tiktok": "tt", "instagram": "ig", "youtube": "yt"}.get(platform, "xx")
        profile_id = f"{prefix}_{uuid.uuid4().hex[:6]}"
        sessions_dir = DATA_DIR / "profiles" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        session_file = str(sessions_dir / f"{platform}_{username}.json")

        with db_conn() as conn:
            try:
                conn.execute("""
                    INSERT INTO profiles
                    (id, platform, username, niche, proxy, notes, status, session_file, created, updated)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (profile_id, platform, username, niche, proxy, notes,
                      "warming_up", session_file, now, now))
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT * FROM profiles WHERE platform=? AND username=?",
                    (platform, username)
                ).fetchone()
                return dict(row) if row else {"error": "already exists"}

        return self.get(profile_id)

    def get(self, profile_id: str) -> Optional[dict]:
        with db_conn() as conn:
            row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
            return dict(row) if row else None

    def list(self, platform: str = None, status: str = None, limit: int = 200) -> list:
        sql = "SELECT * FROM profiles WHERE 1=1"
        params = []
        if platform:
            sql += " AND platform=?"; params.append(platform)
        if status:
            sql += " AND status=?"; params.append(status)
        sql += " ORDER BY created DESC LIMIT ?"
        params.append(limit)
        with db_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_available(self, platform: str, rate_gap_minutes: int = 180, limit: int = 10) -> list:
        """Profiles active and not posted within rate_gap_minutes."""
        cutoff = datetime.now().isoformat()
        sql = """
            SELECT * FROM profiles
            WHERE platform=? AND status='active'
            AND (last_posted IS NULL
                 OR datetime(last_posted) <= datetime('now', ? || ' minutes'))
            ORDER BY last_posted ASC NULLS FIRST
            LIMIT ?
        """
        with db_conn() as conn:
            rows = conn.execute(sql, (platform, f"-{rate_gap_minutes}", limit)).fetchall()
            return [dict(r) for r in rows]

    def update(self, profile_id: str, **kwargs) -> dict:
        kwargs["updated"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [profile_id]
        with db_conn() as conn:
            conn.execute(f"UPDATE profiles SET {sets} WHERE id=?", vals)
        return self.get(profile_id)

    def mark_posted(self, profile_id: str) -> dict:
        with db_conn() as conn:
            conn.execute("""
                UPDATE profiles
                SET last_posted=?, posts=posts+1, status=CASE WHEN status='warming_up' THEN 'active' ELSE status END,
                    updated=?
                WHERE id=?
            """, (datetime.now().isoformat(), datetime.now().isoformat(), profile_id))
        return self.get(profile_id)

    def stats(self) -> dict:
        with db_conn() as conn:
            total     = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
            followers = conn.execute("SELECT COALESCE(SUM(followers),0) FROM profiles").fetchone()[0]
            by_plat   = {r[0]: r[1] for r in conn.execute(
                "SELECT platform, COUNT(*) FROM profiles GROUP BY platform").fetchall()}
            by_status = {r[0]: r[1] for r in conn.execute(
                "SELECT status, COUNT(*) FROM profiles GROUP BY status").fetchall()}
        return {"total_profiles": total, "total_followers": followers,
                "by_platform": by_plat, "by_status": by_status}

    def migrate_from_json(self, json_path: str = None):
        """One-time migration: import existing profiles.json into SQLite."""
        path = Path(json_path) if json_path else DATA_DIR / "profiles" / "profiles.json"
        if not path.exists():
            print("[DB] No profiles.json to migrate")
            return 0
        data = json.loads(path.read_text())
        count = 0
        for p in data.get("profiles", []):
            try:
                now = datetime.now().isoformat()
                with db_conn() as conn:
                    conn.execute("""
                        INSERT OR IGNORE INTO profiles
                        (id, platform, username, niche, proxy, notes, followers, following,
                         posts, status, last_posted, assigned_calendar, session_file, created, updated)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (p.get("id"), p.get("platform"), p.get("username"),
                          p.get("niche","default"), p.get("proxy"), p.get("notes",""),
                          p.get("followers",0), p.get("following",0), p.get("posts",0),
                          p.get("status","warming_up"), p.get("last_posted"),
                          p.get("assigned_calendar"), p.get("session_file"),
                          p.get("created", now), now))
                count += 1
            except Exception as e:
                print(f"[DB] Skipped profile {p.get('id')}: {e}")
        print(f"[DB] Migrated {count} profiles from JSON → SQLite")
        return count


# ═══════════════════════════════════════════════════════════════════
# ABTestDB — replaces ab_testing.py JSON ops
# ═══════════════════════════════════════════════════════════════════

class ABTestDB:

    def create(self, test_id: str, product_slug: str, platform: str,
               content_type: str, niche: str, base_content: str,
               variants: list) -> dict:
        now = datetime.now().isoformat()
        with db_conn() as conn:
            conn.execute("""
                INSERT INTO ab_tests (test_id, product_slug, platform, content_type,
                    niche, status, created, base_content)
                VALUES (?,?,?,?,?,?,?,?)
            """, (test_id, product_slug, platform, content_type, niche, "active", now, base_content))
            for v in variants:
                conn.execute("""
                    INSERT INTO ab_variants
                    (test_id, label, avatar_id, avatar_name, content, updated)
                    VALUES (?,?,?,?,?,?)
                """, (test_id, v["label"], v.get("avatar_id",""), v.get("avatar_name",""),
                      v.get("content",""), now))
        return self.get(test_id)

    def get(self, test_id: str) -> Optional[dict]:
        with db_conn() as conn:
            test = conn.execute("SELECT * FROM ab_tests WHERE test_id=?", (test_id,)).fetchone()
            if not test:
                return None
            test = dict(test)
            variants = conn.execute(
                "SELECT * FROM ab_variants WHERE test_id=? ORDER BY label", (test_id,)
            ).fetchall()
            test["variants"] = []
            for v in variants:
                vd = dict(v)
                vd["traffic_source"] = json.loads(vd.get("traffic_source") or "{}")
                vd["metrics"] = {
                    "impressions": vd["impressions"], "clicks": vd["clicks"],
                    "saves": vd["saves"], "shares": vd["shares"],
                    "comments": vd["comments"], "link_clicks": vd["link_clicks"],
                    "conversions": vd["conversions"], "revenue": vd["revenue"],
                    "ctr": vd["ctr"], "engagement_rate": vd["engagement_rate"],
                    "traffic_source": vd["traffic_source"],
                }
                test["variants"].append(vd)
            test["winner"] = json.loads(test.get("winner_json") or "null")
        return test

    def update_metrics(self, test_id: str, label: str, **delta) -> dict:
        """Increment metric columns atomically (SQL handles concurrency)."""
        now = datetime.now().isoformat()
        ts_update = delta.pop("traffic_source", None)

        # Build incremental UPDATE for numeric fields
        numeric_cols = ["impressions","clicks","saves","shares","comments","link_clicks","conversions"]
        sets = []
        vals = []
        for col in numeric_cols:
            if col in delta and delta[col]:
                sets.append(f"{col}={col}+?")
                vals.append(int(delta[col]))
        if "revenue" in delta and delta["revenue"]:
            sets.append("revenue=revenue+?")
            vals.append(float(delta["revenue"]))

        if sets:
            sets.append("updated=?")
            vals += [now, test_id, label]
            with db_conn() as conn:
                conn.execute(
                    f"UPDATE ab_variants SET {', '.join(sets)} WHERE test_id=? AND label=?", vals
                )

        # Recalculate CTR and engagement rate
        with db_conn() as conn:
            row = conn.execute(
                "SELECT * FROM ab_variants WHERE test_id=? AND label=?", (test_id, label)
            ).fetchone()
            if row:
                imp = max(row["impressions"], 1)
                eng = row["clicks"] + row["saves"] + row["shares"] + row["comments"]
                ctr = round(row["clicks"] / imp * 100, 3)
                er  = round(eng / imp * 100, 3)
                # Update traffic_source JSON
                if ts_update:
                    existing = json.loads(row["traffic_source"] or "{}")
                    for src, cnt in ts_update.items():
                        existing[src] = existing.get(src, 0) + cnt
                    conn.execute(
                        "UPDATE ab_variants SET ctr=?, engagement_rate=?, traffic_source=?, updated=? WHERE test_id=? AND label=?",
                        (ctr, er, json.dumps(existing), now, test_id, label)
                    )
                else:
                    conn.execute(
                        "UPDATE ab_variants SET ctr=?, engagement_rate=?, updated=? WHERE test_id=? AND label=?",
                        (ctr, er, now, test_id, label)
                    )

        return self.get(test_id)

    def conclude(self, test_id: str, winner: dict):
        now = datetime.now().isoformat()
        with db_conn() as conn:
            conn.execute(
                "UPDATE ab_tests SET status='concluded', concluded=?, winner_json=? WHERE test_id=?",
                (now, json.dumps(winner), test_id)
            )

    def list(self, product_slug: str = None, status: str = None,
             platform: str = None, limit: int = 100) -> list:
        sql = "SELECT * FROM ab_tests WHERE 1=1"
        params = []
        if product_slug:
            sql += " AND product_slug=?"; params.append(product_slug)
        if status:
            sql += " AND status=?"; params.append(status)
        if platform:
            sql += " AND platform=?"; params.append(platform)
        sql += " ORDER BY created DESC LIMIT ?"
        params.append(limit)
        with db_conn() as conn:
            return [self.get(r["test_id"]) for r in conn.execute(sql, params).fetchall()]

    def dashboard_data(self, product_slug: str = None) -> dict:
        with db_conn() as conn:
            base = "WHERE 1=1" + (f" AND product_slug='{product_slug}'" if product_slug else "")
            total     = conn.execute(f"SELECT COUNT(*) FROM ab_tests {base}").fetchone()[0]
            active    = conn.execute(f"SELECT COUNT(*) FROM ab_tests {base} AND status='active'").fetchone()[0]
            concluded = conn.execute(f"SELECT COUNT(*) FROM ab_tests {base} AND status='concluded'").fetchone()[0]

            # Avatar win rates from concluded tests
            winners_raw = conn.execute(
                f"SELECT winner_json FROM ab_tests {base} AND status='concluded' AND winner_json IS NOT NULL"
            ).fetchall()
            avatar_wins = {}
            recent_winners = []
            for row in winners_raw:
                w = json.loads(row[0])
                if w:
                    av = w.get("winner_avatar","unknown")
                    avatar_wins[av] = avatar_wins.get(av, 0) + 1
                    recent_winners.append(w)

            # Platform avg CTR
            plat_rows = conn.execute("""
                SELECT t.platform, AVG(v.ctr)
                FROM ab_tests t JOIN ab_variants v ON t.test_id=v.test_id
                WHERE v.impressions > 0
                GROUP BY t.platform
            """).fetchall()
            platform_avg_ctr = {r[0]: round(r[1], 3) for r in plat_rows}

        return {
            "total_tests": total, "active_tests": active, "concluded_tests": concluded,
            "avatar_win_rates": avatar_wins,
            "platform_avg_ctr": platform_avg_ctr,
            "recent_winners": recent_winners[-10:],
        }

    def migrate_from_json(self, ab_dir: str = None):
        """One-time migration: import existing ab_*.json files into SQLite."""
        path = Path(ab_dir) if ab_dir else DATA_DIR / "ab_tests"
        if not path.exists():
            print("[DB] No ab_tests/ dir to migrate")
            return 0
        count = 0
        for f in path.glob("ab_*.json"):
            try:
                data = json.loads(f.read_text())
                variants = data.get("variants", [])
                self.create(
                    data["test_id"], data["product_slug"], data["platform"],
                    data["content_type"], data.get("niche","default"),
                    data.get("base_content",""), variants
                )
                # If concluded, restore winner
                if data.get("winner"):
                    self.conclude(data["test_id"], data["winner"])
                # Restore metrics per variant
                for v in variants:
                    m = v.get("metrics", {})
                    if m.get("impressions", 0) > 0:
                        with db_conn() as conn:
                            conn.execute("""
                                UPDATE ab_variants SET
                                impressions=?, clicks=?, saves=?, shares=?, comments=?,
                                link_clicks=?, conversions=?, revenue=?, ctr=?, engagement_rate=?,
                                traffic_source=?
                                WHERE test_id=? AND label=?
                            """, (m.get("impressions",0), m.get("clicks",0), m.get("saves",0),
                                  m.get("shares",0), m.get("comments",0), m.get("link_clicks",0),
                                  m.get("conversions",0), m.get("revenue",0.0),
                                  m.get("ctr",0.0), m.get("engagement_rate",0.0),
                                  json.dumps(m.get("traffic_source",{})),
                                  data["test_id"], v["label"]))
                count += 1
            except Exception as e:
                print(f"[DB] Skipped {f.name}: {e}")
        print(f"[DB] Migrated {count} AB tests from JSON → SQLite")
        return count


# ═══════════════════════════════════════════════════════════════════
# ContentDB — ChromaDB for content pieces (semantic search)
# ═══════════════════════════════════════════════════════════════════

class ContentDB:
    """
    Stores content pieces in ChromaDB (Quinn's existing instance).
    Enables: find content similar to a winner, dedup before posting,
    retrieve top performers by semantic query.
    """
    COLLECTION = "shipstack_content"

    def __init__(self):
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection:
            return self._collection
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_PATH))
            # Use same embedding function as Quinn (nomic-embed-text via Ollama)
            from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
            _ollama_base = f"http://{os.getenv('OLLAMA_HOST', '127.0.0.1')}:{os.getenv('OLLAMA_PORT', '11434')}"
            ef = OllamaEmbeddingFunction(
                url=f"{_ollama_base}/api/embeddings",
                model_name="nomic-embed-text"
            )
            self._collection = client.get_or_create_collection(
                name=self.COLLECTION,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"}
            )
            self._client = client
            return self._collection
        except Exception as e:
            print(f"[ContentDB] ChromaDB unavailable: {e}")
            return None

    def store(self, content: str, metadata: dict, content_id: str = None) -> str:
        """Store a content piece with metadata."""
        col = self._get_collection()
        if not col:
            return None
        cid = content_id or f"c_{uuid.uuid4().hex[:12]}"
        # Chunk if too long (ChromaDB has token limits)
        chunks = _chunk_text(content, max_chars=500)
        chunk_ids = []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{cid}_c{i}"
            meta = {**metadata, "chunk_index": i, "content_id": cid}
            # ChromaDB metadata must be str/int/float/bool
            meta = {k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                    for k, v in meta.items()}
            try:
                col.upsert(ids=[chunk_id], documents=[chunk], metadatas=[meta])
                chunk_ids.append(chunk_id)
            except Exception as e:
                print(f"[ContentDB] Store error: {e}")
        return cid

    def store_batch(self, items: list) -> int:
        """Store multiple content pieces. items = [{content, metadata, id?}]"""
        col = self._get_collection()
        if not col:
            return 0
        count = 0
        for item in items:
            result = self.store(item["content"], item.get("metadata", {}), item.get("id"))
            if result:
                count += 1
        return count

    def find_similar(self, query: str, n: int = 10, filters: dict = None) -> list:
        """Semantic search — find content similar to query."""
        col = self._get_collection()
        if not col:
            return []
        where = {k: str(v) for k, v in filters.items()} if filters else None
        try:
            results = col.query(
                query_texts=[query],
                n_results=min(n, col.count() or 1),
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            items = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                items.append({
                    "content": doc,
                    "metadata": meta,
                    "similarity": round(1 - dist, 4),
                })
            return items
        except Exception as e:
            print(f"[ContentDB] Search error: {e}")
            return []

    def find_winner_similar(self, winning_content: str, platform: str, n: int = 20) -> list:
        """Find stored content pieces similar to a proven winner."""
        return self.find_similar(
            winning_content, n=n,
            filters={"platform": platform, "verdict": "PASS"}
        )

    def store_approved_batch(self, approved_content_path: str, product_slug: str, niche: str) -> int:
        """Index all approved content from a pipeline run into ChromaDB."""
        with open(approved_content_path) as f:
            data = json.load(f)

        platform_map = {"tiktok": "tiktok", "instagram": "instagram",
                        "youtube": "youtube", "ad_hooks": "ad_hook"}
        items = []
        for key, platform in platform_map.items():
            for piece in data.get("content", {}).get(key, []):
                text = piece.get("final_text") or piece.get("script") or \
                       piece.get("caption") or piece.get("content", "")
                if not text:
                    continue
                items.append({
                    "content": text,
                    "metadata": {
                        "platform": platform,
                        "product_slug": product_slug,
                        "niche": niche,
                        "verdict": piece.get("qa_verdict", "PASS"),
                        "qa_score": str(piece.get("qa_score", 0)),
                        "content_type": key,
                    }
                })
        count = self.store_batch(items)
        print(f"[ContentDB] Indexed {count}/{len(items)} approved pieces into ChromaDB")
        return count

    def count(self) -> int:
        col = self._get_collection()
        return col.count() if col else 0


def _chunk_text(text: str, max_chars: int = 500) -> list:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    words = text.split()
    current = []
    char_count = 0
    for word in words:
        if char_count + len(word) + 1 > max_chars and current:
            chunks.append(" ".join(current))
            current = [word]
            char_count = len(word)
        else:
            current.append(word)
            char_count += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


# ═══════════════════════════════════════════════════════════════════
# LearningDB — Qdrant for long-term learning persistence
# ═══════════════════════════════════════════════════════════════════

class LearningDB:
    """
    Stores learning patterns in Qdrant (already running on server).
    Falls back to SQLite learning_state table if Qdrant unavailable.
    """
    COLLECTION = "shipstack_learning"
    VECTOR_SIZE = 384  # all-MiniLM-L6-v2 on server

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=5)
            # Create collection if needed
            collections = [c.name for c in client.get_collections().collections]
            if self.COLLECTION not in collections:
                client.create_collection(
                    collection_name=self.COLLECTION,
                    vectors_config=VectorParams(size=self.VECTOR_SIZE, distance=Distance.COSINE)
                )
            self._client = client
            return client
        except Exception as e:
            print(f"[LearningDB] Qdrant unavailable ({e}) — using SQLite fallback")
            return None

    @property
    def backend(self) -> str:
        return "qdrant" if self._get_client() else "sqlite"

    # ── High-level methods used by LearningEngine ─────────────────────────────

    def load_master(self) -> dict:
        """Load master knowledge state from SQLite."""
        return self._sqlite_load("master_knowledge")

    def save_master(self, data: dict):
        """Persist master knowledge state to SQLite (and mirror key metrics to Qdrant)."""
        self._sqlite_store("master_knowledge", data)

    def log_event(self, event_type: str, message: str):
        """Append to improvement_log table."""
        now = datetime.now().isoformat()
        with db_conn() as conn:
            conn.execute(
                "INSERT INTO improvement_log (timestamp, event_type, message) VALUES (?,?,?)",
                (now, event_type, message)
            )

    def store_winner(self, content: str, metadata: dict):
        """Store a winning content piece as a vector in Qdrant for semantic retrieval."""
        client = self._get_client()
        if client:
            try:
                from qdrant_client.models import PointStruct
                embedding = self._embed(content)
                if embedding:
                    import hashlib
                    point_id = int(hashlib.md5(content[:200].encode()).hexdigest(), 16) % (10**9)
                    client.upsert(
                        collection_name=self.COLLECTION,
                        points=[PointStruct(
                            id=point_id,
                            vector=embedding,
                            payload={k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                                     for k, v in metadata.items()},
                        )]
                    )
                    return
            except Exception as e:
                print(f"[LearningDB] store_winner Qdrant error: {e}")
        # SQLite fallback — store as learning_state entry
        key = f"winner:{datetime.now().isoformat()}"
        self._sqlite_store(key, {"content": content[:500], **metadata})

    def find_similar_winners(self, query: str, n: int = 5) -> list:
        """Semantic search for past winners similar to this content."""
        return self.find_similar_patterns(query, n=n)

    def store_pattern(self, pattern_type: str, pattern: str, metadata: dict, score: float = 0.0):
        """Store a winning pattern (hook, CTA, emotion, etc.) in Qdrant."""
        client = self._get_client()
        if client:
            try:
                from qdrant_client.models import PointStruct
                embedding = self._embed(f"{pattern_type}: {pattern}")
                if embedding:
                    client.upsert(
                        collection_name=self.COLLECTION,
                        points=[PointStruct(
                            id=abs(hash(f"{pattern_type}:{pattern}")) % (10**9),
                            vector=embedding,
                            payload={
                                "pattern_type": pattern_type,
                                "pattern": pattern,
                                "score": score,
                                "stored_at": datetime.now().isoformat(),
                                **{k: str(v) for k, v in metadata.items()},
                            }
                        )]
                    )
                    return
            except Exception as e:
                print(f"[LearningDB] Qdrant store error: {e}")
        # SQLite fallback
        self._sqlite_store(f"{pattern_type}:{pattern}", {"pattern": pattern, "score": score, **metadata})

    def find_similar_patterns(self, query: str, pattern_type: str = None, n: int = 10) -> list:
        """Find patterns similar to query — power Ollama prompt synthesis."""
        client = self._get_client()
        if client:
            try:
                embedding = self._embed(query)
                if embedding:
                    filt = None
                    if pattern_type:
                        from qdrant_client.models import Filter, FieldCondition, MatchValue
                        filt = Filter(must=[FieldCondition(
                            key="pattern_type", match=MatchValue(value=pattern_type)
                        )])
                    results = client.search(
                        collection_name=self.COLLECTION,
                        query_vector=embedding,
                        limit=n,
                        query_filter=filt,
                        with_payload=True,
                    )
                    return [{"pattern": r.payload.get("pattern"), "score": r.score,
                             "metadata": r.payload} for r in results]
            except Exception as e:
                print(f"[LearningDB] Qdrant search error: {e}")
        return self._sqlite_list(pattern_type)

    def store_master_state(self, key: str, data: dict):
        """Persist learning state — survives server restart."""
        self._sqlite_store(key, data)

    def load_master_state(self, key: str) -> dict:
        return self._sqlite_load(key)

    def _embed(self, text: str) -> list:
        """Get embedding from Ollama (nomic-embed-text, 768-dim)
           or return None if unavailable."""
        try:
            import requests
            _ollama_base = f"http://{os.getenv('OLLAMA_HOST', '127.0.0.1')}:{os.getenv('OLLAMA_PORT', '11434')}"
            r = requests.post(
                f"{_ollama_base}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
                timeout=10
            )
            if r.ok:
                emb = r.json().get("embedding", [])
                # Qdrant server uses 384-dim — truncate/pad if needed
                if len(emb) > self.VECTOR_SIZE:
                    return emb[:self.VECTOR_SIZE]
                elif len(emb) < self.VECTOR_SIZE:
                    return emb + [0.0] * (self.VECTOR_SIZE - len(emb))
                return emb
        except:
            pass
        return None

    def _sqlite_store(self, key: str, data: dict):
        now = datetime.now().isoformat()
        with db_conn() as conn:
            conn.execute("""
                INSERT INTO learning_state (key, value_json, updated)
                VALUES (?,?,?)
                ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated=excluded.updated
            """, (key, json.dumps(data), now))

    def _sqlite_load(self, key: str) -> dict:
        with db_conn() as conn:
            row = conn.execute("SELECT value_json FROM learning_state WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else {}

    def _sqlite_list(self, pattern_type: str = None, limit: int = 20) -> list:
        sql = "SELECT key, value_json FROM learning_state WHERE 1=1"
        params = []
        if pattern_type:
            sql += " AND key LIKE ?"; params.append(f"{pattern_type}:%")
        sql += f" ORDER BY updated DESC LIMIT {limit}"
        with db_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [json.loads(r[1]) for r in rows]


# ═══════════════════════════════════════════════════════════════════
# Migration runner — call once to move from JSON → DB
# ═══════════════════════════════════════════════════════════════════

def run_migration():
    """One-time migration of all JSON files into SQLite + ChromaDB."""
    print("\n[Migration] Starting ShipStack JSON → Database migration…")
    init_db()

    profile_db = ProfileDB()
    ab_db      = ABTestDB()

    p_count = profile_db.migrate_from_json()
    ab_count = ab_db.migrate_from_json()

    # Migrate learning state
    learning_db = LearningDB()
    master_path = DATA_DIR / "learning" / "master_knowledge.json"
    if master_path.exists():
        data = json.loads(master_path.read_text())
        learning_db.store_master_state("master_knowledge", data)
        print(f"[Migration] Learning state migrated → SQLite/Qdrant")

    print(f"\n[Migration] Complete:")
    print(f"  Profiles migrated : {p_count}")
    print(f"  AB tests migrated : {ab_count}")
    print(f"  SQLite DB         : {SQLITE_PATH}")
    print(f"  ChromaDB          : {CHROMA_PATH}")
    print(f"  Qdrant            : {QDRANT_HOST}:{QDRANT_PORT}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "migrate":
        run_migration()
    elif len(sys.argv) >= 2 and sys.argv[1] == "init":
        init_db()
        print("SQLite initialized.")
    elif len(sys.argv) >= 2 and sys.argv[1] == "status":
        init_db()
        p = ProfileDB()
        a = ABTestDB()
        c = ContentDB()
        print(f"Profiles    : {p.stats()}")
        print(f"AB Tests    : {a.dashboard_data()['total_tests']}")
        print(f"Content vecs: {c.count()}")
    else:
        print("Usage:")
        print("  python db.py migrate   — move JSON → SQLite+ChromaDB+Qdrant")
        print("  python db.py init      — create SQLite tables")
        print("  python db.py status    — show counts")
