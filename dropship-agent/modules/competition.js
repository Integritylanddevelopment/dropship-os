// ============================================================
// MODULE: COMPETITION ANALYZER
// Measures seller saturation, ad density, listing quality,
// brand dominance, and market efficiency gaps
// ============================================================

import config from '../config.js';

export class CompetitionAnalyzer {

  constructor(quinnClient) {
    this.ai = quinnClient;
  }

  // ── Main: Full Competition Analysis ──────────────────────
  async analyze(product) {
    const name = typeof product === 'string' ? product : product.query;
    console.log(`  [Competition] Analyzing: "${name}"`);

    const [saturation, adLandscape, brandLandscape] = await Promise.all([
      this.analyzeSaturation(name),
      this.analyzeAdLandscape(name),
      this.analyzeBrandLandscape(name),
    ]);

    const overallScore = this._computeCompetitionScore(saturation, adLandscape, brandLandscape);

    return {
      product: name,
      saturation,
      adLandscape,
      brandLandscape,
      overallScore,       // 1-10: 10 = most competitive (bad), 1 = least (good for entry)
      opportunityGap: this._identifyGaps(saturation, adLandscape, brandLandscape),
      timestamp: new Date().toISOString(),
    };
  }

  // ── Saturation Analysis ───────────────────────────────────
  async analyzeSaturation(productName) {
    const prompt = `You are a competitive intelligence analyst for dropshipping.

Analyze seller saturation for: "${productName}"

Consider:
- How many sellers are actively selling this on Amazon, Shopify, TikTok Shop, eBay
- How crowded the Facebook/TikTok ad space is for this product
- Whether the niche is still inefficient (price gaps, weak listings, poor content)
- Whether there are clear opportunities for differentiation

Return JSON only (no markdown):
{
  "estimatedActiveSellerCount": <number>,
  "amazonListingCount": <estimated number>,
  "shopifyStoreCount": <estimated number>,
  "tiktokShopSellerCount": <estimated number>,
  "saturationLevel": "very_low|low|medium|high|very_high",
  "saturationScore": <1-10 where 10 = most saturated>,
  "listingQualityOfCompetitors": "poor|average|strong",
  "listingQualityScore": <1-10 where 10 = competitors have excellent listings>,
  "weaknessesInExistingListings": ["list of gaps you can exploit"],
  "priceRangeInMarket": { "low": <$>, "mid": <$>, "high": <$> },
  "dominantPricePoint": <$>
}`;

    const r = await this.ai.messages.create({
      model: config.quinn.model,
      max_tokens: 600,
      messages: [{ role: 'user', content: prompt }],
    });
    return this._parseJSON(r.content[0].text, {
      estimatedActiveSellerCount: 500, amazonListingCount: 200,
      shopifyStoreCount: 100, tiktokShopSellerCount: 50,
      saturationLevel: 'medium', saturationScore: 5,
      listingQualityOfCompetitors: 'average', listingQualityScore: 5,
      weaknessesInExistingListings: ['Generic photos', 'Poor copywriting'],
      priceRangeInMarket: { low: 15, mid: 35, high: 80 }, dominantPricePoint: 35,
    });
  }

  // ── Ad Landscape Analysis ─────────────────────────────────
  async analyzeAdLandscape(productName) {
    const prompt = `You are a paid advertising competitive analyst.

Evaluate the paid advertising landscape for: "${productName}"

Return JSON only (no markdown):
{
  "adDensity": "sparse|light|moderate|heavy|saturated",
  "adDensityScore": <1-10 where 10 = most ad-saturated>,
  "estimatedCompetitorAdSpend": "low <$1k/mo | medium $1k-10k/mo | high $10k-100k/mo | very_high $100k+/mo",
  "creativeExhaustion": <1-10 where 10 = same creative being run by everyone>,
  "auctionEfficiency": "inefficient|normal|competitive|auction_war",
  "estimatedCPMRange": { "low": <$>, "high": <$> },
  "estimatedCPCRange": { "low": <$>, "high": <$> },
  "bestAdAnglesNotYetUsed": ["angles competitors are missing"],
  "adPlatformsWithMostCompetition": ["ranked list"],
  "adPlatformsWithLeastCompetition": ["ranked list"]
}`;

    const r = await this.ai.messages.create({
      model: config.quinn.model,
      max_tokens: 600,
      messages: [{ role: 'user', content: prompt }],
    });
    return this._parseJSON(r.content[0].text, {
      adDensity: 'moderate', adDensityScore: 5,
      estimatedCompetitorAdSpend: 'medium $1k-10k/mo',
      creativeExhaustion: 5, auctionEfficiency: 'normal',
      estimatedCPMRange: { low: 4, high: 12 },
      estimatedCPCRange: { low: 0.5, high: 2.0 },
      bestAdAnglesNotYetUsed: ['UGC testimonial', 'Educational hook'],
      adPlatformsWithMostCompetition: ['facebook'],
      adPlatformsWithLeastCompetition: ['pinterest', 'reddit'],
    });
  }

