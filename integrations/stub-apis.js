/**
 * Stub API Implementations for MVP
 * These are placeholder implementations that return mock data
 * Will be replaced with real API calls in Phase 2+3
 */

export class EbayAPI {
  async searchProducts(query) {
    console.log(`[EBAY] Searching for: "${query}" (stub)`);
    return [
      {
        product_name: query,
        sold_count_30d: Math.floor(Math.random() * 5000) + 100,
        watch_count: Math.floor(Math.random() * 3000) + 200,
        average_price: Math.random() * 50 + 15
      }
    ];
  }
}

export class AliexpressAPI {
  async searchProducts(query) {
    console.log(`[ALIEXPRESS] Searching for: "${query}" (stub)`);
    return [
      {
        product_name: query,
        stock: Math.floor(Math.random() * 50000) + 1000,
        lifetime_sales: Math.floor(Math.random() * 500000) + 10000,
        rating: Math.random() * 1.5 + 3.5,
        cost: Math.random() * 20 + 3,
        lead_time_days: Math.floor(Math.random() * 20) + 5
      }
    ];
  }
}

export class GoogleTrendsAPI {
  async getTrendScore(query) {
    console.log(`[GOOGLE_TRENDS] Fetching trend score for: "${query}" (stub)`);
    const score = Math.floor(Math.random() * 100);
    const velocity = ['accelerating', 'stable', 'decelerating'][Math.floor(Math.random() * 3)];
    return {
      trend_score: score,
      velocity
    };
  }
}

export class YoutubeAPI {
  async searchProductReviews(query) {
    console.log(`[YOUTUBE] Searching for reviews of: "${query}" (stub)`);
    return [
      {
        product_name: query,
        review_count: Math.floor(Math.random() * 100) + 5
      }
    ];
  }
}

export class RedditAPI {
  async searchMentions(query) {
    console.log(`[REDDIT] Searching for mentions of: "${query}" (stub)`);
    return {
      mentions_30d: Math.floor(Math.random() * 1000) + 50
    };
  }
}

export class ShopifyAPI {
  async getCompetitorCount(query) {
    console.log(`[SHOPIFY] Estimating competitors for: "${query}" (stub)`);
    return {
      estimated_store_count: Math.floor(Math.random() * 50000) + 100,
      sample_stores: [] // Would populate with actual store URLs
    };
  }
}
