#!/usr/bin/env python3
"""
Launch ShipStack — Kill & Start All Services
==============================================

Implements Directive #5: Kill Before Launch

Starts:
1. ShipStack Engine (:8889)
2. Prometheus Engine (:8766)
3. Social AI Agent (:8867)
4. ShipStack Dashboard (:8890)

Kills any existing processes on those ports before launching.
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

SHIPSTACK_ROOT = Path(__file__).parent.parent
SERVICES = {
    "engines/shipstack_engine.py": 8889,
    "engines/prometheus_engine.py": 8766,
    "agents/social_ai_agent.py": 8867,
    "engines/shipstack_dashboard.py": 8890,
}


def kill_port(port: int) -> bool:
    """Kill process listening on port (Windows)."""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             f"$p = Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue; if ($p) {{ Stop-Process -Id $p.OwningProcess -Force -Confirm:$false }}"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            logger.info(f"✓ Killed process on port {port}")
            return True
    except Exception as e:
        logger.warning(f"Failed to kill port {port}: {e}")
    return False


def start_service(script_name: str, port: int) -> subprocess.Popen:
    """Start a Python service."""
    script_path = SHIPSTACK_ROOT / script_name

    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return None

    try:
        # Minimize window + start process
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 6  # SW_MINIMIZE

        proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(SHIPSTACK_ROOT),
            startupinfo=startupinfo,
            env={**os.environ, "SHIPSTACK_ENGINE_PORT": "8889", "PROMETHEUS_ENGINE_PORT": "8766", "SOCIAL_AI_AGENT_PORT": "8867", "SHIPSTACK_DASHBOARD_PORT": "8890"},
        )
        logger.info(f"✓ Started {script_name} (PID {proc.pid}) on port {port}")
        return proc
    except Exception as e:
        logger.error(f"Failed to start {script_name}: {e}")
        return None


def main():
    """Kill all, then start all services."""
    logger.info("=" * 60)
    logger.info("ShipStack Launcher — Kill & Start All")
    logger.info("=" * 60)
    
    # Phase 1: Kill old processes
    logger.info("\nPhase 1: Killing old processes...")
    for script, port in SERVICES.items():
        kill_port(port)
    
    time.sleep(2)  # Wait for ports to be released
    
    # Phase 2: Start new processes
    logger.info("\nPhase 2: Starting services...")
    processes = {}
    for script, port in SERVICES.items():
        proc = start_service(script, port)
        if proc:
            processes[script] = proc
        time.sleep(1)  # Stagger startup
    
    logger.info("\n" + "=" * 60)
    logger.info(f"All services started ({len(processes)}/{len(SERVICES)})")
    logger.info("=" * 60)
    logger.info("\nService URLs:")
    logger.info("  ShipStack Engine:     http://localhost:8889")
    logger.info("  Prometheus Engine:    http://localhost:8766")
    logger.info("  Social AI Agent:      http://localhost:8867")
    logger.info("  Dashboard:            http://localhost:8890")
    logger.info("\nPress Ctrl+C to stop all services...")
    
    # Keep running until interrupted
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        for script, proc in processes.items():
            try:
                proc.terminate()
                proc.wait(timeout=5)
                logger.info(f"✓ Stopped {script}")
            except:
                proc.kill()
                logger.warning(f"Force-killed {script}")


if __name__ == "__main__":
    main()
