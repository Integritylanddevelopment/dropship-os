import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
#!/usr/bin/env python3
"""
ShipStack Engine — Core HTTP API Server
========================================

Flask microservice on port 8889 that wires together:
- DecisionEngine (product scoring & ranking)
- ProductResearcher (supplier aggregation)
- Discovery pipeline (signal collection & clustering)

All LLM calls route through Quinn bridge at http://127.0.0.1:8765.
"""

import os
import json
import time
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

# ── Environment ──────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    load_dotenv(Path(__file__).parent.parent / ".env.local", override=True)
except ImportError:
    pass

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
)
logger = logging.getLogger("shipstack_engine")

# ── Flask ────────────────────────────────────────────────────────────────
from flask import Flask, request, jsonify

app = Flask(__name__)

# ── Constants ────────────────────────────────────────────────────────────
SHIPSTACK_ROOT = Path(__file__).parent.parent
PORT = int(os.getenv("SHIPSTACK_ENGINE_PORT", 8889))
VERSION = "1.0.0"
START_TIME = time.time()

# ── Subsystem Imports (graceful degradation) ─────────────────────────────

# Decision Engine
DecisionEngine = None
Product = None
try:
    sys.path.insert(0, str(SHIPSTACK_ROOT))
    from engines.decision_engine import DecisionEngine, Product, Decision
    logger.info("DecisionEngine loaded")
except Exception as e:
    logger.warning(f"DecisionEngine unavailable: {e}")

# Product Researcher
ProductResearcher = None
try:
    from agents.product_research import ProductResearcher, ProductDB
    logger.info("ProductResearcher loaded")
except Exception as e:
    logger.warning(f"ProductResearcher unavailable: {e}")

# Discovery Pipeline
discovery_pipeline = None
try:
    from discovery_engine import pipeline as discovery_pipeline
    logger.info("Discovery pipeline loaded")
except Exception as e:
    logger.warning(f"Discovery pipeline unavailable: {e}")

# Badge system
badge_module = None
try:
    from badge.shipstack_badge import validate_token, log_action
    badge_module = True
    logger.info("Badge system loaded")
except Exception as e:
    logger.warning(f"Badge system unavailable: {e}")


# ── CORS ─────────────────────────────────────────────────────────────────

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Badge-Issued-At"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        return "", 204


# ── Helpers ──────────────────────────────────────────────────────────────

def _product_from_dict(d: dict):
    """Convert a raw dict into a Product dataclass, filling defaults."""
    if Product is None:
        return None
    return Product(
        id=d.get("id", f"p_{int(time.time()*1000)}"),
        title=d.get("title", "Unknown"),
        price=float(d.get("price", 0)),
        supplier=d.get("supplier", "unknown"),
        reviews=int(d.get("reviews", 0)),
        rating=float(d.get("rating", 0.0)),
        niche=d.get("niche", "general"),
        description=d.get("description", ""),
    )


def _require(subsystem, name: str):
    """Return a 503 response if a subsystem is missing."""
    if subsystem is None:
        return jsonify({
            "error": f"{name} is not available",
            "detail": f"The {name} subsystem failed to import. Check server logs.",
        }), 503
    return None


# ── Routes ───────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    uptime_sec = round(time.time() - START_TIME, 1)
    return jsonify({
        "status": "healthy",
        "service": "ShipStack Engine",
        "version": VERSION,
        "port": PORT,
        "uptime_seconds": uptime_sec,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "subsystems": {
            "decision_engine": DecisionEngine is not None,
            "product_researcher": ProductResearcher is not None,
            "discovery_pipeline": discovery_pipeline is not None,
            "badge_system": badge_module is not None,
        },
    })


@app.route("/api/discover", methods=["POST"])
def api_discover():
    """Run discovery pipeline — collect signals, cluster, score."""
    err = _require(discovery_pipeline, "Discovery pipeline")
    if err:
        return err

    body = request.get_json(silent=True) or {}
    keywords = body.get("query")
    sources = body.get("sources")

    try:
        # Build kwargs for pipeline.run()
        kwargs = {"verbose": False}
        if keywords:
            kwargs["keywords"] = [keywords] if isinstance(keywords, str) else keywords
        if sources:
            kwargs["subreddits"] = sources if isinstance(sources, list) else [sources]

        result = discovery_pipeline.run(**kwargs)
        return jsonify({
            "status": "ok",
            "total_signals": result.get("total_signals", 0),
            "n_clusters": result.get("n_clusters", 0),
            "n_reports": result.get("n_reports", 0),
            "reports": result.get("reports", []),
            "elapsed_sec": result.get("elapsed_sec", 0),
        })
    except Exception as e:
        logger.exception("Discovery pipeline error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/score", methods=["POST"])
def api_score():
    """Score a single product through DecisionEngine."""
    err = _require(DecisionEngine, "DecisionEngine")
    if err:
        return err

    body = request.get_json(silent=True) or {}
    product_data = body.get("product") or body
    target_niches = body.get("target_niches")

    try:
        product = _product_from_dict(product_data)
        engine = DecisionEngine()
        decision = engine.decide(product, target_niches)
        return jsonify({
            "status": "ok",
            "decision": asdict(decision),
        })
    except Exception as e:
        logger.exception("Score error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/research", methods=["POST"])
