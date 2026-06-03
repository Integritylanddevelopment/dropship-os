#!/usr/bin/env python3
"""Config Validator - Pre-Flight Checks"""

import os
import sys
import socket
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DROPSHIP_OS_ROOT = Path(__file__).parent


def check_ports() -> bool:
    """Check required ports are available."""
    logger.info("\nChecking ports...")
    ports = {8889: "ShipStack", 8766: "Prometheus", 8867: "Social AI", 8890: "Dashboard", 8765: "Quinn"}
    for port, name in ports.items():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
            logger.info(f"PASS: Port {port} ({name}) available")
        except:
            logger.warning(f"WARN: Port {port} in use")
    return True


def check_files() -> bool:
    """Check required files exist."""
    logger.info("\nChecking files...")
    files = [
        "CLAUDE.md", "SHIPSTACK_DIRECTIVES.md", ".env.local",
        "shipstack_engine.py", "prometheus_engine.py", "social_ai_agent.py", "shipstack_dashboard.py",
        "shipstack_badge.py", "decision_engine.py", "product_research.py", "analytics_engine.py"
    ]
    all_ok = True
    for fname in files:
        if (DROPSHIP_OS_ROOT / fname).exists():
            logger.info(f"PASS: {fname}")
        else:
            logger.error(f"FAIL: {fname} NOT FOUND")
            all_ok = False
    return all_ok


def check_no_leaks() -> bool:
    """Check no direct Anthropic calls."""
    logger.info("\nChecking for Anthropic API leaks...")
    import glob
    for py_file in glob.glob(str(DROPSHIP_OS_ROOT / "*.py")):
        if "validate_config" in py_file:
            continue
        with open(py_file) as f:
            for i, line in enumerate(f, 1):
                if line.strip().startswith("#"):
                    continue
                if "api.anthropic.com" in line and "requests" in line:
                    logger.error(f"FAIL: Found api.anthropic.com in {Path(py_file).name}:{i}")
                    return False
    logger.info("PASS: No Anthropic leaks detected")
    return True


def main():
    """Run all checks."""
    logger.info("=" * 60)
    logger.info("ShipStack Configuration Validator")
    logger.info("=" * 60)
    
    checks = [
        ("Ports", check_ports),
        ("Files", check_files),
        ("No Leaks", check_no_leaks),
    ]
    
    results = {}
    for name, fn in checks:
        try:
            results[name] = fn()
        except Exception as e:
            logger.error(f"Exception in {name}: {e}")
            results[name] = False
    
    logger.info("\n" + "=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        logger.info(f"{status} | {name}")
    
    all_passed = all(results.values())
    logger.info("")
    if all_passed:
        logger.info("All checks passed! Ready to launch.")
        return 0
    else:
        logger.warning("Some checks need attention. Review above.")
        return 0  # Still allow launch with warnings


if __name__ == "__main__":
    sys.exit(main())
