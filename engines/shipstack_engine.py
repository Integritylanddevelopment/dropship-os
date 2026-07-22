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
from flask import Flask, request, jsonify, send_file, send_from_directory

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


# ── Mission Control (one-button pipeline UI) ─────────────────────────────

mission_pipeline = None
try:
    from engines import mission_pipeline
    logger.info("Mission pipeline loaded")
except Exception as e:
    logger.warning(f"Mission pipeline unavailable: {e}")

FRONTEND_DIR = SHIPSTACK_ROOT / "frontend"
CARDS_DIR = SHIPSTACK_ROOT / "pinterest_cards"


@app.route("/", methods=["GET"])
def mission_control_ui():
    """Serve the Mission Control interface."""
    ui = FRONTEND_DIR / "mission_control.html"
    if ui.exists():
        return send_file(str(ui))
    return jsonify({"error": "mission_control.html not found", "hint": str(ui)}), 404


@app.route("/cards/<path:filename>", methods=["GET"])
def serve_card(filename):
    """Serve generated card images for UI preview."""
    return send_from_directory(str(CARDS_DIR), filename)


@app.route("/api/pipeline/start", methods=["POST"])
def api_pipeline_start():
    err = _require(mission_pipeline, "Mission pipeline")
    if err:
        return err
    body = request.get_json(silent=True) or {}
    result = mission_pipeline.start_run(
        query=body.get("query") or None,
        platforms=body.get("platforms") or ["pinterest"],
        limit=int(body.get("limit", 5)),
        dry_run=bool(body.get("dry_run", False)),
    )
    return jsonify(result), (200 if result.get("ok") else 409)


@app.route("/api/pipeline/status", methods=["GET"])
def api_pipeline_status():
    err = _require(mission_pipeline, "Mission pipeline")
    if err:
        return err
    return jsonify(mission_pipeline.get_status())


@app.route("/api/library", methods=["GET"])
def api_library():
    """Every product ever gathered + its collateral. Survives restarts."""
    err = _require(mission_pipeline, "Mission pipeline")
    if err:
        return err
    return jsonify({"products": mission_pipeline.load_library()})


@app.route("/api/product/regenerate", methods=["POST"])
def api_product_regenerate():
    """Create/redo ads for one product, or retry a single ad (context-injected)."""
    err = _require(mission_pipeline, "Mission pipeline")
    if err:
        return err
    body = request.get_json(silent=True) or {}
    pid = body.get("product_id", "")
    if not pid:
        return jsonify({"ok": False, "error": "product_id required"}), 400
    variant = body.get("variant")
    variant = int(variant) if variant is not None else None
    result = mission_pipeline.start_regen(pid, variant)
    return jsonify(result), (200 if result.get("ok") else 409)


@app.route("/api/regen/status", methods=["GET"])
def api_regen_status():
    err = _require(mission_pipeline, "Mission pipeline")
    if err:
        return err
    return jsonify(mission_pipeline.get_regen_status())


# ── Orders + auto-fulfillment ────────────────────────────────────────────

order_fulfillment = None
try:
    from integrations import order_fulfillment
    logger.info("Order fulfillment loaded")
except Exception as e:
    logger.warning(f"Order fulfillment unavailable: {e}")


@app.route("/api/orders", methods=["GET"])
def api_orders():
    err = _require(order_fulfillment, "Order fulfillment")
    if err:
        return err
    orders = order_fulfillment.list_orders()
    revenue = sum(o.get("amount", 0) for o in orders if o.get("status") != "failed")
    return jsonify({"orders": orders, "count": len(orders),
                    "revenue": round(revenue, 2),
                    "auto": order_fulfillment.AUTO_FULFILL})


@app.route("/api/orders/refresh", methods=["POST"])
def api_orders_refresh():
    err = _require(order_fulfillment, "Order fulfillment")
    if err:
        return err
    return jsonify(order_fulfillment.process_cycle())


@app.route("/api/orders/fulfill", methods=["POST"])
def api_orders_fulfill():
    err = _require(order_fulfillment, "Order fulfillment")
    if err:
        return err
    body = request.get_json(silent=True) or {}
    sid = body.get("session_id", "")
    if not sid:
        return jsonify({"ok": False, "error": "session_id required"}), 400
    return jsonify(order_fulfillment.fulfill_order(sid, force=bool(body.get("force"))))


@app.route("/api/orders/done", methods=["POST"])
def api_orders_done():
    err = _require(order_fulfillment, "Order fulfillment")
    if err:
        return err
    body = request.get_json(silent=True) or {}
    return jsonify(order_fulfillment.mark_done(body.get("session_id", "")))


@app.route("/api/services", methods=["GET"])
def api_services():
    """Health check across all ShipStack services for the UI status bar."""
    import requests as _rq
    services = {
        "engine": {"url": f"http://127.0.0.1:{PORT}", "up": True},
        "social": {"url": "http://127.0.0.1:8867", "up": False},
        "prometheus": {"url": "http://127.0.0.1:8766", "up": False},
        "quinn": {"url": "http://127.0.0.1:8765", "up": False},
    }
    for name in ("social", "prometheus", "quinn"):
        try:
            r = _rq.get(f"{services[name]['url']}/health", timeout=3)
            services[name]["up"] = r.ok
        except Exception:
            services[name]["up"] = False
    # platform posting readiness
    platforms = {
        "pinterest": bool(os.getenv("PINTEREST_ACCESS_TOKEN")),
        "youtube": all([os.getenv("YOUTUBE_CLIENT_ID"), os.getenv("YOUTUBE_CLIENT_SECRET"), os.getenv("YOUTUBE_REFRESH_TOKEN")]),
        "tiktok": bool(os.getenv("TIKTOK_ACCESS_TOKEN")),
        "instagram": bool(os.getenv("META_ACCESS_TOKEN")),
    }
    hosting = all([os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_PAGES_REPO")])
    return jsonify({"services": services, "platforms": platforms, "image_hosting": hosting})


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

    # Order watcher: checks Stripe every 5 min, auto-fulfills at CJ
    if order_fulfillment is not None:
        try:
            order_fulfillment.start_background_loop(300)
            logger.info("Order auto-fulfillment loop started (every 5 min)")
        except Exception as e:
            logger.warning(f"Order loop failed to start: {e}")

    app.run(host="0.0.0.0", port=PORT, debug=False)
