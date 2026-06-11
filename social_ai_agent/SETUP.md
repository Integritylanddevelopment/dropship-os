# Social AI Agent — Setup Guide

## What This Is
A fully autonomous Reddit + Pinterest organic growth agent. It discovers subreddits, 
scores them, generates Reddit-native content, builds Pinterest keyword strategies, 
creates pins, runs research, and can operate on a full automated schedule.

---

## Step 1: Install Dependencies

```bash
cd social_ai_agent
pip install -r requirements.txt --break-system-packages
playwright install chromium
```

---

## Step 2: Configure Your Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum:

```
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key_here   # or use OPENAI_API_KEY

BUSINESS_NICHE=dropshipping
BUSINESS_NAME=Your Store Name
WEBSITE_URL=https://yourwebsite.com
TARGET_PRODUCTS=product1,product2,product3
```

Get your Anthropic API key at: https://console.anthropic.com
Get your OpenAI API key at: https://platform.openai.com

---

## Step 3: First-Time Setup

```bash
python main.py setup
```

This will:
- Discover and score 20+ subreddits for your niche
- Build your Pinterest keyword strategy
- Generate your board architecture
- Create a 30-day execution plan

---

## Step 4: Run Your First Sessions

**Reddit — dry run (generates content, doesn't post):**
```bash
python main.py reddit session
```

**Reddit — live (actually posts):**
```bash
python main.py reddit session --auto
```

**Pinterest — generate pins:**
```bash
python main.py pinterest daily --pins 15
```

---

## Step 5: Go Fully Automated

```bash
python main.py schedule --auto
```

Runs on this schedule:
- Reddit comments: 8:30am and 7:00pm daily
- Research pass: Mon/Wed/Fri 6am
- Pinterest morning pins: 8:00am
- Pinterest midday pins: 12:00pm  
- Pinterest evening pins: 8:00pm
- Weekly plan generation: Sunday 9pm

---

## Adding Official API Access (Optional — Faster + More Reliable)

### Reddit API (PRAW)
1. Go to https://www.reddit.com/prefs/apps
2. Create a "script" app
3. Add to `.env`:
```
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USERNAME=...
REDDIT_PASSWORD=...
REDDIT_MODE=api
```

### Pinterest API v5
1. Go to https://developers.pinterest.com
2. Create an app and get your access token
3. Add to `.env`:
```
PINTEREST_ACCESS_TOKEN=...
PINTEREST_APP_ID=...
PINTEREST_MODE=api
```

---

## Key Commands

| Command | What it does |
|---------|-------------|
| `python main.py config` | Check what's configured |
| `python main.py dashboard` | View stats and command list |
| `python main.py setup` | Full first-time setup |
| `python main.py reddit discover` | Find and score subreddits |
| `python main.py reddit session` | Run Reddit session (warmup) |
| `python main.py reddit session --phase active` | Run active session |
| `python main.py reddit research r/dropshipping` | Deep subreddit research |
| `python main.py reddit plan` | Generate 7-day Reddit plan |
| `python main.py pinterest daily` | Generate today's pins |
| `python main.py pinterest keywords` | Build keyword strategy |
| `python main.py pinterest boards` | Design board architecture |
| `python main.py pinterest seasonal` | Seasonal content calendar |
| `python main.py research` | Full market research pass |
| `python main.py schedule --auto` | Start autonomous scheduler |

---

## Reddit Account Strategy (Built In)

The agent follows a 3-phase approach:

**Phase 1: Warmup (Days 1-30)**
- Comments only, no promotion
- 3 comments per day in credibility subreddits
- Target: 500+ karma before moving to active

**Phase 2: Active (Days 31-90)**
- Posts + comments
- 2 posts + 8 comments per day
- No direct promotion until 1000+ karma

**Phase 3: Promotion (90+ days)**
- Strategic soft mentions allowed
- Profile traffic plays
- Link posts in self-promo threads

---

## Pinterest Strategy (Built In)

- 15 pins per day across 3 publishing windows
- 70% fresh pins, 30% variations of top performers
- Seasonal content published 45 days early
- Boards organized by keyword cluster
- Keywords sourced from autocomplete + AI clustering
- Performance tracked: saves, clicks, impressions
