import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from flask import Flask, render_template_string, request
import urllib.request

app = Flask(__name__)

@app.route('/health')
def health():
    return {"status":"ok","service":"shipstack_dashboard","port":8890}

@app.route('/')
def index():
    html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>ShipStack Dashboard</title>
        <style>
            body { background-color: #0a0a0a; color: white; font-family: Arial, sans-serif; }
            .card {
                border: 1px solid grey;
                padding: 20px;
                border-radius: 8px;
                margin: 10px;
            }
        </style>
    </head>
    <body>
        <h1>ShipStack Operations</h1>
        <div class="card"><a href="http://127.0.0.1:8889/health">Engine</a></div>
        <div class="card"><a href="http://127.0.0.1:8766/health">Prometheus</a></div>
        <div class="card"><a href="http://127.0.0.1:8867/health">Social</a></div>
        <div class="card"><a href="http://127.0.0.1:8891/">Pipeline</a></div>
    </body>
    </html>
    '''
    return html

@app.route('/api/status')
def api_status():
    services = {
        'Engine': 'http://127.0.0.1:8889/health',
        'Prometheus': 'http://127.0.0.1:8766/health',
        'Social': 'http://127.0.0.1:8867/health',
        'Pipeline': 'http://127.0.0.1:8891/'
    }
    status = {}
    for service, url in services.items():
        try:
            response = urllib.request.urlopen(url, timeout=2)
            if response.getcode() == 200:
                status[service] = 'up'
            else:
                status[service] = 'down'
        except Exception as e:
            status[service] = 'down'
    return status

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8890, debug=False, use_reloader=False)