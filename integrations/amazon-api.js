/**
 * Amazon Product Advertising API Integration
 * 
 * Fetches:
 * - Product rank (by category)
 * - Price
 * - Number of reviews (and daily review velocity)
 * - Estimated monthly sales (calculated from rank + category)
 * - Supplier/ASIN mapping
 */

import axios from 'axios';
import crypto from 'crypto';
import { v4 as uuidv4 } from 'uuid';

export class AmazonAPI {
  constructor() {
    this.accessKeyId = process.env.AMAZON_ACCESS_KEY_ID;
    this.secretAccessKey = process.env.AMAZON_SECRET_ACCESS_KEY;
    this.partnerTag = process.env.AMAZON_PARTNER_TAG;
    this.host = 'webapi.amazon.com';
    this.baseUrl = 'https://api.amazon.com/onca/xml';
    
    if (!this.accessKeyId || !this.secretAccessKey || !this.partnerTag) {
      console.warn('[AMAZON] Missing API credentials in .env. API calls will fail.');
    }
  }

  /**
   * Search for products matching a query
   * @param {string} query - Search query (e.g., "led projection lamp")
   * @returns {Promise<Array>} Array of products with sales data
   */
  async searchProducts(query) {
    try {
      console.log(`[AMAZON] Searching for: "${query}"`);

      // For MVP: using ItemSearch operation
      // In production, should use newer SearchItems operation
      const params = {
        Service: 'AWSECommerceService',
        Operation: 'ItemSearch',
        SearchIndex: 'All',
        Keywords: query,
        ResponseGroup: 'Images,ItemAttributes,Offers,Reviews,EditorialReviews',
        AssociateTag: this.partnerTag,
        Timestamp: new Date().toISOString(),
        Version: '2013-08-01'
      };

      // Add AWS signature (required for API authentication)
      const canonicalQueryString = this.buildCanonicalQueryString(params);
      const signature = this.calculateSignature('GET', this.host, '/onca/xml', canonicalQueryString);
      
      const url = `${this.baseUrl}?${canonicalQueryString}&Signature=${encodeURIComponent(signature)}`;

      console.log(`[AMAZON] Making request to: ${url.substring(0, 100)}...`);
      
      const response = await axios.get(url, {
        timeout: 10000,
        headers: {
          'User-Agent': 'ShipStack Product Discovery / 1.0'
        }
      });

      // Parse XML response and extract product data
      const products = this.parseSearchResponse(response.data, query);
      
      console.log(`[AMAZON] Found ${products.length} products`);
      return products;
    } catch (error) {
      console.error('[AMAZON] API Error:', error.message);
      // Graceful fallback: return empty array instead of throwing
      return [];
    }
  }

  /**
   * Get detailed product information including rank
   * @param {string} asin - Amazon Standard Identification Number
   * @returns {Promise<Object>} Product details with rank estimate
   */
  async getProductDetails(asin) {
    try {
      const params = {
        Service: 'AWSECommerceService',
        Operation: 'ItemLookup',
        ItemId: asin,
        ResponseGroup: 'Large',
        AssociateTag: this.partnerTag,
        Timestamp: new Date().toISOString(),
        Version: '2013-08-01'
      };

      const canonicalQueryString = this.buildCanonicalQueryString(params);
      const signature = this.calculateSignature('GET', this.host, '/onca/xml', canonicalQueryString);
      
      const url = `${this.baseUrl}?${canonicalQueryString}&Signature=${encodeURIComponent(signature)}`;

      const response = await axios.get(url, {
        timeout: 10000,
        headers: {
          'User-Agent': 'ShipStack Product Discovery / 1.0'
        }
      });

      return this.parseItemLookupResponse(response.data);
    } catch (error) {
      console.error('[AMAZON] Item Lookup Error:', error.message);
      return null;
    }
  }

  /**
   * Build canonical query string for AWS signature
   */
  buildCanonicalQueryString(params) {
    const sorted = Object.keys(params)
      .sort()
      .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
      .join('&');
    
    return sorted;
  }

  /**
   * Calculate AWS Signature Version 2 (required for API auth)
   */
  calculateSignature(httpMethod, host, uri, canonicalQueryString) {
    const stringToSign = `${httpMethod}\n${host}\n${uri}\n${canonicalQueryString}`;
    
    const signature = crypto
      .createHmac('sha256', this.secretAccessKey)
      .update(stringToSign)
      .digest('base64');
    
    return signature;
  }

  /**
   * Parse ItemSearch response (XML)
   * Stub implementation — full version would parse actual Amazon XML
   */
  parseSearchResponse(xmlData, query) {
    // Stub: return mock data for MVP testing
    // In production, use xml2js or similar to parse actual response
    
    console.log('[AMAZON] Parsing search response (stub implementation)');
    
    return [
      {
        product_name: query.charAt(0).toUpperCase() + query.slice(1),
        asin: 'B0123456789',
        rank: Math.floor(Math.random() * 1000) + 50,
        estimated_monthly_sales: Math.floor(Math.random() * 5000) + 500,
        daily_review_count: Math.floor(Math.random() * 50) + 5,
        price: Math.random() * 100 + 10,
        rating: Math.random() * 2 + 3.5,
        supplier: 'Amazon FBA / Third-party'
      }
    ];
  }

  /**
   * Parse ItemLookup response (XML)
   */
  parseItemLookupResponse(xmlData) {
    // Stub: return mock data for MVP testing
    console.log('[AMAZON] Parsing item lookup response (stub implementation)');
    
    return {
      asin: 'B0123456789',
      rank: Math.floor(Math.random() * 1000) + 50,
      estimated_monthly_sales: Math.floor(Math.random() * 5000) + 500,
      daily_review_count: Math.floor(Math.random() * 50) + 5,
      price: Math.random() * 100 + 10,
      rating: Math.random() * 2 + 3.5
    };
  }

  /**
   * Estimate monthly sales from rank
   * Based on category average conversion rates
   */
  estimateSalesFromRank(rank, category = 'Electronics') {
    // Rough estimation: lower rank = more sales
    // Actual calculation would use category-specific benchmarks
    const baseSales = 10000;
    return Math.max(Math.floor(baseSales / (rank / 10)), 10);
  }

  /**
   * Calculate review velocity (reviews per day)
   */
  calculateReviewVelocity(totalReviews, daysSinceRelease) {
    if (daysSinceRelease === 0) return 0;
    return Math.round((totalReviews / daysSinceRelease) * 10) / 10;
  }
}
