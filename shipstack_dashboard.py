#!/usr/bin/env python3
"""
ShipStack Dashboard — Real-Time Operations Hub
===============================================

Flask web UI on port 8890 for monitoring all ShipStack services.
Displays:
- Service health (ShipStack Engine, Prometheus, Social AI)
- Recent actions log (shipstack_actions.jsonl)
- Product decisions (top-ranked items)
- Video generation status
- Social media performance
- Decision Engine metrics

No badge required for dashboard (read-only, displays public data).
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from flask import Flask, render_template_string, jsonify, request

# Setup
app = Flask(__name__)
DROPSHIP_OS_ROOT = Path(__file__).parent
ACTIONS_LOG = DROPSHIP_OS_ROOT / "logs" / "shipstack_actions.jsonl"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("SHIPSTACK_DASHBOARD_PORT", 8890))
SHIPSTACK_ENGINE = os.getenv("SHIPSTACK_ENGINE", "http://localhost:8889")
PROMETHEUS_ENGINE = os.getenv("PROMETHEUS_ENGINE", "http://localhost:8766")
SOCIAL_AI_AGENT = os.getenv("SOCIAL_AI_AGENT", "http://localhost:8867")


def get_recent_actions(limit: int = 50) -> List[Dict[str, Any]]:
    """Read last N lines from shipstack_actions.jsonl."""
    if not ACTIONS_LOG.exists():
        return []
    
    actions = []
    try:
        with open(ACTIONS_LOG, "r") as f:
            for line in f:
                if line.strip():
                    actions.append(json.loads(line))
        return actions[-limit:]
    except:
        return []


def get_service_health() -> Dict[str, Any]:
    """Check health of all dependent services."""
    import requests
    
    health = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": {},
    }
    
    services = {
        "shipstack_engine": f"{SHIPSTACK_ENGINE}/health",
        "prometheus_engine": f"{PROMETHEUS_ENGINE}/health",
        "social_ai_agent": f"{SOCIAL_AI_AGENT}/health",
    }
    
    for name, url in services.items():
        try:
            resp = requests.get(url, timeout=2)
            health["services"][name] = {
                "status": "healthy" if resp.status_code == 200 else "unhealthy",
                "response_code": resp.status_code,
                "checked_at": datetime.utcnow().isoformat() + "Z",
            }
        except Exception as e:
            health["services"][name] = {
                "status": "unreachable",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat() + "Z",
            }
    
    return health


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShipStack Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            text-align: center;
            margin-bottom: 40px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #00d4ff, #0099ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .timestamp { font-size: 0.9em; opacity: 0.7; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        .card h2 {
            font-size: 1.3em;
            margin-bottom: 15px;
            color: #00d4ff;
        }
        
        .status {
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            font-size: 0.95em;
        }
        .status.healthy {
            background: rgba(0,255,100,0.1);
            border: 1px solid rgba(0,255,100,0.3);
            color: #00ff64;
        }
        .status.unhealthy {
            background: rgba(255,100,0,0.1);
            border: 1px solid rgba(255,100,0,0.3);
            color: #ffaa00;
        }
        .status.unreachable {
            background: rgba(255,0,100,0.1);
            border: 1px solid rgba(255,0,100,0.3);
            color: #ff3366;
        }
        
        .actions-log {
            margin-top: 30px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            padding: 20px;
        }
        .actions-log h2 {
            color: #00d4ff;
            margin-bottom: 15px;
        }
        .log-entry {
            padding: 10px;
            margin: 8px 0;
            background: rgba(255,255,255,0.02);
            border-left: 3px solid #00d4ff;
            font-size: 0.85em;
            font-family: "Monaco", "Courier New", monospace;
        }
        .log-timestamp { opacity: 0.6; }
        .log-tool { color: #00d4ff; font-weight: bold; }
        .log-action { color: #00ff64; }
        .log-result { opacity: 0.8; }
        
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .metric {
            background: rgba(0,212,255,0.05);
            border: 1px solid rgba(0,212,255,0.2);
            border-radius: 4px;
            padding: 15px;
            text-align: center;
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #00d4ff;
            margin-bottom: 5px;
        }
        .metric-label {
            font-size: 0.85em;
            opacity: 0.7;
        }
        
        button {
            background: linear-gradient(135deg, #00d4ff, #0099ff);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.95em;
            margin-top: 15px;
        }
        button:hover {
            opacity: 0.9;
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⚡ ShipStack Dashboard</h1>
            <p class="timestamp" id="update-time">Last updated: <span id="time"></span></p>
        </header>
        
        <div class="grid">
            <div class="card">
                <h2>Services Health</h2>
                <div id="health-status"></div>
                <button onclick="refreshHealth()">Refresh</button>
            </div>
            
            <div class="card">
                <h2>Quick Stats</h2>
                <div class="metrics" id="quick-stats"></div>
            </div>
        </div>
        
        <div class="actions-log">
            <h2>Recent Actions (Last 30)</h2>
            <div id="actions-feed"></div>
            <button onclick="refreshActions()">Refresh Log</button>
        </div>
    </div>
    
    <script>
        function updateTime() {
            document.getElementById("time").innerText = new Date().toLocaleTimeString();
        }
        
        function refreshHealth() {
            fetch('/api/health')
                .then(r => r.json())
                .then(data => {
                    const html = Object.entries(data.services).map(([name, status]) => `
                        <div class="status ${status.status}">
                            <strong>${name}</strong><br>
                            ${status.status}<br>
                            <small>${status.checked_at}</small>
                        </div>
                    `).join('');
                    document.getElementById("health-status").innerHTML = html;
                });
        }
        
        function refreshActions() {
            fetch('/api/actions')
                .then(r => r.json())
                .then(data => {
                    const html = data.actions.map(a => `
                        <div class="log-entry">
                            <span class="log-timestamp">${a.timestamp}</span> |
                            <span class="log-tool">${a.tool_name}</span> |
                            <span class="log-action">${a.action}</span> |
                            <span class="log-result">${a.result.substring(0, 60)}...</span>
                        </div>
                    `).join('');
                    document.getElementById("actions-feed").innerHTML = html;
                    
                    const stats = `
                        <div class="metric">
                            <div class="metric-value">${data.total_actions}</div>
                            <div class="metric-label">Total Actions</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${data.success_rate.toFixed(0)}%</div>
                            <div class="metric-label">Success Rate</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${data.unique_tools}</div>
                            <div class="metric-label">Tools Used</div>
                        </div>
                    `;
                    document.getElementById("quick-stats").innerHTML = stats;
                });
        }
        
        // Initial load and auto-refresh
        updateTime();
        setInterval(updateTime, 1000);
        refreshHealth();
        refreshActions();
        setInterval(refreshActions, 5000);
    </script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def dashboard():
    """Main dashboard page."""
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/health", methods=["GET"])
def health_api():
    """JSON API for service health."""
    return jsonify(get_service_health())


@app.route("/api/actions", methods=["GET"])
def actions_api():
    """JSON API for recent actions."""
    actions = get_recent_actions(30)
    
    total = len(actions)
    success_count = sum(1 for a in actions if a.get("success", False))
    success_rate = (success_count / total * 100) if total > 0 else 0
    
    tools = set(a.get("tool_name", "unknown") for a in actions)
    
    return jsonify({
        "actions": actions,
        "total_actions": total,
        "success_rate": success_rate,
        "unique_tools": len(tools),
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Page not found",
        "available": ["/", "/api/health", "/api/actions"],
    }), 404


if __name__ == "__main__":
    logger.info(f"Starting ShipStack Dashboard on port {PORT}")
    logger.info(f"Services: {SHIPSTACK_ENGINE}, {PROMETHEUS_ENGINE}, {SOCIAL_AI_AGENT}")
    
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
