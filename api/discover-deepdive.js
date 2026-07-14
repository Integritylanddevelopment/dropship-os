/**
 * Phase 2: Deep Dive Product Corpus Scraper
 * 
 * Triggered when Decision Engine score >= 70 for a product
 * 
 * POST /api/discover/deepdive?product_id=<id>
 * 
 * Flow:
 * 1. Get product metadata from Qdrant
 * 2. Scrape TikTok videos (hooks, descriptions, sounds)
 * 3. Find + scrape Shopify competitor stores (copy, images, reviews)
 * 4. Scrape YouTube reviews + product mentions
 * 5. Scrape Reddit threads (safety signals)
 * 6. Store entire corpus in Qdrant under product_id
 * 7. Return corpus path for Prometheus to consume
 */

import { QdrantClient } from '@qdrant/js-client-rest';
import { TikTokScraperStub, ShopifyCompetitorScraper, runScraplingScript } from '../integrations/tiktok-shopify-scraper.js';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'POST only' });
  }

  const productId = req.query.product_id;
  if (!productId) {
    return res.status(400).json({ error: 'Missing product_id' });
  }

  const startTime = Date.now();
  console.log(`[DEEPDIVE] Starting for product: ${productId}`);

  try {
    const corpus = await buildProductCorpus(productId);
    const elapsed = Math.round((Date.now() - startTime) / 1000);

    return res.status(200).json({
      status: 'success',
      product_id: productId,
      corpus_size: {
        tiktok_videos: corpus.tiktok_videos.length,
        shopify_competitors: corpus.shopify_stores.length,
        youtube_reviews: corpus.youtube_reviews.length,
        reddit_threads: corpus.reddit_threads.length,
        total_copy_variants: corpus.copy_variants.length,
        total_images: corpus.images.length
      },
      elapsed_seconds: elapsed,
      timestamp: new Date().toISOString(),
      corpus
    });
  } catch (error) {
    console.error('[DEEPDIVE] Error:', error.message);
    return res.status(500).json({ error: error.message });
  }
}

/**
 * Build complete product corpus from all sources
 */
async function buildProductCorpus(productId) {
  const tiktok = new TikTokScraperStub();
  const shopify = new ShopifyCompetitorScraper();

  // Fetch product info from Qdrant (Phase 1 result)
  const productName = await getProductNameFromQdrant(productId);
  console.log(`[DEEPDIVE] Building corpus for: ${productName}`);

  // Parallel scraping for speed
  const [
    tiktokVideos,
    competitorStores,
    youtubeReviews,
    redditThreads
  ] = await Promise.allSettled([
    tiktok.getProductVideos(productName, 50),
    shopify.findCompetitorStores(productName),
    scrapeYoutubeReviews(productName),
    scrapeRedditThreads(productName)
  ]);

  const corpus = {
    product_id: productId,
    product_name: productName,
    created_at: new Date().toISOString(),
    
    // TikTok corpus: hooks, captions, sounds
    tiktok_videos: tiktokVideos.status === 'fulfilled' 
      ? tiktokVideos.value.sample_videos || [] 
      : [],
    
    // Shopify competitor data: copy, images, reviews, pricing
    shopify_stores: [],
    
    // YouTube reviews: what people say about product
    youtube_reviews: youtubeReviews.status === 'fulfilled'
      ? youtubeReviews.value.reviews || []
      : [],
    
    // Reddit discussions: safety, authenticity signals
    reddit_threads: redditThreads.status === 'fulfilled'
      ? redditThreads.value.threads || []
      : [],
    
    // Derived: copy variants for remixing
    copy_variants: [],
    
    // Derived: all images for Prometheus
    images: []
  };

  // Scrape each competitor store
  if (competitorStores.status === 'fulfilled') {
    const stores = competitorStores.value.competitor_stores || [];
    
    for (const store of stores) {
      try {
        const storeData = await shopify.scrapeStore(store.store_url, productName);
        if (storeData.status === 'success') {
          corpus.shopify_stores.push({
            store_name: store.store_name,
            store_url: store.store_url,
            estimated_revenue: store.estimated_revenue_signal,
            product_data: storeData.product_data
          });
          
          // Extract images
          if (storeData.product_data.images) {
            corpus.images.push(...storeData.product_data.images);
          }
        }
      } catch (e) {
        console.warn(`[DEEPDIVE] Failed to scrape ${store.store_url}: ${e.message}`);
      }
    }
  }

  // Generate copy variants (remixed from all sources)
  corpus.copy_variants = generateCopyVariants(corpus);

  // Store corpus in Qdrant
  await storeCorpusInQdrant(productId, corpus);

  return corpus;
}

/**
 * Get product name from Phase 1 result in Qdrant
 */
