"""google_oauth_listener.py - captures Google OAuth code on localhost:8090."""
import http.server, pathlib, urllib.parse
OUT = pathlib.Path(r"C:\Users\integ\Documents\Claude\Projects\ShipStack\data\google_oauth_code.txt")
OUT.parent.mkdir(parents=True, exist_ok=True)
if OUT.exists():
    OUT.unlink()
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = (params.get("code") or [""])[0]
        if code:
            OUT.write_text(code, encoding="utf-8")
        self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
        self.wfile.write(b"<h2>ShipStack: Google authorization received. You can close this tab.</h2>")
    def log_message(self, *a):
        pass
http.server.HTTPServer(("127.0.0.1", 8090), H).handle_request()