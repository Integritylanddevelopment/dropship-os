# DROPSHIP INTELLIGENCE AGENT — SETUP GUIDE

## What This Does

This is a fully autonomous AI agent that:
- Scouts for high-margin, low-competition dropshipping products
- Finds the cheapest attention channels (CPM/CPC arbitrage)
- Scores every product × channel combination
- Generates content hooks, TikTok scripts, and 30-day content plans
- Ranks and labels winner products with special badges
- Saves reports as Markdown + JSON automatically
- Serves a live web dashboard at `localhost:3737`
- Runs continuously in monitor mode (scans every 60 minutes)

---

## Quick Start

### Step 1 — Install dependencies
```bash
cd dropship-agent
npm install
```

### Step 2 — Set your API key
```bash
# Mac/Linux:
export ANTHROPIC_API_KEY=your-key-here

# Windows:
set ANTHROPIC_API_KEY=your-key-here
```
Get your key at: https://console.anthropic.com

### Step 3 — Run your first scan
```bash
node index.js scan
```

---

## All Commands

| Command | What It Does |
|---------|-------------|
| `node index.js scan` | Full scan — products + channels + scoring + content + report |
| `node index.js scan --niche "health"` | Scan a specific niche |
| `node index.js scan --products 20` | Scout 20 products instead of 10 |
| `node index.js products` | Products only |
| `node index.js products "pet accessories"` | Products in a specific niche |
| `node index.js channels` | Channel CPM scan only |
| `node index.js research "sleep mask"` | Quick research a single product |
| `node index.js content "sleep mask"` | Generate content strategy only |
| `node index.js monitor` | Run continuous scans every 60 minutes |
| `node index.js monitor --interval 30` | Scan every 30 minutes |
| `node index.js dashboard` | Serve web dashboard at localhost:3737 |
| `node index.js history` | View scan history in terminal |

---

## Optional: Live Web Search

For real-time data (instead of AI estimation), add a SerpAPI key:

```bash
export SERP_API_KEY=your-serp-key
```

Free tier at https://serpapi.com gives 100 searches/month.

The agent works perfectly without this — it uses DuckDuckGo as a free fallback.

---

## Output Files

Every scan saves:
- `reports/scan-YYYY-MM-DD-HH-MM-SS.json` — Full structured data
- `reports/scan-YYYY-MM-DD-HH-MM-SS.md`   — Formatted markdown report
- `reports/latest.json`                     — Dashboard-ready data (always overwritten)
- `data/products.json`                      — Persistent product database

---

## Architecture

```
index.js              ← CLI entry point
agent.js              ← Main orchestrator
config.js             ← All configuration
modules/
  product-scout.js    ← AI agent that scouts product opportunities
  channel-scout.js    ← AI agent that finds cheapest attention channels
  scorer.js           ← Scoring engine (demand × competition × margin × etc.)
  content.js          ← Content hook + script generator
  reporter.js         ← Report output (JSON, Markdown)
  web-search.js       ← DuckDuckGo + SerpAPI search
data/
  products.json       ← Persistent product database
  platforms.json      ← Platform CPM benchmarks
  scoring-matrix.json ← Scoring weights and thresholds
dashboard/
  index.html          ← Full web dashboard
reports/              ← All generated reports
```

---

## The Scoring Model

Each product is scored 1-10 across 5 dimensions:

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Demand | 25% | Search volume, social engagement, trend velocity |
| Competition | 20% | Seller count, ad density, brand dominance (INVERTED) |
| Attention Cost | 20% | CPM, CPC, organic potential (INVERTED) |
| Margin | 20% | Gross margin %, AOV, return risk |
| Launch Speed | 15% | Days to source, regulatory risk, IP risk |

Final score = weighted average. 8.5+ = launch immediately.

---

## Winner Labels

Every scan assigns 5 special labels:

- 🥇 **Best Overall** — highest combined score
- 🔵 **Best Low Competition** — biggest market gap
- 💚 **Best Cheap Attention** — lowest CAC channel
- 💰 **Best Margin** — highest gross margin %
- 🚀 **Best Fast Launch** — fastest to source and start selling
