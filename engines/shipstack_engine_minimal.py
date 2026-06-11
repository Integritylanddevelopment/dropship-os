#!/usr/bin/env python3
"""
ShipStack Engine — Minimal HTTP Health Server
Temporary test service to verify port is working.
"""

import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except:
    pass

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import os

PORT = int(os.getenv('SHIPSTACK_ENGINE_PORT', 8889))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            response = {
                "status": "healthy",
                "service": "ShipStack Engine (minimal test)",
                "port": PORT,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
            print(f"[{datetime.now().isoformat()}] GET /health - 200 OK")
        else:
            self.send_response(404)
            self.end_headers()
            print(f"[{datetime.now().isoformat()}] GET {self.path} - 404 Not Found")

    def log_message(self, format, *args):
        # Suppress default logging
        pass

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', PORT), HealthHandler)
    print(f"ShipStack Engine (minimal) listening on http://127.0.0.1:{PORT}/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown")
        server.shutdown()
