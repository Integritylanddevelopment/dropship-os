# ShipStack Product Discovery Engine - Canonical Spec
Source: Alex direct paste, 2026-06-07
Status: Authoritative. Replaces earlier scattered intent. This file IS the brief.

## Goal
Build a product discovery engine that finds early-wave consumer product trends from downstream demand signals, then matches those products to dropshipping or supplier sources with strong margin potential.

## Core Strategy
Identify products beginning to trend on consumer-facing platforms before they become saturated. Detect early demand signals from TikTok, Instagram, YouTube Shorts, Pinterest, Reddit, Amazon, Etsy, Google Trends, and other social platforms. Once a product shows rising interest, search upstream supply sources: 1688, Taobao, AliExpress, CJdropshipping, Zendrop, Spocket, Alibaba, private supplier catalogs.

## Primary Objective - Find products with:
- Early rising social interest
- High content marketing potential
- Available dropshipping or wholesale supply
- Large price gap between supplier cost and consumer retail
- Strong visual appeal
- Low shipping complexity
- Low saturation
- High impulse-buy potential

## Downstream Signal Collection
Scrapers / API integrations / search modules for: TikTok, Instagram Reels, YouTube Shorts, Pinterest, Reddit, Etsy, Amazon, Google Trends, Facebook groups (if available), X/Twitter (if useful).

Per-platform signals: product keywords, hashtags, video titles, captions, comments, mentions, engagement rate, view/like/share/save counts, comment velocity, # creators posting, # recent posts, date of first detected spike, comment sentiment, and buyer-intent phrases ("where can I buy this", "link please", "need this", "Amazon link", "TikTok made me buy it", "does this ship to me").

## Trend Detection Logic
Find products at the BEGINNING of a demand wave, not already-saturated ones.

Score HIGHER when: mentions rising fast over 3/7/14 days; multiple creators on same product; engagement growing faster than post volume; comments show purchase intent; people asking where to buy; visually demonstrable in short-form video; few established stores; ads not yet saturated; search volume rising but not peaking.

Score LOWER when: too many Shopify stores already selling; Amazon has many identical listings with high review counts; TikTok Shop saturated; paid ad libraries show heavy competition; supplier cost too high; shipping slow/expensive; product fragile/oversized/restricted/hard-to-explain.

## Product Extraction (per trending post or listing)
Product name, description, keywords, hashtags, platform source, source URL, creator/seller name, engagement metrics, comment examples showing purchase intent, detected category, estimated buyer persona, visual hooks, problem solved, suggested marketing angle.

## Upstream Supply Search
Sources: 1688.com, Taobao, AliExpress, Alibaba, CJdropshipping, Zendrop, Spocket, AutoDS-compatible suppliers, DSers-compatible suppliers, private supplier lists.

Matching uses: keyword similarity, translated Chinese keywords, image similarity, product category, variant match, material match, dimensions, packaging style, supplier title similarity.

Per-supplier extract: supplier name, product URL, image, unit cost, MOQ, processing time, shipping time, shipping options, dropshipping availability, bulk availability, supplier rating, review count, estimated landed cost, available variants, return/refund policy, blind dropshipping support.

## Margin Analysis (per product)
Estimated consumer retail price, supplier unit cost, shipping cost, platform fees, payment processing fees, estimated ad/content production cost, estimated landed cost, estimated gross margin, estimated net margin, break-even CPA, recommended selling price.

Prioritize products where: gross margin >= 60%; sellable at >= 3x landed cost; simple shipping; acceptable delivery time; strong video content potential; supplier can scale.

## Content Marketing Priority Score
HIGHER when: easy to demonstrate visually; solves obvious problem; creates curiosity; before-and-after potential; surprising/satisfying/weird/cute/useful/giftable; comments show strong buyer intent; multiple content hooks; supports daily short-form testing; high perceived value vs actual cost.

## Output - Product Opportunity Report
Product name, category, downstream trend score, supply availability score, margin score, saturation score, content marketing score, overall opportunity score, main social source URL, top 3 social posts/trend sources, top 3 supplier links, estimated retail price, estimated landed cost, estimated gross margin, MOQ, shipping concerns, supplier concerns, recommended content angles, recommended offer structure, recommended selling platform, final recommendation (pursue / test / watch / skip).

## Ranking Weights
- Downstream demand velocity: 30%
- Buyer intent in comments: 20%
- Supplier availability and cost: 20%
- Content marketing potential: 15%
- Low saturation: 10%
- Shipping simplicity: 5%

## System Workflow
1. Scan downstream platforms for early product signals.
2. Extract product candidates from posts, captions, comments, hashtags, listings.
3. Cluster similar product mentions into one product opportunity.
4. Measure trend velocity over 3, 7, 14 days.
5. Detect buyer intent from comments.
6. Check saturation across Amazon, TikTok Shop, Shopify, Etsy, ad libraries.
7. Search upstream supplier sources.
8. Match trending products to supplier listings.
9. Estimate landed cost and margin.
10. Score the product opportunity.
11. Generate a ranked list of products to test.
12. Recommend which products deserve the most content marketing effort.

