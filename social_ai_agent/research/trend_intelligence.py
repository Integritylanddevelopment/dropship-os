"""
research/trend_intelligence.py — Enterprise Trend Intelligence Engine
Google Trends signals + Qdrant vector memory for semantic research recall.
Tells the agent WHAT is trending NOW and WHERE attention is cheapest.
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

# ── Google Trends ──────────────────────────────────────────
try:
    from pytrends.request import TrendReq
    TRENDS_AVAILABLE = True
except ImportError:
    TRENDS_AVAILABLE = False

# ── Qdrant Vector Memory ───────────────────────────────────
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct, Filter,
        FieldCondition, MatchValue, SearchRequest
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False


DATA_DIR = Path(__file__).parent.parent / "data"
QDRANT_PATH = str(DATA_DIR / "qdrant_store")


class TrendIntelligence:
    """
    Enterprise-grade trend + memory system.
    - Pulls real-time Google Trends signals for your niche
    - Stores all research intel as vector embeddings in Qdrant
    - Semantically retrieves relevant past intel to inform new content
    - Identifies trending angles before competitors
    """

    def __init__(self):
        self.niche = config.niche
        self._trends = None
        self._qdrant = None
        self._embedder = None
        self._collection = "social_intel"
        self._setup()

    def _setup(self):
        # Google Trends
        if TRENDS_AVAILABLE:
            try:
                self._trends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
                logger.info("Google Trends initialized")
            except Exception as e:
                logger.warning(f"Google Trends init failed: {e}")

        # Qdrant local vector store
        if QDRANT_AVAILABLE:
            try:
                (DATA_DIR / "qdrant_store").mkdir(parents=True, exist_ok=True)
                self._qdrant = QdrantClient(path=QDRANT_PATH)
                self._init_collection()
                logger.info("Qdrant vector store initialized")
            except Exception as e:
                logger.warning(f"Qdrant init failed: {e}")

        # Sentence embeddings
        if EMBEDDINGS_AVAILABLE:
            try:
                _embedding_model = os.getenv("QDRANT_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
                self._embedder = SentenceTransformer(_embedding_model)
                logger.info(f"Sentence embedder loaded ({_embedding_model})")
            except Exception as e:
                logger.warning(f"Embedder load failed: {e}")

    def _init_collection(self):
        """Create Qdrant collection if it doesn't exist"""
        try:
            existing = [c.name for c in self._qdrant.get_collections().collections]
            if self._collection not in existing:
                self._qdrant.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {self._collection}")
        except Exception as e:
            logger.error(f"Collection init failed: {e}")

    # ─────────────────────────────────────────────
    # GOOGLE TRENDS
    # ─────────────────────────────────────────────

    async def get_trending_keywords(
        self,
        seed_keywords: list = None,
        timeframe: str = "today 1-m",
        geo: str = "US"
    ) -> dict:
        """
        Get Google Trends data for keywords.
        Returns interest-over-time + related rising queries.
        """
        if not self._trends:
            return {"error": "Google Trends not available", "fallback": seed_keywords or []}

        seeds = seed_keywords or [self.niche] + config.target_products[:3]
        seeds = seeds[:5]  # Trends API limit

        result = {
            "seeds": seeds,
            "timeframe": timeframe,
            "interest_over_time": {},
            "rising_queries": {},
            "top_queries": {},
            "trending_breakouts": [],
            "generated_at": datetime.utcnow().isoformat(),
        }

        try:
            loop = asyncio.get_event_loop()

            def _fetch():
                self._trends.build_payload(seeds, timeframe=timeframe, geo=geo)
                iot = self._trends.interest_over_time()
                related = self._trends.related_queries()
                return iot, related

            iot, related = await loop.run_in_executor(None, _fetch)

            if not iot.empty:
                # Get last 4 weeks trend
                for kw in seeds:
                    if kw in iot.columns:
                        values = iot[kw].tolist()[-4:]
                        result["interest_over_time"][kw] = {
                            "recent_values": values,
                            "trend": "rising" if values[-1] > values[0] else "falling",
                            "peak": max(values),
                        }

            if related:
                for kw in seeds:
                    kw_data = related.get(kw, {})
                    if kw_data:
                        rising = kw_data.get("rising")
                        top = kw_data.get("top")
                        if rising is not None and not rising.empty:
                            result["rising_queries"][kw] = rising["query"].tolist()[:10]
                        if top is not None and not top.empty:
                            result["top_queries"][kw] = top["query"].tolist()[:10]

            # Find breakout queries (rising_queries with very high % change)
            all_rising = []
            for kw, queries in result["rising_queries"].items():
                all_rising.extend(queries)
            result["trending_breakouts"] = list(set(all_rising))[:15]

            logger.info(f"Google Trends fetched for {seeds}")

        except Exception as e:
            logger.error(f"Google Trends fetch error: {e}")

        return result

    async def get_daily_trend_signals(self) -> dict:
        """
        Daily trend signal pass — what's rising TODAY that we should post about.
        Returns prioritized content angles based on trend velocity.
        """
        trend_data = await self.get_trending_keywords(timeframe="today 7-d")

        content_signals = {
            "hot_right_now": [],
            "rising_fast": [],
            "evergreen_stable": [],
            "declining_avoid": [],
        }

        for kw, data in trend_data.get("interest_over_time", {}).items():
            values = data.get("recent_values", [0])
            if not values:
                continue

            trend = data.get("trend")
            peak = data.get("peak", 0)

            if trend == "rising" and peak > 70:
                content_signals["hot_right_now"].append(kw)
            elif trend == "rising" and peak > 40:
                content_signals["rising_fast"].append(kw)
            elif trend == "falling":
                content_signals["declining_avoid"].append(kw)
            else:
                content_signals["evergreen_stable"].append(kw)

        # Add rising queries as angles
        for kw, queries in trend_data.get("rising_queries", {}).items():
            content_signals["hot_right_now"].extend(queries[:3])

        content_signals["recommended_angle"] = (
            content_signals["hot_right_now"][:1] or
            content_signals["rising_fast"][:1] or
            content_signals["evergreen_stable"][:1]
        )

        return content_signals

    # ─────────────────────────────────────────────
    # QDRANT VECTOR MEMORY
    # ─────────────────────────────────────────────

    def store_intel(self, text: str, metadata: dict = None) -> bool:
        """
        Store a research insight as a vector embedding.
        Everything we learn gets stored here for future retrieval.
        """
        if not self._qdrant or not self._embedder:
            logger.warning("Vector store not available")
            return False

        try:
            embedding = self._embedder.encode(text).tolist()

            import time
            point_id = int(time.time() * 1000) % (2**31)

            payload = {
                "text": text,
                "niche": self.niche,
                "stored_at": datetime.utcnow().isoformat(),
                **(metadata or {}),
            }

            self._qdrant.upsert(
                collection_name=self._collection,
                points=[PointStruct(id=point_id, vector=embedding, payload=payload)],
            )
            return True

        except Exception as e:
            logger.error(f"Vector store failed: {e}")
            return False

    def recall_similar(self, query: str, top_k: int = 5, intel_type: str = None) -> list:
        """
        Semantically retrieve past research intel similar to a query.
        Used before generating content — feeds the AI relevant past learnings.
        """
        if not self._qdrant or not self._embedder:
            return []

        try:
            query_vec = self._embedder.encode(query).tolist()

            filter_condition = None
            if intel_type:
                filter_condition = Filter(
                    must=[FieldCondition(key="intel_type", match=MatchValue(value=intel_type))]
                )

            results = self._qdrant.search(
                collection_name=self._collection,
                query_vector=query_vec,
                limit=top_k,
                query_filter=filter_condition,
                with_payload=True,
            )

            return [
                {
                    "text": r.payload.get("text", ""),
                    "score": round(r.score, 3),
                    "intel_type": r.payload.get("intel_type", ""),
                    "stored_at": r.payload.get("stored_at", ""),
                }
                for r in results
            ]

        except Exception as e:
            logger.error(f"Vector recall failed: {e}")
            return []

    def store_research_batch(self, intel_list: list):
        """Bulk store research intel from a market research pass"""
        stored = 0
        for item in intel_list:
            if isinstance(item, dict):
                text = item.get("content", item.get("text", str(item)))
                metadata = {k: v for k, v in item.items() if k not in ["content", "text"]}
            else:
                text = str(item)
                metadata = {}

            if text and len(text) > 20:
                if self.store_intel(text, metadata):
                    stored += 1

        logger.info(f"Stored {stored}/{len(intel_list)} intel items in vector memory")
        return stored

    def get_collection_stats(self) -> dict:
        """Get vector store collection statistics"""
        if not self._qdrant:
            return {"status": "not_initialized"}
        try:
            info = self._qdrant.get_collection(self._collection)
            return {
                "total_vectors": info.points_count,
                "collection": self._collection,
                "status": "active",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ─────────────────────────────────────────────
    # COMBINED INTELLIGENCE
    # ─────────────────────────────────────────────

    async def get_content_brief(self, topic: str, platform: str = "reddit") -> dict:
        """
        Generate a content brief combining:
        - Current trend signals (Google Trends)
        - Relevant past research intel (Qdrant recall)
        - Platform-specific angle recommendations
        """
        # Get trend signals
        trends = await self.get_daily_trend_signals()

        # Recall relevant past intel
        past_intel = self.recall_similar(
            f"{platform} content about {topic} in {self.niche}",
            top_k=5
        )

        # Get pain points from memory
        pain_points = self.recall_similar(f"pain points {topic}", top_k=3, intel_type="pain_point")
        language = self.recall_similar(f"customer language {topic}", top_k=3, intel_type="language")

        return {
            "topic": topic,
            "platform": platform,
            "trending_angles": trends.get("hot_right_now", [])[:3],
            "rising_angles": trends.get("rising_fast", [])[:3],
            "relevant_past_intel": past_intel,
            "known_pain_points": [p["text"] for p in pain_points],
            "customer_language": [l["text"] for l in language],
            "recommended_angle": trends.get("recommended_angle", [topic]),
            "avoid_topics": trends.get("declining_avoid", []),
        }


# Singleton
trend_intel = TrendIntelligence()
