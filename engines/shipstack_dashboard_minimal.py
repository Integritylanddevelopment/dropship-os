#!/usr/bin/env python3
"""ShipStack Dashboard — Minimal HTTP Server (Port 8890)"""
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except:
    pass

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse
import os

PORT = int(os.getenv('DASHBOARD_PORT', 8890))

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/':
            # Serve minimal HTML dashboard
            html = """
<!DOCTYPE html>
<html>
<head>
    <title>ShipStack Dashboard</title>
    <meta charset="utf-8">
    <style>
        body { font-family: monospace; padding: 20px; background: #1a1a1a; color: #0f0; }
        .service { padding: 10px; margin: 10px 0; border: 1px solid #0f0; }
        .healthy { background: #001a00; }
        .unhealthy { background: #330000; }
    </style>
</head>
<body>
    <h1>ShipStack Services</h1>
    <div id="services"></div>
    <script>
        async function checkService(name, port) {
            try {
                const resp = await fetch(`http://127.0.0.1:${port}/health`, {timeout: 2000});
                const data = await resp.json();
                return {name, port, status: 'healthy', data};
            } catch (e) {
                return {name, port, status: 'unhealthy', error: e.message};
            }
        }

        async function updateDashboard() {
            const services = [
                {name: 'ShipStack Engine', port: 8889},
                {name: 'Prometheus Engine', port: 8766},
                {name: 'Social AI Agent', port: 8867},
            ];

            const results = await Promise.all(services.map(s => checkService(s.name, s.port)));
            const html = results.map(r => `
                <div class="service ${r.status}">
                    <strong>${r.name}</strong> (port ${r.port})<br>
                    Status: <strong>${r.status}</strong><br>
                    ${r.status === 'healthy' ? `Last check: ${new Date().toISOString()}` : `Error: ${r.error}`}
                </div>
            `).join('');

            document.getElementById('services').innerHTML = html;
        }

        updateDashboard();
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
            """
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode())

        elif path == '/health':
            response = {
                "status": "healthy",
                "service": "ShipStack Dashboard",
                "port": PORT,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', PORT), DashboardHandler)
    print(f"ShipStack Dashboard listening on http://127.0.0.1:{PORT}/")
    server.serve_forever()