## Important Notes
The system should not only find popular products. It should find products becoming popular EARLY enough to enter before the market is crowded.

Best opportunities = rising downstream attention + clear purchase intent + accessible supply + high margin + strong content marketing potential.

Avoid: already saturated, hard to ship, legally risky, low margin, impossible to explain in short-form content.

---

## SOURCE AVAILABILITY STATUS (2026-06-07 audit)

Three tiers: **WIRED** = code exists and works; **AVAILABLE NOW** = free no-auth path exists, can wire today; **BLOCKED** = needs paid API / OAuth / Selenium / cookie session.

### Downstream signal sources

| Platform | Tier | How |
|---|---|---|
| Reddit | **WIRED** | api.pullpush.io (Pushshift mirror). 50+25 posts/sub verified 2026-06-07. social_ai_agent/automation/reddit_browser.py |
| Pinterest | partial WIRED (broken) | social_ai_agent/agents/pinterest_agent.py exists, browser mode, but selectors stale -> 0 results. Pinterest RSS feeds `pinterest.com/<user>/<board>.rss` work auth-less; HTML pin pages have JSON-LD embedded. Re-wire on RSS + JSON-LD. |
| Google Trends | **AVAILABLE NOW** | `pytrends` Python lib (free, no auth). 5-min wire. Gives 3/7/14-day velocity directly. |
| YouTube Shorts | **AVAILABLE NOW** | `yt-dlp` or `youtube-search-python`. Free, no API key. Returns view/like counts + comments + title + tags. |
| Amazon | **AVAILABLE NOW (partial)** | Amazon Movers & Shakers RSS feeds (`/gp/movers-and-shakers/<category>/`) are public. Product Advertising API needs PA-API credentials. |
| Etsy | **AVAILABLE NOW** | Etsy trending HTML pages scrape without login. Official API needs OAuth. |
| TikTok | BLOCKED (free) | No public API. Options: TikTok Research API (academic only), unofficial libs like `TikTokApi` (cookie session required + breaks often), paid scrapers (Apify, ScrapeCreators). |
| Instagram Reels | BLOCKED (free) | Same as TikTok. Official API requires Meta business app. `instaloader` works for public profiles but rate-limited heavily. |
| Facebook groups | BLOCKED | Meta Graph API only. Requires app + user token. |
| X/Twitter | BLOCKED (free) | API tier removed in 2023. $100+/mo for basic. Only `snscrape` works limp now. |

### Upstream supplier sources

| Source | Tier | How |
|---|---|---|
| AliExpress | BLOCKED (stdlib) | Anti-bot (302 redirect loop or shell page on retry). Open Platform API needs OAuth + app. Selenium + persistent profile works. |
| CJdropshipping | **AVAILABLE NOW** | Open API. Free dev tier. Product search, pricing, inventory all exposed via REST. https://developers.cjdropshipping.com |
| Spocket | **AVAILABLE NOW (partial)** | Public catalog browse without login. Affiliate API for deeper integration. |
| 1688.com | BLOCKED | Chinese-IP-friendly. Anti-bot heavy. Needs proxy + translated keyword pipeline. Image-search API is paid. |
| Taobao | BLOCKED | Same as 1688. |
| Alibaba | BLOCKED (free) | Public catalog scrape possible but anti-bot aggressive. Real path is Alibaba RFQ API (requires business account). |
| Zendrop | BLOCKED | Login required to browse catalog. No public catalog API. |
| AutoDS / DSers | BLOCKED | These are integration tools, not direct sources. They proxy AliExpress / Amazon. Skip. |

### MVP achievable today (no cards, no OAuth)

The free combo that gets the discovery engine producing real opportunity reports immediately:

**Downstream:** Reddit (WIRED) + Google Trends + YouTube Shorts + Amazon Movers&Shakers RSS + Etsy trending + Pinterest RSS.

**Upstream:** CJdropshipping API + Spocket public browse.

That is 6 downstream + 2 upstream = enough for the full Discover -> Score -> Match -> Margin -> Rank workflow described above. The blocked sources are nice-to-haves that come later when paid API tiers or Selenium fleet are budgeted.

### Build priority (next operator pick up here)

1. Google Trends via pytrends - 30 min, biggest immediate signal lift
2. YouTube Shorts via yt-dlp - 1 hour, gives view-count velocity
3. Amazon Movers & Shakers RSS - 30 min, gives "what's heating up" baseline
4. Etsy trending HTML - 1 hour
5. Pinterest re-wire on RSS + JSON-LD (replaces stale selectors) - 2 hours
6. CJdropshipping API supplier match - 2-3 hours
7. Spocket public catalog browse - 1 hour
8. Cluster + score across all signals - 4 hours
9. Margin / saturation / content-potential scoring + Output report - 4 hours

Total ~17 hours of focused work for a real working MVP using only free sources.