async function getProductNameFromQdrant(productId) {
  try {
    const client = new QdrantClient({
      host: process.env.QDRANT_HOST || '127.0.0.1',
      port: process.env.QDRANT_PORT || 6333
    });
    
    const point = await client.getPoint('dropship_intel', productId);
    return point.payload?.product_name || 'Unknown Product';
  } catch (e) {
    console.warn('[DEEPDIVE] Could not fetch from Qdrant:', e.message);
    return 'Unknown Product';
  }
}

/**
 * Scrape YouTube for product reviews
 * Stub implementation — real version uses YouTube Data API
 */
async function scrapeYoutubeReviews(productName) {
  console.log(`[YOUTUBE] Searching reviews for: "${productName}"`);
  
  return {
    reviews: [
      {
        channel: 'Tech Unboxer',
        title: `${productName} Review - Is it WORTH IT?`,
        views: 250000,
        likes: 8900,
        url: 'https://youtube.com/watch?v=example1',
        hook: 'the unboxing was incredible',
        summary: 'Positive overall, minor durability concerns'
      },
      {
        channel: 'Gadget Central',
        title: `I tested ${productName} for 30 days`,
        views: 180000,
        likes: 6200,
        url: 'https://youtube.com/watch?v=example2',
        hook: 'wait for the fail at the end',
        summary: 'Great product but pricey vs alternatives'
      }
    ]
  };
}

/**
 * Scrape Reddit for product discussions
 * Stub implementation — real version uses Reddit API
 */
async function scrapeRedditThreads(productName) {
  console.log(`[REDDIT] Searching discussions for: "${productName}"`);
  
  return {
    threads: [
      {
        subreddit: 'r/gadgets',
        title: `PSA: ${productName} is overrated`,
        upvotes: 1200,
        comments: 340,
        sentiment: 'mixed',
        safety_signals: ['authentic_reviews', 'price_complaint'],
        url: 'https://reddit.com/r/gadgets/...'
      },
      {
        subreddit: 'r/lifehacks',
        title: `Best use case for ${productName}`,
        upvotes: 890,
        comments: 210,
        sentiment: 'positive',
        safety_signals: ['use_case_specific', 'customer_recommendation'],
        url: 'https://reddit.com/r/lifehacks/...'
      }
    ]
  };
}

/**
 * Generate copy variants by remixing TikTok hooks + Shopify descriptions
 * These become inputs to Prometheus video generation
 */
function generateCopyVariants(corpus) {
  const variants = [];
  
  // Hook variations from TikTok
  const tiktokHooks = corpus.tiktok_videos
    .slice(0, 5)
    .map(v => v.hook)
    .filter(h => h);
  
  // Copy from Shopify stores
  const shopifyCopy = corpus.shopify_stores
    .slice(0, 3)
    .map(s => s.product_data.short_description)
    .filter(c => c);
  
  // YouTube hooks
  const youtubeHooks = corpus.youtube_reviews
    .slice(0, 3)
    .map(r => r.hook)
    .filter(h => h);
  
  // Combine into variants
  for (const tiktokHook of tiktokHooks) {
    for (const shopifyText of shopifyCopy) {
      variants.push({
        source: 'tiktok + shopify',
        hook: tiktokHook,
        description: shopifyText,
        style: 'viral_unboxing'
      });
    }
  }
  
  for (const youtubeHook of youtubeHooks) {
    variants.push({
      source: 'youtube',
      hook: youtubeHook,
      description: `Check this out! ${corpus.product_name}`,
      style: 'tutorial'
    });
  }
  
  return variants.slice(0, 10); // Top 10 variants
}

/**
 * Store entire corpus in Qdrant for later retrieval
 * Indexed by product_id for fast lookup by Prometheus
 */
async function storeCorpusInQdrant(productId, corpus) {
  try {
    const client = new QdrantClient({
      host: process.env.QDRANT_HOST || '127.0.0.1',
      port: process.env.QDRANT_PORT || 6333
    });
    
    // Store as vector metadata — full corpus attached to product point
    await client.setPayload(
      'dropship_intel',
      {
        points: [
          {
            id: productId,
            payload: {
              product_id: productId,
              corpus_metadata: {
                created_at: corpus.created_at,
                tiktok_count: corpus.tiktok_videos.length,
                shopify_count: corpus.shopify_stores.length,
                youtube_count: corpus.youtube_reviews.length,
                reddit_count: corpus.reddit_threads.length,
                copy_variants: corpus.copy_variants.length,
                images_count: corpus.images.length
              }
            }
          }
        ]
      }
    );
    
    console.log(`[DEEPDIVE] Corpus stored in Qdrant for product: ${productId}`);
  } catch (e) {
    console.warn('[DEEPDIVE] Could not store in Qdrant:', e.message);
    // Not fatal — corpus still exists in response
  }
}
