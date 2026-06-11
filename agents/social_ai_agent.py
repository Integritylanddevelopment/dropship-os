import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from flask import Flask, request, jsonify
import uuid

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return {"status":"ok","service":"social_ai_agent","port":8867}

@app.route('/agents', methods=['GET'])
def agents():
    return {
        "agents":[
            {"name":"tiktok","status":"idle"},
            {"name":"instagram","status":"idle"},
            {"name":"pinterest","status":"idle"},
            {"name":"youtube","status":"idle"}
        ]
    }

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    return {
        "platform":data['platform'],
        "topic":data['topic'],
        "draft":"Draft post about " + data['topic'],
        "status":"draft"
    }

@app.route('/post', methods=['POST'])
def post():
    data = request.get_json()
    return {
        "status":"queued",
        "platform":data['platform'],
        "id":"stub-" + str(uuid.uuid4())
    }

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8867, debug=False, use_reloader=False)