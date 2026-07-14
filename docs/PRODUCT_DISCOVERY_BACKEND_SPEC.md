# Product Discovery Backend — MVP Implementation Spec

**Status:** UI complete (product_discovery_page.html). Backend pending.

**Version:** 2026-06-01 — MVP scope locked (NO ScraperAPI, free APIs only)

---

## ARCHITECTURE: Two-Phase Data Gathering

### PHASE 1: DISCOVERY (Fast, minimal data — feeds Decision Engine)
**Trigger:** User clicks "Search Internet"  
**Data sources:** Amazon, eBay, AliExpress, Google Trends, Reddit, YouTube, Shopify (manual count)  
**Speed:** <2 seconds  
**Purpose:** Decision Engine scores products to decide YES/NO before scraping  
**Cost:** $0 (all free APIs or manual)

### PHASE 2: DEEP DIVE (Massive corpus — only for chosen products)
**Trigger:** Decision Engine says YES + user clicks "Add to Pipeline"  
**Data sources:** YouTube videos (transcripts), Amazon reviews, eBay listings, AliExpress reviews, competitor Shopify pages (manual or simple scrape)  
**Speed:** 30-60 seconds (background job)  
**Purpose:** Feeds Prometheus + social posting with remixable content  
**Cost:** $0 (no ScraperAPI needed)

**Why this approach:**
- Only chosen products get expensive scraping
- Avoid storing gigabytes of data on rejected products
- Discovery stays fast (real sales data, not viral hype)
- API quota usage minimal

---

## API Endpoint 1: `/api/discover` (PHASE 1 — Discovery)

### Request
```
GET /api/discover?q=<search_query>
```

**Parameters:**
- `q` (required): Search query (e.g., "led projection lamp", "portable humidifier")

### Response
```json
{
  "status": "success",
  "query": "led projection lamp",
  "products": [
    {
      "product_name": "Rainbow LED Projection Lamp",
      "supplier": "Zendrop",
      
      "sales_data": {
        "amazon_rank": 145,
        "amazon_sales_estimate": 2400,
        "amazon_review_velocity": 23,
        "ebay_sold_count_30d": 3847,
        "ebay_watch_count": 12340
      },
      
      "supply_data": {
        "aliexpress_stock": 12400,
        "aliexpress_sales_lifetime": 89340,
        "aliexpress_rating": 4.7,
        "supplier_lead_time_days": 7,
        "stock_status": "healthy"
      },
      
      "demand_signals": {
        "google_trends_score": 78,
        "google_trends_velocity": "up_45_percent",
        "reddit_mentions_30d": 567,
        "youtube_review_count": 45
      },
      
      "market_saturation": {
        "competitor_count_estimate": 8420,
        "saturation_level": "medium",
        "new_competitors_per_week": 45,
        "market_direction": "crowding"
      },
      
      "pricing": {
        "amazon_price": 19.99,
        "ebay_avg_price": 21.50,
        "shopify_avg_price": 24.99,
        "supplier_cost": 4.50,
        "margin_low_percent": 35,
        "margin_high_percent": 82
      },
      
      "decision_engine_score": {
        "overall_score": 82,
        "trending_velocity": "accelerating",
        "days_trending": 23,
        "risk_level": "medium",
        "recommendation": "PURSUE"
      },
      
      "discovered_at": "2026-06-01T14:32:00Z"
    }
  ],
  "count": 1,
  "timestamp": "2026-06-01T14:32:00Z"
}
```

---

## API Endpoint 2: `/api/discover/add` (PHASE 2 — Deep Dive Trigger)

### Request
```
POST /api/discover/add
Content-Type: application/json

{
  "product_name": "Rainbow LED Projection Lamp",
  "supplier": "Zendrop",
  "decision_score": 82
}
```

### Response (immediate)
```json
{
  "status": "deep_dive_started",
  "product_name": "Rainbow LED Projection Lamp",
  "job_id": "deepdive_12345",
  "estimated_time": "45 seconds",
  "message": "Gathering massive competitor corpus. You will be notified when complete."
}
```

### Background job does:
1. Scrape all YouTube videos about this product → extract transcripts
2. Scrape all Amazon reviews → extract customer feedback + pain points
3. Scrape all eBay listings for this product → analyze competitor pricing + positioning
4. Scrape all AliExpress reviews → quality feedback
5. Find and scrape competitor Shopify stores (manual search + simple scrape)
   - Extract all product images
   - Extract all product copy/descriptions
   - Extract pricing strategies (launch price vs current)
   - Extract discount patterns
6. Analyze competitor account warmup patterns (posting frequency from AliExpress reviews dates)
7. Store complete corpus in `/product_corpus/<product_name>/` folder
8. Mark as "ready_for_prometheus"

### Corpus folder structure:
```
/product_corpus/Rainbow-LED-Projection-Lamp/
├── metadata.json
│   ├── product_name
│   ├── supplier
│   ├── cost
│   ├── margin
│   ├── decision_score
│   ├── discovered_at
│   └── corpus_completed_at
│
├── competitor_data.json
│   ├── shopify_store_count
│   ├── avg_selling_price
│   ├── discount_patterns
│   └── competitor_urls
│
├── youtube_corpus/
│   ├── videos.json (URLs, view count, upload date)
│   ├── transcripts/ (extracted text from videos)
│   └── thumbnails/ (downloaded images)
│
├── amazon_reviews/
│   ├── reviews.json (text, rating, helpful count)
│   └── common_complaints.txt
│
├── ebay_corpus/
│   ├── completed_listings.json (pricing, sold count)
│   └── competitor_positioning.txt
│
├── images/
│   ├── amazon_product_images/
│   ├── shopify_competitor_images/
│   ├── ebay_listing_images/
│   └── youtube_thumbnails/
│
├── copy/
│   ├── amazon_descriptions.txt
│   ├── shopify_sales_copy.txt
│   ├── ebay_listings.txt
│   └── all_copy_compiled.txt (searchable corpus)
│
└── warmup_analysis.json
    ├── posting_frequency
    ├── engagement_patterns
    └── competitor_account_age
```

