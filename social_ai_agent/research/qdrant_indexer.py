"""
research/qdrant_indexer.py — Stores trend research results in Qdrant
Uses sentence-transformers (all-MiniLM-L6-v2, 384-dim) to match the
existing Qdrant server collections.

Qdrant host: configured via QDRANT_HOST / QDRANT_PORT env vars
Collection:  configured via QDRANT_COLLECTION env var
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass

import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("qdrant-client not installed. Run: pip install qdrant-client --break-system-packages")

try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Run: pip install sentence-transformers --break-system-packages")


QDRANT_HOST = os.getenv("QDRANT_HOST", "192.168.1.123")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION = os.getenv("QDRANT_COLLECTION", "general_knowledge")
VECTOR_DIM = 384
EMBEDDING_MODEL = os.getenv("QDRANT_EMBEDDING_MODEL", "all-MiniLM-L6-v2")


class QdrantIndexer:
    """
    Stores dropship research results in the Qdrant memory stack.
    Falls back to JSON-only if Qdrant is unreachable.
    """

    def __init__(self, host: str = QDRANT_HOST, port: int = QDRANT_PORT):
        self.host = host
        self.port = port
        self.client = None
        self.model = None
        self._connect()

    def _connect(self):
        if not QDRANT_AVAILABLE or not ST_AVAILABLE:
            logger.warning("[QdrantIndexer] Missing dependencies — JSON-only mode")
            return
        try:
            self.client = QdrantClient(host=self.host, port=self.port, timeout=5)
            self.client.get_collection(COLLECTION)
            self.model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info(f"[QdrantIndexer] Connected to {self.host}:{self.port} — collection: {COLLECTION}")
        except Exception as e:
            logger.warning(f"[QdrantIndexer] Qdrant unavailable ({e}) — JSON-only mode")
            self.client = None

    def index_trend_results(self, results: dict) -> int:
        """
        Indexes a trend research result set into Qdrant.
        Each top combo becomes a searchable document.
        Returns number of points indexed.
        """
        points = self._build_points(results)

        if not points:
            return 0

        # Always save to JSON as backup
        self._save_to_json(results)

        if self.client is None:
            print(f"[QdrantIndexer] Qdrant offline — {len(points)} records saved to JSON only")
            return 0

        try:
            self.client.upsert(collection_name=COLLECTION, points=points)
            print(f"[QdrantIndexer] Indexed {len(points)} records → {COLLECTION}")
            return len(points)
        except Exception as e:
            logger.error(f"[QdrantIndexer] Upsert failed: {e}")
            return 0

    def _build_points(self, results: dict) -> list:
        if self.model is None:
            return []

        points = []
        ts = results.get("generated_at", datetime.utcnow().isoformat())

        # Index each top combo
        for combo in results.get("top_combos", [])[:20]:
            text = (
                f"Dropship combo: {combo['niche']} on {combo['channel']}. "
                f"Score: {combo['score']}. Margin: {combo['margin_pct']}%. "
                f"CPM: ${combo['cpm']}. Trend: {combo['trend']}. "
                f"Action: {combo['action']}. Supplier: {combo['supplier']}."
            )
            vector = self.model.encode(text).tolist()
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text": text,
                    "source": "dropship_trend_engine",
                    "type": "product_channel_combo",
                    "niche": combo["niche"],
                    "channel": combo["channel"],
                    "score": combo["score"],
                    "action": combo["action"],
                    "generated_at": ts,
                    "project": "dropshipping",
                }
            ))

        # Index the overall decision summary
        top3 = results.get("decision", {}).get("scale", [])[:3]
        if top3:
            summary_text = (
                f"Dropship Decision Engine — {ts[:10]}. "
                f"Top 3 combos to scale: "
                + " | ".join([f"{c['niche']} × {c['channel']} (score {c['score']})" for c in top3])
                + f". Cheapest channel: {results['channel_rankings'][0]['channel']} at ${results['channel_rankings'][0]['cpm']} CPM."
            )
            vector = self.model.encode(summary_text).tolist()
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text": summary_text,
                    "source": "dropship_decision_summary",
                    "type": "weekly_decision",
                    "generated_at": ts,
                    "project": "dropshipping",
                }
            ))

        return points

    def _save_to_json(self, results: dict):
        data_dir = Path(__file__).parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        out = data_dir / "trend_results.json"
        with open(out, "w") as f:
            json.dump(results, f, indent=2, default=str)