  // ── Brand Landscape Analysis ──────────────────────────────
  async analyzeBrandLandscape(productName) {
    const prompt = `You are a brand strategy analyst for e-commerce.

Evaluate brand dominance in the market for: "${productName}"

Return JSON only (no markdown):
{
  "majorBrandsPresent": ["list any well-known brands in this space"],
  "brandDominanceLevel": "none|weak|moderate|strong|dominant",
  "brandDominanceScore": <1-10 where 10 = Amazon/Nike/Apple owns this space>,
  "privateLabelOpportunity": <1-10 where 10 = huge white-label opportunity>,
  "brandLoyaltyStrength": "low|medium|high",
  "commoditizationRisk": <1-10 where 10 = pure commodity with zero differentiation>,
  "differentiationAngles": ["ways to differentiate from existing brands"],
  "patentOrIPRisk": "low|medium|high",
  "estimatedMarketGap": "<describe the biggest gap in the market in one sentence>"
}`;

    const r = await this.ai.messages.create({
      model: config.quinn.model,
      max_tokens: 600,
      messages: [{ role: 'user', content: prompt }],
    });
    return this._parseJSON(r.content[0].text, {
      majorBrandsPresent: [], brandDominanceLevel: 'moderate', brandDominanceScore: 4,
      privateLabelOpportunity: 7, brandLoyaltyStrength: 'low',
      commoditizationRisk: 4, differentiationAngles: ['Better branding', 'Bundle offers'],
      patentOrIPRisk: 'low', estimatedMarketGap: 'Mid-price tier underserved',
    });
  }

  // ── Opportunity Gap Identifier ────────────────────────────
  _identifyGaps(saturation, adLandscape, brandLandscape) {
    const gaps = [];
    if (saturation.saturationScore < 5) gaps.push('Low seller count — first-mover advantage available');
    if (saturation.listingQualityScore < 5) gaps.push('Weak competitor listings — strong creative will dominate');
    if (adLandscape.adDensityScore < 4) gaps.push('Underserved ad auctions — cheap traffic available');
    if (adLandscape.creativeExhaustion < 4) gaps.push('Creative landscape fresh — new angles untested');
    if (brandLandscape.brandDominanceScore < 4) gaps.push('No dominant brand — whitespace for private label');
    if (brandLandscape.privateLabelOpportunity > 7) gaps.push('Strong white-label/OEM opportunity');
    if (adLandscape.adPlatformsWithLeastCompetition.length > 0) {
      gaps.push(`Low competition on: ${adLandscape.adPlatformsWithLeastCompetition.join(', ')}`);
    }
    return gaps.length > 0 ? gaps : ['Market appears competitive — differentiation required'];
  }

  // ── Score Calculator ──────────────────────────────────────
  _computeCompetitionScore(saturation, adLandscape, brandLandscape) {
    // Higher score = more competitive = WORSE for entry
    const raw = (
      saturation.saturationScore * 0.40 +
      adLandscape.adDensityScore * 0.35 +
      brandLandscape.brandDominanceScore * 0.25
    );
    return Math.round(raw * 10) / 10;
  }

  _parseJSON(text, fallback) {
    try {
      const cleaned = text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
      return JSON.parse(cleaned);
    } catch {
      return fallback;
    }
  }
}