---

## API Endpoint 3: `/api/discover/product/<product_id>` (Read full corpus)

### Request
```
GET /api/discover/product/rainbow-led-projection-lamp
```

### Response (Used by Decision Engine, Prometheus, Social Posting)
```json
{
  "product_name": "Rainbow LED Projection Lamp",
  "supplier": "Zendrop",
  "cost": 4.50,
  "margin": 77,
  
  "sales_proof": {
    "amazon_rank": 145,
    "amazon_monthly_sales": 2400,
    "ebay_30day_sales": 3847,
    "supplier_lifetime_sales": 89340
  },
  
  "competitor_analysis": {
    "shopify_stores": 234,
    "avg_selling_price": 24.99,
    "discount_frequency": "25% run promotions"
  },
  
  "content_corpus": {
    "youtube_videos": 45,
    "amazon_reviews": 2340,
    "ebay_listings": 156,
    "unique_images": 156,
    "total_copy_length_chars": 45670
  },
  
  "amazon_reviews_sample": [
    {
      "rating": 5,
      "text": "Amazing product! Love how bright it is...",
      "helpful": 234
    }
  ],
  
  "top_copy_angles": [
    "Transform your room into a galaxy",
    "Perfect for gaming setups",
    "Relaxing ambient lighting",
    "Great for parties and mood setting"
  ],
  
  "image_urls": [
    "file:///product_corpus/Rainbow-LED-Projection-Lamp/images/amazon_product_images/img_1.jpg",
    "file:///product_corpus/Rainbow-LED-Projection-Lamp/images/shopify_competitor_images/img_2.jpg"
  ],
  
  "warmup_data": {
    "typical_posting_frequency": "3-5 per day",
    "engagement_rate_avg": "8.2%"
  },
  
  "ready_for_prometheus": true,
  "corpus_completed_at": "2026-06-01T15:12:00Z"
}
```

---

## Data Sources: MVP Stack (FREE)

| Source | Query type | Data provided | Rate limit | Cost |
|--------|-----------|---------------|-----------|------|
| **Amazon Product Advertising API** | Product search | Rank, price, sales est, review velocity | 100 req/sec burst | Free (first 100/mo) |
| **eBay API** | Product search | Sold count, watch count, avg price | 30 req/sec | Free |
| **AliExpress** | Product scrape | Stock, lifetime sales, rating | Proxy rotation | Free |
| **Google Trends API** | Keyword search | Trend score, velocity | 500/day | Free (cache heavily) |
| **YouTube Data API** | Video search | View count, upload date, review count | 10k quota/day free | Free |
| **Reddit API** | Subreddit search | Mention count, upvotes | 60 req/min | Free |
| **Shopify** | Competitor store scrape | Store count, competitor URLs (manual count) | Manual | Free |

**Total cost for MVP: $0**

---

## Implementation Priority

### Phase 1: MVP (This week)
- [ ] GET /api/discover endpoint
- [ ] Amazon API integration (sales rank + price)
- [ ] eBay API integration (sold count + watch count)
- [ ] AliExpress scrape (stock + lifetime sales + rating)
- [ ] Google Trends integration (trend score + velocity)
- [ ] Decision Engine scoring logic (all data aggregated)

### Phase 2: Expand (Next week)
- [ ] YouTube API (video count for product)
- [ ] Reddit API (mention count)
- [ ] Shopify competitor detection (manual or basic scrape)
- [ ] Caching layer (Google Trends results cache)
- [ ] POST /api/discover/add endpoint (Phase 2 trigger)

### Phase 3: Deep Dive (Following week)
- [ ] YouTube corpus scraping (transcripts)
- [ ] Amazon reviews scraping (detailed feedback)
- [ ] eBay listings analysis
- [ ] Shopify competitor copy scraping
- [ ] Image downloading
- [ ] GET /api/discover/product/<id> endpoint (return full corpus)

---

## Success Criteria

✓ User searches "led projection lamp"  
✓ Gets results in <2 seconds with: sales data (Amazon, eBay), supply data (AliExpress), demand signals (Google Trends, YouTube, Reddit), market saturation (competitor count), pricing tiers, Decision Engine score  
✓ Decision Engine says "PURSUE" or "SKIP"  
✓ If PURSUE: user clicks "Add to Pipeline" → background job starts deep dive  
✓ Deep dive completes in 30-60 seconds → corpus ready for Prometheus  
✓ Prometheus pulls corpus data and generates video  
✓ Social posting uses corpus for remixing  

---

## Why This Works

**Real sales data beats viral hype:**
- Amazon rank = actual customer purchases happening NOW
- eBay completed sales = proof of demand
- AliExpress lifetime sales = supplier-side confirmation
- Competitor count = market reality (not hype)

**Two-phase saves time + resources:**
- Phase 1 is fast (2 sec, free APIs)
- Phase 2 only runs on products you actually chose
- No wasted corpus storage on rejected products

**Everything is free:**
- No ScraperAPI ($29/mo)
- No third-party trending services ($99+/mo)
- Just smart use of free APIs + manual scraping

---

**Owner:** Alex Alexander  
**Created:** 2026-06-01  
**Status:** Spec locked, ready to build Phase 1
