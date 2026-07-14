"""ShipStack Dashboard :8890 - full operations UI (rewritten 2026-07-13).
Server-side aggregates health + pipeline + revenue so the browser needs no CORS.
"""
import json
import os
import time
import urllib.request
from pathlib import Path

from flask import Flask, jsonify

app = Flask(__name__)
PORT = int(os.environ.get("SHIPSTACK_DASHBOARD_PORT", 8890))  # NOT DASHBOARD_PORT (=8888, Quinn dashboard)
RUNS_DIR = Path("/app/discovery_engine/runs")

SERVICES = [
    ("ShipStack Engine", "http://shipstack-engine:8889/health"),
    ("Prometheus Engine", "http://prometheus-engine:8766/health"),
    ("Social AI Agent", "http://social-ai-agent:8867/health"),
    ("Pipeline Dashboard", "http://pipeline-dashboard:8891/"),
    ("Quinn Bridge", "http://host.docker.internal:8765/health"),
]

def _fetch_json(url, timeout=4):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "dashboard"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
        try:
            return True, json.loads(body)
        except Exception:
            return True, {"status_code": r.status}
    except Exception as e:
        return False, {"error": str(e)}

def _latest_run():
    try:
        files = sorted(RUNS_DIR.glob("run_*.json"), reverse=True)
        if not files:
            return None
        d = json.loads(files[0].read_text(encoding="utf-8", errors="replace"))
        return {"file": files[0].name, "data": d}
    except Exception as e:
        return {"error": str(e)}

@app.route("/health")
def health():
    return jsonify({"service": "shipstack_dashboard", "port": PORT, "status": "ok"})

@app.route("/api/status")
def api_status():
    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()), "services": [], "discovery": None, "prometheus_jobs": None, "social": None, "revenue": None}
    for name, url in SERVICES:
        ok, data = _fetch_json(url)
        out["services"].append({"name": name, "ok": ok, "detail": data})
    run = _latest_run()
    if run and "data" in run:
        d = run["data"]
        ops = d.get("opportunities") or d.get("ranked") or []
        out["discovery"] = {"file": run["file"], "count": len(ops),
                            "top": [{"keyword": o.get("keyword"), "recommendation": o.get("recommendation"),
                                     "overall": o.get("overall_score"), "signals": o.get("signal_count"),
                                     "suppliers": o.get("supplier_count")} for o in ops[:10]]}
    else:
        out["discovery"] = run
    ok, jobs = _fetch_json("http://prometheus-engine:8766/list")
    out["prometheus_jobs"] = jobs if ok else None
    ok, soc = _fetch_json("http://social-ai-agent:8867/platforms")
    out["social"] = soc if ok else None
    ok, rev = _fetch_json("https://dropship-os-hazel.vercel.app/api/metrics", timeout=8)
    out["revenue"] = rev if ok else {"error": "metrics unreachable"}
    return jsonify(out)

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ShipStack Operations</title>
<style>
body{background:#0b0e14;color:#e6e6e6;font-family:'Segoe UI',Arial,sans-serif;margin:0}
header{padding:16px 24px;background:#11151f;border-bottom:1px solid #232a3a;display:flex;align-items:center;gap:14px}
header h1{font-size:20px;margin:0}
#stamp{color:#8aa;font-size:12px;margin-left:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;padding:18px 24px}
.card{background:#141a26;border:1px solid #232a3a;border-radius:10px;padding:14px 16px}
.card h2{font-size:14px;margin:0 0 10px;color:#9db;letter-spacing:.5px;text-transform:uppercase}
.tile{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1d2433;font-size:14px}
.tile:last-child{border-bottom:none}
.ok{color:#4cd47f}.bad{color:#ff6b6b}.warn{color:#ffc857}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:5px 6px;border-bottom:1px solid #1d2433}
th{color:#8aa}
a{color:#6fb3ff;text-decoration:none}
.links a{display:inline-block;margin-right:14px;margin-top:6px}
</style></head><body>
<header><h1>ShipStack Operations</h1><span id="stamp">loading...</span></header>
<div class="grid">
  <div class="card"><h2>Services</h2><div id="services">loading...</div>
    <div class="links">
      <a href="http://100.66.135.31:8891/" target="_blank">Pipeline Dashboard</a>
      <a href="http://100.66.135.31:8888/" target="_blank">Quinn Command Center</a>
      <a href="https://dropship-os-hazel.vercel.app" target="_blank">Live Site</a>
    </div></div>
  <div class="card"><h2>Revenue (Vercel / Stripe)</h2><div id="revenue">loading...</div></div>
  <div class="card"><h2>Social Platforms</h2><div id="social">loading...</div></div>
  <div class="card" style="grid-column:1/-1"><h2>Latest Discovery Run</h2><div id="discovery">loading...</div></div>
  <div class="card" style="grid-column:1/-1"><h2>Prometheus Jobs</h2><div id="jobs">loading...</div></div>
</div>
<script>
function esc(s){return String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
async function load(){
  try{
    const r = await fetch('/api/status'); const d = await r.json();
    document.getElementById('stamp').textContent = d.generated_at;
    document.getElementById('services').innerHTML = d.services.map(s=>
      '<div class="tile"><span>'+esc(s.name)+'</span><span class="'+(s.ok?'ok':'bad')+'">'+(s.ok?'HEALTHY':'DOWN')+'</span></div>').join('');
    const rev = d.revenue||{};
    document.getElementById('revenue').innerHTML = Object.keys(rev).length ?
      Object.entries(rev).slice(0,8).map(([k,v])=>'<div class="tile"><span>'+esc(k)+'</span><span>'+esc(typeof v==='object'?JSON.stringify(v):v)+'</span></div>').join('') : 'no data';
    const soc = d.social||{};
    document.getElementById('social').innerHTML = '<pre style="white-space:pre-wrap;font-size:12px">'+esc(JSON.stringify(soc,null,1))+'</pre>';
    const disc = d.discovery||{};
    if(disc.top){
      document.getElementById('discovery').innerHTML = '<div style="color:#8aa;font-size:12px;margin-bottom:6px">'+esc(disc.file)+' - '+disc.count+' opportunities</div>'+
        '<table><tr><th>Keyword</th><th>Recommendation</th><th>Score</th><th>Signals</th><th>Suppliers</th></tr>'+
        disc.top.map(o=>'<tr><td>'+esc(o.keyword)+'</td><td>'+esc(o.recommendation)+'</td><td>'+esc(o.overall)+'</td><td>'+esc(o.signals)+'</td><td>'+esc(o.suppliers)+'</td></tr>').join('')+'</table>';
    } else { document.getElementById('discovery').textContent = JSON.stringify(disc); }
    const jobs = d.prometheus_jobs;
    document.getElementById('jobs').innerHTML = '<pre style="white-space:pre-wrap;font-size:12px">'+esc(JSON.stringify(jobs,null,1))+'</pre>';
  }catch(e){ document.getElementById('stamp').textContent = 'error: '+e; }
}
load(); setInterval(load, 30000);
</script></body></html>"""

@app.route("/")
def index():
    return PAGE

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)