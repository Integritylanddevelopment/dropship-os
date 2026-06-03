"""
engine_ab_patch.py
Add these routes to shipstack_engine.py:
    from agents.engine_ab_patch import register_ab_routes
    register_ab_routes(app)
"""

def register_ab_routes(app):
    from agents.ab_testing import ABTestManager
    from agents.learning_engine import LearningEngine

    mgr = ABTestManager()
    le  = LearningEngine()

    @app.route("/api/engine/ab/dashboard", methods=["GET"])
    def ab_dashboard():
        from flask import jsonify, request
        slug = request.args.get("product_slug")
        return jsonify(mgr.get_dashboard_data(slug))

    @app.route("/api/engine/ab/tests", methods=["GET"])
    def ab_list_tests():
        from flask import jsonify, request
        slug     = request.args.get("product_slug")
        status   = request.args.get("status")
        platform = request.args.get("platform")
        return jsonify(mgr.list_tests(slug, status, platform))

    @app.route("/api/engine/ab/create", methods=["POST"])
    def ab_create():
        from flask import jsonify, request
        d = request.get_json()
        test = mgr.create_test(
            base_content  = d.get("content", ""),
            product_slug  = d.get("product_slug", "unknown"),
            platform      = d.get("platform", "tiktok"),
            content_type  = d.get("content_type", "tiktok_script"),
            niche         = d.get("niche", "default"),
            max_avatars   = int(d.get("max_avatars", 3)),
        )
        return jsonify(test.to_dict())

    @app.route("/api/engine/ab/create-from-approved", methods=["POST"])
    def ab_create_from_approved():
        from flask import jsonify, request
        from pathlib import Path
        d = request.get_json()
        slug = d.get("product_slug", "")
        path = str(Path(__file__).parent.parent / "data" / "product_collateral" / slug / "approved_content.json")
        tests = mgr.create_tests_for_approved_content(path, d.get("max_per_platform", 5), d.get("max_avatars", 3))
        return jsonify({"created": len(tests), "test_ids": [t.to_dict()["test_id"] for t in tests]})

    @app.route("/api/engine/ab/record", methods=["POST"])
    def ab_record():
        from flask import jsonify, request
        d = request.get_json()
        result = mgr.record_performance(
            test_id       = d.get("test_id"),
            variant_label = d.get("variant_label", "A"),
            impressions   = int(d.get("impressions", 0)),
            clicks        = int(d.get("clicks", 0)),
            saves         = int(d.get("saves", 0)),
            shares        = int(d.get("shares", 0)),
            comments      = int(d.get("comments", 0)),
            link_clicks   = int(d.get("link_clicks", 0)),
            conversions   = int(d.get("conversions", 0)),
            revenue       = float(d.get("revenue", 0.0)),
            traffic_source= d.get("traffic_source"),
        )
        return jsonify(result)

    @app.route("/api/engine/ab/check-winners", methods=["POST"])
    def ab_check_winners():
        from flask import jsonify
        winners = mgr.check_all_for_winners()
        return jsonify({"winners_found": len(winners), "winners": winners})

    @app.route("/api/engine/learning/status", methods=["GET"])
    def learning_status():
        from flask import jsonify
        return jsonify(le.get_status())

    @app.route("/api/engine/learning/report", methods=["GET"])
    def learning_report():
        from flask import jsonify
        return jsonify(le.generate_weekly_report())

    @app.route("/api/engine/learning/recommend", methods=["GET"])
    def learning_recommend():
        from flask import jsonify, request
        slug     = request.args.get("product_slug", "unknown")
        niche    = request.args.get("niche", "default")
        platform = request.args.get("platform", "tiktok")
        return jsonify(le.get_recommendations_for_product(slug, niche, platform))

    @app.route("/api/engine/learning/rebuild-formulas", methods=["POST"])
    def learning_rebuild():
        from flask import jsonify
        formulas = le.rebuild_winning_formulas()
        return jsonify({"formulas_generated": len(formulas), "formulas": formulas})

    print("[Engine] A/B + Learning routes registered ✓")
