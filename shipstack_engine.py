#!/usr/bin/env python3
"""
ShipStack Engine — HTTP Service on Port 8889
==============================================

Primary service for ShipStack AI. Routes all AI/LLM calls through Quinn bridge (:8765).
Every HTTP endpoint is badge-gated (requires valid token from shipstack_badge.get_badge()).

Serves:
- Decision Engine API (/api/decide)
- Product research API (/api/research)
- Health check (/health)
- Action logging (/api/log-action)
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from flask import Flask, request, jsonify
from shipstack_badge import get_badge, validate_token, log_action

# Setup
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

PORT = int(os.getenv("SHIPSTACK_ENGINE_PORT", 8889))
QUINN_ENDPOINT = os.getenv("QUINN_ENDPOINT", "http://localhost:8765")
QUINN_BRIDGE_SECRET = os.getenv("QUINN_BRIDGE_SECRET", "")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def require_badge(f):
    """
    Decorator for badge-gated endpoints.
    Checks Authorization header for valid badge token.
    """
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "error": "Missing or invalid Authorization header",
                "expected": "Authorization: Bearer badge-1_...",
            }), 401
        
        token = auth_header[7:]  # Remove "Bearer "
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        if not validate_token(token, issued_at):
            return jsonify({
                "error": "Badge token expired or invalid",
                "hint": "Tokens are valid for 60 seconds only. Get a new badge.",
            }), 401
        
        # Token is valid, proceed
        return f(*args, **kwargs)
    
    wrapper.__name__ = f.__name__
    return wrapper


@app.route("/health", methods=["GET"])
def health_check():
    """
    Public health check (no badge required).
    Returns: { "status": "healthy", "port": 8889, "timestamp": "..." }
    """
    return jsonify({
        "status": "healthy",
        "service": "ShipStack Engine",
        "port": PORT,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "quinn_bridge": QUINN_ENDPOINT,
    }), 200


@app.route("/badge", methods=["GET"])
def get_new_badge():
    """
    Public endpoint to get a new badge token.
    No token required (bootstrapping).
    
    Returns: { "token": "badge-1_...", "issued_at": "...", "expires_at": "...", ... }
    """
    badge = get_badge()
    logger.info(f"Issued badge token: {badge['token'][:20]}... (expires {badge['expires_at']})")
    return jsonify(badge), 200


@app.route("/api/decide", methods=["POST"])
@require_badge
def decide():
    """
    Decision Engine — Score and rank products.
    
    Badge-gated endpoint.
    
    Request body:
    {
        "products": [
            {
                "id": "product-123",
                "title": "Widget",
                "price": 15.99,
                "niche": "home kitchen",
            },
            ...
        ],
        "context": {
            "budget_per_unit": 8.00,
            "target_margin": 0.50,
            "target_niche": "home kitchen",
        }
    }
    
    Response:
    {
        "rankings": [
            {
                "product_id": "product-123",
                "score": 0.87,
                "reasoning": "...",
            },
            ...
        ],
        "top_pick": "product-123",
    }
    """
    try:
        data = request.get_json()
        products = data.get("products", [])
        context = data.get("context", {})
        
        token = request.headers.get("Authorization", "Bearer ")[7:]
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        # TODO: Call Quinn bridge for scoring
        # For now, return placeholder
        
        rankings = []
        for product in products:
            rankings.append({
                "product_id": product.get("id"),
                "score": 0.75,  # placeholder
                "reasoning": "Awaiting Decision Engine implementation",
            })
        
        result = {
            "rankings": rankings,
            "top_pick": rankings[0]["product_id"] if rankings else None,
        }
        
        # Log the action
        log_action(
            token=token,
            issued_at_iso=issued_at,
            tool_name="shipstack_engine_decide",
            target="/api/decide",
            action="decide",
            result=f"Scored {len(products)} products",
            success=True,
        )
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error in /api/decide: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/research", methods=["POST"])
@require_badge
def research():
    """
    Product Research — Fetch supplier data, pricing, reviews.
    
    Badge-gated endpoint.
    
    Request body:
    {
        "search_term": "pet collars",
        "supplier": "zendrop|autods|aliexpress",
        "limit": 20,
    }
    
    Response:
    {
        "products": [
            {
                "id": "...",
                "title": "...",
                "price": 4.50,
                "supplier": "zendrop",
                "reviews": 152,
                "rating": 4.7,
            },
            ...
        ],
    }
    """
    try:
        data = request.get_json()
        search_term = data.get("search_term", "")
        supplier = data.get("supplier", "zendrop")
        limit = data.get("limit", 20)
        
        token = request.headers.get("Authorization", "Bearer ")[7:]
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        # TODO: Call supplier APIs via Quinn bridge
        # For now, return placeholder
        
        result = {
            "search_term": search_term,
            "supplier": supplier,
            "products": [],  # placeholder
            "count": 0,
        }
        
        # Log the action
        log_action(
            token=token,
            issued_at_iso=issued_at,
            tool_name="shipstack_engine_research",
            target="/api/research",
            action="research",
            result=f"Researched '{search_term}' on {supplier}",
            success=True,
        )
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error in /api/research: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/log-action", methods=["POST"])
@require_badge
def log_action_endpoint():
    """
    Log a tool call action.
    
    Badge-gated endpoint.
    
    Request body:
    {
        "tool_name": "quinn_write_file",
        "target": "/path/to/file.py",
        "action": "write",
        "result": "Successfully created file",
        "success": true,
    }
    
    Response:
    {
        "logged": true,
        "line_number": 42,
        "timestamp": "2026-06-03T12:00:15Z",
    }
    """
    try:
        data = request.get_json()
        tool_name = data.get("tool_name", "unknown")
        target = data.get("target", "unknown")
        action = data.get("action", "unknown")
        result = data.get("result", "")
        success = data.get("success", True)
        
        token = request.headers.get("Authorization", "Bearer ")[7:]
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        log_result = log_action(
            token=token,
            issued_at_iso=issued_at,
            tool_name=tool_name,
            target=target,
            action=action,
            result=result,
            success=success,
        )
        
        return jsonify(log_result), 200 if log_result.get("logged") else 400
    except Exception as e:
        logger.error(f"Error in /api/log-action: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "hint": "Available: /health, /badge, /api/decide, /api/research, /api/log-action",
    }), 404


if __name__ == "__main__":
    logger.info(f"Starting ShipStack Engine on port {PORT}")
    logger.info(f"Quinn bridge: {QUINN_ENDPOINT}")
    logger.info("Routes: /health (public), /badge (public), /api/decide, /api/research, /api/log-action (badge-gated)")
    
    # Minimize PowerShell window on launch
    try:
        import subprocess
        subprocess.Popen([
            "powershell.exe",
            "-NoProfile",
            "-Command",
            """
            $h = (Get-Process -Id $PID).MainWindowHandle
            if ($h -ne 0) {
                Add-Type -Name W -Namespace P -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(int h, int s);' -ErrorAction SilentlyContinue
                [P.W]::ShowWindow($h, 6) | Out-Null
            }
            """
        ])
    except:
        pass
    
    app.run(host="127.0.0.1", port=PORT, debug=False)
