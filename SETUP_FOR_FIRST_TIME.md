# First Time Setup — ShipStack AI

**Architecture:** ShipStack is a Vercel front-end that requires a Local AI Stack running on your machine and exposed via ngrok. The Vercel site handles routing; your machine handles AI inference.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Windows 10+ | — | Mac/Linux: adapt bat files to shell scripts |
| Python | 3.10+ | `python --version` |
| Node.js | 16+ | for Vercel CLI |
| Docker Desktop | any | runs Qdrant |
| Ollama | any | `ollama.ai` |
| ngrok | any | `ngrok.com` free tier is fine |
| Vercel CLI | latest | `npm install -g vercel` |

---

## Step 1 — Clone the repo

```powershell
git clone https://github.com/Integritylanddevelopment/dropship-os.git
cd dropship-os
```

---

## Step 2 — Set up .env

Copy the template and fill in your keys:

```powershell
copy .env.example .env
```

Edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
STRIPE_SECRET_KEY=sk_live_...
QUINN_BRIDGE_SECRET=dropship-os-quinn-2026-alex
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
OLLAMA_HOST=127.0.0.1
OLLAMA_PORT=11434
QUINN_BRIDGE_PORT=8765
```

---

## Step 3 — Start Qdrant (Docker)

```powershell
docker run -d -p 6333:6333 --name qdrant qdrant/qdrant
```

Verify it's running:
```powershell
curl http://127.0.0.1:6333/collections
```

---

## Step 4 — Create Qdrant Partitions

Run once to create the required collections:

```powershell
cd dropship-os
python SETUP_QDRANT_PARTITIONS.py
```

Verify:
```powershell
cd ..
python verify_qdrant_partitions.py
```

Expected output: `[PASS] All partitions present.`

---

## Step 5 — Start Ollama + pull models

```powershell
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
```

---

## Step 6 — Install Python dependencies

```powershell
pip install -r requirements.txt
```

---

## Step 7 — Set Vercel Environment Variables

Go to: https://vercel.com/togetherwe/dropship-os/settings/environment-variables

Add:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your Anthropic key |
| `STRIPE_SECRET_KEY` | your Stripe key |
| `QUINN_BRIDGE_SECRET` | `dropship-os-quinn-2026-alex` |
| `QUINN_ENDPOINT` | leave blank for now (set in Step 9) |

---

## Step 8 — Start Everything Locally

Double-click or run:

```
dropship-os\START_ALL.bat
```

This will:
1. Start Quinn Web Bridge on port 8765
2. Open ngrok to expose it publicly

---

## Step 9 — Update Vercel with Your ngrok URL

Copy the `https://xxxx.ngrok-free.app` URL from the ngrok window.

Then run:

```
dropship-os\UPDATE_QUINN_ENDPOINT.bat
```

Paste your ngrok URL when prompted. It will update Vercel and redeploy.

---

## Step 10 — Verify Everything Works

1. Open https://dropship-os-gamma.vercel.app
2. Check bridge status: https://dropship-os-gamma.vercel.app/api/health
   - Should return `{"status":"connected",...}`
3. Try the chat widget on any page
4. Check metrics: https://dropship-os-gamma.vercel.app/api/metrics

---

## Ongoing Usage

Each session:
1. Make sure Docker is running (Qdrant)
2. Make sure Ollama is running
3. Run `dropship-os\START_ALL.bat`
4. If ngrok URL changed, run `dropship-os\UPDATE_QUINN_ENDPOINT.bat`

To automate ngrok: use a paid ngrok plan with a static domain, set `QUINN_ENDPOINT` in Vercel permanently.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/api/health` returns `no_endpoint` | `QUINN_ENDPOINT` not set in Vercel | Run `UPDATE_QUINN_ENDPOINT.bat` |
| `/api/health` returns `disconnected` | Quinn bridge not running or ngrok down | Run `START_ALL.bat` |
| Chat returns errors | `ANTHROPIC_API_KEY` not set | Set in Vercel dashboard |
| Metrics show null | Quinn bridge offline | Check `/api/health` first |
| Qdrant missing partitions | Docker not running | `docker start qdrant` |
