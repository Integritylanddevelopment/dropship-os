#!/usr/bin/env python3
"""Prometheus Engine — Minimal HTTP Health Server (Port 8766)"""
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except:
    pass

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import os

PORT = int(os.getenv('PROMETHEUS_ENGINE_PORT', 8766))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            response = {
                "status": "healthy",
                "service": "Prometheus Engine (video generation)",
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
    server = HTTPServer(('127.0.0.1', PORT), HealthHandler)
    print(f"Prometheus Engine listening on http://127.0.0.1:{PORT}/health")
    server.serve_forever()
