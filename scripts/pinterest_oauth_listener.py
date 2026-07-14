"""pinterest_oauth_listener.py - captures the Pinterest OAuth code on localhost:8085.
Writes the code to data/pinterest_oauth_code.txt then exits.
"""
import http.server
import pathlib
import urllib.parse

OUT = pathlib.Path(r"C:\Users\integ\Documents\Claude\Projects\ShipStack\data\pinterest_oauth_code.txt")
OUT.parent.mkdir(parents=True, exist_ok=True)
if OUT.exists():
    OUT.unlink()

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(q)
        code = (params.get("code") or [""])[0]
        if code:
            OUT.write_text(code, encoding="utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        msg = b"<h2>ShipStack: Pinterest authorization received. You can close this tab.</h2>"
        self.wfile.write(msg)
    def log_message(self, *a):
        pass

srv = http.server.HTTPServer(("127.0.0.1", 8085), H)
srv.handle_request()  # serve exactly one request, then exit