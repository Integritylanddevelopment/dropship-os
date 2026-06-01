#!/usr/bin/env python3
"""
Scrapling runner — handles TikTok + Shopify scraping with Cloudflare bypass
Called from Node.js via subprocess spawn
Returns JSON to stdout
"""

import json
import sys
import asyncio
from datetime import datetime

# Try to import Scrapling; graceful fallback if not installed
try:
    from scrapling import StealthyFetcher
    HAS_SCRAPLING = True
except ImportError:
    HAS_SCRAPLING = False
    print("WARNING: Scrapling not installed. Using mock data.", file=sys.stderr)


async def scrape_tiktok_trending():
    """Scrape TikTok discover page for trending products"""
    if not HAS_SCRAPLING:
        return {
            "status": "mock",
            "reason": "Scrapling not installed",
            "products": [
                {
                    "product_name": "LED Projection Lamp",
                    "video_count": 45000,
                    "views": 1200000000,
                    "engagement_rate": 0.082
                }
            ]
        }
    
    try:
        fetcher = StealthyFetcher(auto_match=True)
        
        # Fetch TikTok trending page
        result = await fetcher.fetch(
            "https://www.tiktok.com/discover/trending-products",
            headless=True,
            network_idle=True,
            timeout=30
        )
        
        # Parse product cards
        products = []
        for card in result.css("div[data-product-card]"):
            try:
                name = card.css("h3.product-name::text").get()
                views = card.css("span.views::text").get()
                engagement = card.css("span.engagement::text").get()
                
                if name:
                    products.append({
                        "product_name": name.strip(),
                        "views": int(views.replace(",", "")) if views else 0,
                        "engagement_rate": float(engagement.replace("%", "")) / 100 if engagement else 0
                    })
            except Exception as e:
                continue
        
        return {
            "status": "success",
            "products_found": len(products),
            "products": products[:10]  # Top 10
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


async def scrape_shopify_store(store_url, product_name):
    """Scrape a single Shopify store for product data"""
    if not HAS_SCRAPLING:
        return {
            "status": "mock",
            "reason": "Scrapling not installed",
            "store_url": store_url,
            "product_data": {
                "title": product_name,
                "price": 34.99,
                "reviews_count": 342,
                "rating": 4.6
            }
        }
    
    try:
        fetcher = StealthyFetcher(auto_match=True)
        
        # Scrape store page
        page = await fetcher.fetch(
            store_url,
            headless=True,
            network_idle=True,
            timeout=30
        )
        
        # Extract data
        title = page.css("h1.product-title::text").get() or product_name
        price = page.css("span.price::text").get()
        reviews_count = page.css("span.review-count::text").get()
        rating = page.css("span.rating::text").get()
        images = page.css("img.product-image::attr(src)").getall()
        description = page.css("div.product-description::text").getall()
        
        # Parse reviews
        reviews = []
        for review_elem in page.css("div.review-item"):
            try:
                rev_text = review_elem.css("p.review-text::text").get()
                rev_rating = review_elem.css("span.stars::attr(data-rating)").get()
                if rev_text:
                    reviews.append({
                        "text": rev_text.strip(),
                        "rating": int(rev_rating) if rev_rating else 5
                    })
            except:
                continue
        
        return {
            "status": "success",
            "store_url": store_url,
            "product_data": {
                "title": title.strip() if title else product_name,
                "price": float(price.replace("$", "")) if price else 0,
                "reviews_count": int(reviews_count) if reviews_count else 0,
                "rating": float(rating) if rating else 0,
                "images": images[:5],  # Top 5 images
                "description": " ".join(description),
                "reviews": reviews[:10]  # Top 10 reviews
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "store_url": store_url
        }


async def main():
    """Entry point — reads args from Node.js, runs scraper, outputs JSON"""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No arguments provided"}))
        sys.exit(1)
    
    try:
        args = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON arguments"}))
        sys.exit(1)
    
    action = args.get("action")
    
    if action == "tiktok_trending":
        result = await scrape_tiktok_trending()
    elif action == "shopify_store":
        result = await scrape_shopify_store(
            args.get("store_url"),
            args.get("product_name")
        )
    else:
        result = {"error": f"Unknown action: {action}"}
    
    # Output JSON to stdout (Node.js will parse this)
    print(json.dumps(result))


if __name__ == "__main__":
    asyncio.run(main())
