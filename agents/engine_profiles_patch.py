"""
engine_profiles_patch.py
Paste these routes into shipstack_engine.py — or import this module and
call register_profile_routes(app) from within your Flask app setup.

Usage in shipstack_engine.py:
    from agents.engine_profiles_patch import register_profile_routes
    register_profile_routes(app)
"""

import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def register_profile_routes(app):
    from agents.profile_manager import ProfileManager
    from agents.content_spinner import ContentSpinner

    pm = ProfileManager()

    # ── GET /api/engine/profiles ──────────────────────────────────────────────
    @app.route("/api/engine/profiles", methods=["GET"])
    def get_profiles():
        from flask import jsonify
        stats = pm.get_stats()
        return jsonify(stats)

    # ── POST /api/engine/profiles/add ─────────────────────────────────────────
    @app.route("/api/engine/profiles/add", methods=["POST"])
    def add_profile():
        from flask import jsonify, request
        data = request.get_json()
        result = pm.add_profile(
            platform=data.get("platform"),
            username=data.get("username"),
            niche=data.get("niche", "default"),
            proxy=data.get("proxy"),
            notes=data.get("notes", ""),
        )
        return jsonify(result)

    # ── POST /api/engine/profiles/<id>/assign-calendar ───────────────────────
    @app.route("/api/engine/profiles/<profile_id>/assign-calendar", methods=["POST"])
    def assign_calendar(profile_id):
        from flask import jsonify, request
        data = request.get_json()
        result = pm.assign_calendar(profile_id, data.get("calendar_path", ""))
        return jsonify(result)

    # ── POST /api/engine/profiles/<id>/status ─────────────────────────────────
    @app.route("/api/engine/profiles/<profile_id>/status", methods=["POST"])
    def set_profile_status(profile_id):
        from flask import jsonify, request
        data = request.get_json()
        result = pm.set_status(profile_id, data.get("status"))
        return jsonify(result)

    # ── GET /api/engine/profiles/<id>/stats ──────────────────────────────────
    @app.route("/api/engine/profiles/<profile_id>/stats", methods=["GET"])
    def profile_stats(profile_id):
        from flask import jsonify
        profile = pm.get_profile(profile_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
        return jsonify(profile)

    # ── POST /api/engine/content/spin ─────────────────────────────────────────
    @app.route("/api/engine/content/spin", methods=["POST"])
    def spin_content():
        from flask import jsonify, request
        data = request.get_json()
        slug = data.get("product_slug", "")
        profile_count = int(data.get("profile_count", 1))

        # Load Quinn output for this product
        quinn_path = BASE_DIR / "data" / "product_collateral" / slug / "quinn_output.json"
        if not quinn_path.exists():
            return jsonify({"error": f"Quinn output not found for slug: {slug}"}), 404

        quinn_output = json.loads(quinn_path.read_text())
        product_name = quinn_output.get("product_name", slug)
        niche = quinn_output.get("niche", "default")

        spinner = ContentSpinner()
        results = spinner.spin_product(quinn_output, product_name, niche, profile_count)
        out_path = spinner.save(results)

        return jsonify({
            "status": "done",
            "product": product_name,
            "output_file": out_path,
            "totals": results["totals"],
        })

    # ── POST /api/engine/profiles/<id>/distribute ─────────────────────────────
    @app.route("/api/engine/profiles/<profile_id>/distribute", methods=["POST"])
    def distribute_calendar(profile_id):
        from flask import jsonify, request
        data = request.get_json()
        slug = data.get("product_slug", "")
        platform = data.get("platform", "tiktok")
        calendar_path = str(BASE_DIR / "data" / "product_collateral" / slug / "content_calendar.json")

        result = pm.distribute_calendar(
            calendar_path=calendar_path,
            platform=platform,
            profiles_limit=int(data.get("profiles_limit", 10)),
        )
        return jsonify(result)

    print("[Engine] Profile routes registered ✓")
