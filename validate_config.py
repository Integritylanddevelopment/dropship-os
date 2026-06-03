#!/usr/bin/env python3
"""
Config Validator — Pre-Flight Checks
=====================================

Validates ShipStack configuration before launch.
Checks:
- Required env vars present
- No ANTHROPIC_API_KEY in ShipStack (.env.local OK if empty)
- Ports not in use
- Required files exist
- Database writeable
- Log directory writeable
"""

import os
import sys
import socket
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DROPSHIP_OS_ROOT = Path(__file__).parent


def check_port_available(port: int) -> bool:
    """Check if port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def check_file_exists(path: Path, name: str) -> bool:
    """Check if file exists."""
    if path.exists():
        logger.info(f"✓ {name}: {path}")
        return True
    else:
        logger.error(f"✗ {name} NOT FOUND: {path}")
        return False


def check_directory_writeable(path: Path, name: str) -> bool:
    """Check if directory is writeable."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        test_file = path / ".writetest"
        test_file.write_text("test")
        test_file.unlink()
        logger.info(f"✓ {name} writeable: {path}")
        return True
    except Exception as e:
        logger.error(f"✗ {name} NOT writeable: {e}")
        return False


def check_env_vars() -> bool:
    """Check required env vars."""
    required = {
        "QUINN_ENDPOINT": "Quinn bridge URL",
        "QUINN_BRIDGE_SECRET": "Quinn auth secret",
    }
    
    optional = {
        "ZENDROP_API_KEY": "Zendrop API key",
        "AUTODS_API_KEY": "AutoDS API key",
        "TIKTOK_ACCESS_TOKEN": "TikTok auth",
        "META_ACCESS_TOKEN": "Instagram auth",
        "PINTEREST_ACCESS_TOKEN": "Pinterest auth",
        "YOUTUBE_REFRESH_TOKEN": "YouTube auth",
        "STRIPE_SECRET_KEY": "Stripe payment key",
    }
    
    all_ok = True
    
    logger.info("\nRequired env vars:")
    for key, desc in required.items():
        if key in os.environ and os.environ[key]:
            logger.info(f"✓ {key}")
        else:
            logger.error(f"✗ {key} MISSING")
            all_ok = False
    
    logger.info("\nOptional env vars:")
    for key, desc in optional.items():
        if key in os.environ and os.environ[key]:
            logger.info(f"✓ {key}")
        else:
            logger.warning(f"⊘ {key} (optional, will skip)")
    
    return all_ok


def check_no_anthropic_leak() -> bool:
    """Verify no ANTHROPIC_API_KEY in ShipStack code."""
    logger.info("\nChecking for Anthropic API key leaks...")
    
    # Check .env.local
    env_path = DROPSHIP_OS_ROOT / ".env.local"
    if env_path.exists():
        content = env_path.read_text()
        if "ANTHROPIC_API_KEY" in content and "PLACEHOLDER" not in content:
            logger.error(f"✗ ANTHROPIC_API_KEY found in .env.local (should be removed)")
            return False
    
    # Check Python files
    import glob
    python_files = glob.glob(str(DROPSHIP_OS_ROOT / "*.py"))
    
    for py_file in python_files:
        with open(py_file, "r") as f:
            content = f.read()
            if "api.anthropic.com" in content:
                logger.error(f"✗ Direct Anthropic API call found in {Path(py_file).name}")
                return False
    
    logger.info("✓ No Anthropic API leaks detected")
    return True


def check_ports() -> bool:
    """Check required ports are available."""
    logger.info("\nChecking ports...")
    
    ports = {
        8889: "ShipStack Engine",
        8766: "Prometheus Engine",
        8867: "Social AI Agent",
        8890: "ShipStack Dashboard",
        8765: "Quinn Bridge (external)",
    }
    
    all_ok = True
    for port, name in ports.items():
        if check_port_available(port):
            logger.info(f"✓ Port {port} ({name}) available")
        else:
            if port == 8765:
                logger.error(f"✗ Port {port} ({name}) IN USE — Quinn Bridge not running?")
                all_ok = False
            else:
                logger.warning(f"⊘ Port {port} ({name}) in use")
    
    return all_ok


def check_files() -> bool:
    """Check required files exist."""
    logger.info("\nChecking files...")
    
    files = {
        DROPSHIP_OS_ROOT / "CLAUDE.md": "Foundation doc",
        DROPSHIP_OS_ROOT / "SHIPSTACK_DIRECTIVES.md": "Directives",
        DROPSHIP_OS_ROOT / ".env.local": "Config",
        DROPSHIP_OS_ROOT / "shipstack_engine.py": "ShipStack Engine",
        DROPSHIP_OS_ROOT / "prometheus_engine.py": "Prometheus Engine",
        DROPSHIP_OS_ROOT / "social_ai_agent.py": "Social AI Agent",
        DROPSHIP_OS_ROOT / "shipstack_dashboard.py": "Dashboard",
        DROPSHIP_OS_ROOT / "shipstack_badge.py": "Badge system",
        DROPSHIP_OS_ROOT / "decision_engine.py": "Decision Engine",
        DROPSHIP_OS_ROOT / "product_research.py": "Product Research",
        DROPSHIP_OS_ROOT / "analytics_engine.py": "Analytics Engine",
    }
    
    all_ok = True
    for path, name in files.items():
        if not check_file_exists(path, name):
            all_ok = False
    
    return all_ok


def check_directories() -> bool:
    """Check directories are writeable."""
    logger.info("\nChecking directories...")
    
    dirs = {
        DROPSHIP_OS_ROOT / "logs": "Logs",
        DROPSHIP_OS_ROOT / "data": "Data",
    }
    
    all_ok = True
    for path, name in dirs.items():
        if not check_directory_writeable(path, name):
            all_ok = False
    
    return all_ok


def main():
    """Run all checks."""
    logger.info("=" * 60)
    logger.info("ShipStack Configuration Validator")
    logger.info("=" * 60)
    
    checks = [
        ("Env Vars", check_env_vars),
        ("No Anthropic Leaks", check_no_anthropic_leak),
        ("Ports", check_ports),
        ("Files", check_files),
        ("Directories", check_directories),
    ]
    
    results = {}
    for name, check_fn in checks:
        try:
            results[name] = check_fn()
        except Exception as e:
            logger.error(f"Exception in {name}: {e}")
            results[name] = False
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status} | {name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n✓ All checks passed! Ready to launch.")
        return 0
    else:
        logger.error("\n✗ Some checks failed. Fix issues before launching.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