def api_research():
    """Search suppliers via ProductResearcher."""
    err = _require(ProductResearcher, "ProductResearcher")
    if err:
        return err

    body = request.get_json(silent=True) or {}
    query = body.get("query", body.get("search_term", ""))
    suppliers = body.get("suppliers")
    limit = int(body.get("limit", 20))

    if not query:
        return jsonify({"error": "Missing 'query' parameter"}), 400

    try:
        researcher = ProductResearcher()
        results = researcher.research(query, suppliers=suppliers, limit=limit)
        return jsonify({
            "status": "ok",
            "query": query,
            "count": len(results),
            "products": results,
        })
    except NotImplementedError as e:
        return jsonify({
            "status": "stub",
            "query": query,
            "count": 0,
            "products": [],
            "detail": "Supplier APIs are stubbed — real keys not configured yet.",
        })
    except Exception as e:
        logger.exception("Research error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    """Full pipeline: discover -> score -> rank -> top N."""
    err = _require(discovery_pipeline, "Discovery pipeline")
    if err:
        return err
    err = _require(DecisionEngine, "DecisionEngine")
    if err:
        return err

    body = request.get_json(silent=True) or {}
    limit = int(body.get("limit", 10))
    keywords = body.get("query")
    target_niches = body.get("target_niches")

    try:
        # Step 1: Discover
        pipeline_kwargs = {"verbose": False}
        if keywords:
            pipeline_kwargs["keywords"] = [keywords] if isinstance(keywords, str) else keywords

        pipeline_result = discovery_pipeline.run(**pipeline_kwargs)
        reports = pipeline_result.get("reports", [])

        if not reports:
            return jsonify({
                "status": "ok",
                "count": 0,
                "recommendations": [],
                "detail": "No products found from discovery pipeline.",
            })

        # Step 2: Convert reports to Product objects for scoring
        products = []
        for rpt in reports:
            products.append(Product(
                id=rpt.get("keyword", f"r_{len(products)}"),
                title=rpt.get("keyword", "Unknown"),
                price=rpt.get("avg_price", 5.0) if "avg_price" in rpt else 5.0,
                supplier=rpt.get("top_supplier", "mixed"),
                reviews=rpt.get("signal_count", len(rpt.get("signals", []))),
                rating=rpt.get("avg_rating", 4.0) if "avg_rating" in rpt else 4.0,
                niche=rpt.get("keyword", "general"),
                description=rpt.get("summary", ""),
            ))

        # Step 3: Rank
        engine = DecisionEngine()
        rankings = engine.rank(products, target_niches)

        # Step 4: Top N
        top = rankings[:limit]

        return jsonify({
            "status": "ok",
            "count": len(top),
            "total_signals": pipeline_result.get("total_signals", 0),
            "recommendations": [asdict(d) for d in top],
        })
    except Exception as e:
        logger.exception("Recommend pipeline error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/decide", methods=["POST"])
def api_decide():
    """
    Accept product data, return scored rankings + channel recommendations.
    This is the endpoint the integration tests expect.

    Expected payload:
        {
            "products": [{"id": "p1", "title": "...", "price": 5.0, "niche": "..."}],
            "context": {"budget_per_unit": 8.0}
        }

    Returns:
        {"rankings": [{"product_id": ..., "score": ..., ...}]}
    """
    err = _require(DecisionEngine, "DecisionEngine")
    if err:
        return err

    body = request.get_json(silent=True) or {}
    raw_products = body.get("products", [])
    context = body.get("context", {})
    target_niches = body.get("target_niches")

    if not raw_products:
        return jsonify({"error": "Missing 'products' list"}), 400

    try:
        products = []
        for p in raw_products:
            products.append(_product_from_dict(p))

        engine = DecisionEngine()
        rankings = engine.rank(products, target_niches)

        # Add channel recommendations based on score
        results = []
        for decision in rankings:
            d = asdict(decision)
            # Simple channel recommendation
            if decision.score >= 0.75:
                d["channels"] = ["tiktok", "instagram", "pinterest"]
            elif decision.score >= 0.50:
                d["channels"] = ["pinterest", "instagram"]
            else:
                d["channels"] = ["pinterest"]
            results.append(d)

        return jsonify({
            "status": "ok",
            "rankings": results,
            "context": context,
        })
    except Exception as e:
        logger.exception("Decide error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/products", methods=["GET"])
def api_products():
    """Return cached/recent products from SQLite."""
    limit = int(request.args.get("limit", 50))
    search = request.args.get("q", "%")

    try:
        if ProductResearcher is not None:
            db = ProductDB()
        else:
            # Fall back to direct SQLite if ProductResearcher didn't import
            db_path = SHIPSTACK_ROOT / "agents" / "data" / "products.db"
            if not db_path.exists():
                return jsonify({"status": "ok", "count": 0, "products": []})
            db = None

        if db is not None:
            products = db.get_products(search, limit=limit)
        else:
            # Direct query
            db_path = SHIPSTACK_ROOT / "agents" / "data" / "products.db"
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM products ORDER BY cached_at DESC LIMIT ?", (limit,)
            ).fetchall()
            conn.close()
            products = [dict(r) for r in rows]

        return jsonify({
            "status": "ok",
            "count": len(products),
            "products": products,
        })
    except Exception as e:
        logger.exception("Products fetch error")
        return jsonify({"error": str(e)}), 500


# ── Entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"Starting ShipStack Engine on port {PORT}")
    logger.info(f"SHIPSTACK_ROOT: {SHIPSTACK_ROOT}")
    logger.info(f"Subsystems: DecisionEngine={DecisionEngine is not None}, "
                f"ProductResearcher={ProductResearcher is not None}, "
                f"DiscoveryPipeline={discovery_pipeline is not None}")

    app.run(host="0.0.0.0", port=PORT, debug=False)
