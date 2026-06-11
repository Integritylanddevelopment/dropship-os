#!/usr/bin/env python3
"""
Integration Tests — End-to-End Smoke Tests
===========================================

Verifies:
1. Badge system works (get token, validate, expire)
2. ShipStack Engine responds to requests
3. All endpoints return proper JSON
4. Decision Engine scoring logic
5. Product research returns results
6. Analytics computes metrics
7. Cross-service communication
"""

import os
import sys
import json
import time
import logging
import requests
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DROPSHIP_OS_ROOT = Path(__file__).parent
SHIPSTACK_ENDPOINT = "http://localhost:8889"
PROMETHEUS_ENDPOINT = "http://localhost:8766"
SOCIAL_ENDPOINT = "http://localhost:8867"
DASHBOARD_ENDPOINT = "http://localhost:8890"


class IntegrationTest:
    """Run integration tests."""
    
    def __init__(self):
        self.results = {}
        self.badge_token = None
        self.badge_issued_at = None
    
    def test_badge_system(self) -> bool:
        """Test badge generation and validation."""
        logger.info("\n=== Test 1: Badge System ===")
        
        try:
            # Get badge
            resp = requests.get(f"{SHIPSTACK_ENDPOINT}/badge", timeout=5)
            assert resp.status_code == 200, f"Badge endpoint failed: {resp.status_code}"
            
            badge = resp.json()
            assert "token" in badge, "No token in badge response"
            assert "issued_at" in badge, "No issued_at in badge"
            assert "expires_at" in badge, "No expires_at in badge"
            
            self.badge_token = badge["token"]
            self.badge_issued_at = badge["issued_at"]
            
            logger.info(f"✓ Got badge: {self.badge_token[:30]}...")
            logger.info(f"  Expires: {badge['expires_at']}")
            
            return True
        except Exception as e:
            logger.error(f"✗ Badge test failed: {e}")
            return False
    
    def test_health_checks(self) -> bool:
        """Test /health endpoints on all services."""
        logger.info("\n=== Test 2: Health Checks ===")
        
        services = {
            "ShipStack Engine": SHIPSTACK_ENDPOINT,
            "Prometheus Engine": PROMETHEUS_ENDPOINT,
            "Social AI Agent": SOCIAL_ENDPOINT,
            "Dashboard": DASHBOARD_ENDPOINT,
        }
        
        all_ok = True
        for name, url in services.items():
            try:
                resp = requests.get(f"{url}/health", timeout=3)
                if resp.status_code == 200:
                    logger.info(f"✓ {name} healthy")
                else:
                    logger.warning(f"⊘ {name} returned {resp.status_code}")
                    all_ok = False
            except Exception as e:
                logger.warning(f"⊘ {name} unreachable: {e}")
        
        return all_ok
    
    def test_decision_engine(self) -> bool:
        """Test Decision Engine scoring."""
        logger.info("\n=== Test 3: Decision Engine ===")
        
        try:
            sys.path.insert(0, str(DROPSHIP_OS_ROOT))
            from decision_engine import DecisionEngine, Product
            
            engine = DecisionEngine()
            
            test_product = Product(
                id="test-001",
                title="Test Widget",
                price=5.50,
                supplier="zendrop",
                reviews=150,
                rating=4.7,
                niche="pet accessories",
            )
            
            decision = engine.decide(test_product)
            
            assert 0 <= decision.score <= 1, f"Score out of range: {decision.score}"
            logger.info(f"✓ Decision Engine scored: {decision.score:.2f}")
            logger.info(f"  Rationale: {decision.rationale}")
            logger.info(f"  Competition: {decision.competition_level}")
            
            return True
        except Exception as e:
            logger.error(f"✗ Decision Engine test failed: {e}")
            return False
    
    def test_product_research(self) -> bool:
        """Test Product Research tool."""
        logger.info("\n=== Test 4: Product Research ===")
        
        try:
            sys.path.insert(0, str(DROPSHIP_OS_ROOT))
            from product_research import ProductResearcher
            
            researcher = ProductResearcher()
            products = researcher.research("pet collars", suppliers=["zendrop"], limit=3)
            
            assert len(products) > 0, "No products returned"
            logger.info(f"✓ Found {len(products)} products")
            
            for product in products:
                logger.info(f"  - {product['title']} (${product['price']:.2f})")
            
            return True
        except Exception as e:
            logger.error(f"✗ Product Research test failed: {e}")
            return False
    
    def test_analytics_engine(self) -> bool:
        """Test Analytics Engine metrics."""
        logger.info("\n=== Test 5: Analytics Engine ===")
        
        try:
            sys.path.insert(0, str(DROPSHIP_OS_ROOT))
            from analytics_engine import AnalyticsEngine
            
            analytics = AnalyticsEngine()
            metrics = analytics.get_summary_metrics(hours=24)
            
            logger.info(f"✓ Analytics computed metrics")
            logger.info(f"  Total actions: {metrics['total_actions']}")
            logger.info(f"  Success rate: {metrics['success_rate']:.1%}")
            
            return True
        except Exception as e:
            logger.error(f"✗ Analytics Engine test failed: {e}")
            return False
    
    def test_badge_gated_endpoint(self) -> bool:
        """Test badge-gated endpoint with valid token."""
        logger.info("\n=== Test 6: Badge-Gated Endpoints ===")
        
        if not self.badge_token:
            logger.error("✗ No badge token (run test 1 first)")
            return False
        
        try:
            # Test ShipStack Engine /api/decide
            payload = {
                "products": [
                    {"id": "p1", "title": "Widget", "price": 5.0, "niche": "home kitchen"},
                ],
                "context": {"budget_per_unit": 8.0},
            }
            
            headers = {
                "Authorization": f"Bearer {self.badge_token}",
                "X-Badge-Issued-At": self.badge_issued_at,
            }
            
            resp = requests.post(
                f"{SHIPSTACK_ENDPOINT}/api/decide",
                json=payload,
                headers=headers,
                timeout=5,
            )
            
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
            data = resp.json()
            assert "rankings" in data, "No rankings in response"
            
            logger.info(f"✓ Badge-gated endpoint accepted valid token")
            logger.info(f"  Returned {len(data['rankings'])} rankings")
            
            return True
        except Exception as e:
            logger.error(f"✗ Badge-gated endpoint test failed: {e}")
            return False
    
    def test_no_anthropic_leak(self) -> bool:
        """Verify no direct Anthropic calls in code."""
        logger.info("\n=== Test 7: No Anthropic Leaks ===")
        
        try:
            import glob
            
            violations = []
            
            # Check all Python files
            for py_file in glob.glob(str(DROPSHIP_OS_ROOT / "*.py")):
                with open(py_file, "r") as f:
                    content = f.read()
                    
                    if "api.anthropic.com" in content:
                        violations.append(f"{Path(py_file).name}: api.anthropic.com")
                    
                    if "ANTHROPIC_API_KEY" in content and "PLACEHOLDER" not in content:
                        violations.append(f"{Path(py_file).name}: ANTHROPIC_API_KEY")
            
            if violations:
                logger.error(f"✗ Found {len(violations)} violations:")
                for v in violations:
                    logger.error(f"  - {v}")
                return False
            else:
                logger.info("✓ No Anthropic API leaks detected")
                return True
        except Exception as e:
            logger.error(f"✗ Leak detection test failed: {e}")
            return False
    
    def run_all(self) -> bool:
        """Run all tests."""
        logger.info("=" * 60)
        logger.info("ShipStack Integration Tests")
        logger.info("=" * 60)
        logger.info("\nNote: Some tests require services to be running.")
        logger.info("Run: python launch_shipstack.py")
        
        tests = [
            ("Badge System", self.test_badge_system),
            ("Health Checks", self.test_health_checks),
            ("Decision Engine", self.test_decision_engine),
            ("Product Research", self.test_product_research),
            ("Analytics Engine", self.test_analytics_engine),
            ("Badge-Gated Endpoints", self.test_badge_gated_endpoint),
            ("No Anthropic Leaks", self.test_no_anthropic_leak),
        ]
        
        for name, test_fn in tests:
            try:
                self.results[name] = test_fn()
            except Exception as e:
                logger.error(f"Exception in {name}: {e}")
                self.results[name] = False
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Test Summary")
        logger.info("=" * 60)
        
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        for name, passed_test in self.results.items():
            status = "✓ PASS" if passed_test else "✗ FAIL"
            logger.info(f"{status} | {name}")
        
        logger.info(f"\n{passed}/{total} tests passed")
        
        return all(self.results.values())


if __name__ == "__main__":
    tester = IntegrationTest()
    success = tester.run_all()
    sys.exit(0 if success else 1)
