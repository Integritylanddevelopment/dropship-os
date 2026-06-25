// ============================================================
// MODULE: RESEARCHER
// Finds trending products, validates demand signals,
// searches for market opportunities using web data
// ============================================================

import axios from 'axios';
import config from '../config.js';

export class Researcher {

  constructor(quinnClient) {
    this.ai = quinnClient;
    this.serpApiBase = 'https://serpapi.com/search';
  }

  // ── Main Entry: Research a product keyword ────────────────
  async researchProduct(query) {
    console.log(`  [Researcher] Analyzing: "${query}"`);
    const [trendData, marketData, socialData] = await Promise.all([
      this.analyzeTrend(query),
      this.estimateMarketDemand(query),
      this.estimateSocialEngagement(query),
    ]);
    return { query, trendData, marketData, socialData, timestamp: new Date().toISOString() };
  }

  // ── Trend Analysis ────────────────────────────────────────
  async analyzeTrend(keyword) {
    if (config.serpApi.enabled) {
      return await this._serpTrendSearch(keyword);
    }
    // AI-based estimation when no live API
    return await this._aiEstimateTrend(keyword);
  }

  async _aiEstimateTrend(keyword) {
    const prompt = `You are a market research expert specializing in e-commerce trends.

Analyze this product keyword for dropshipping viability: "${keyword}"

Return a JSON object with these exact fields (no markdown, pure JSON):
{
  "trendDirection": "rising|stable|declining",
  "trendVelocity": <1-10 score where 10 = fastest growing>,
  "seasonality": "evergreen|seasonal|peak_now",
  "peakMonths": ["month names if seasonal, else null"],
  "googleTrendsEstimate": <estimated relative search score 0-100>,
  "searchVolumeTier": "very_high|high|medium|low",
  "yearOverYearGrowthPct": <estimated % growth>,
  "reasoning": "<one sentence>"
}`;

    const response = await this.ai.messages.create({
      model: config.quinn.model,
      max_tokens: 512,
      messages: [{ role: 'user', content: prompt }],
    });
    return this._parseJSON(response.content[0].text, {
      trendDirection: 'stable', trendVelocity: 5, seasonality: 'evergreen',
      peakMonths: [], googleTrendsEstimate: 50, searchVolumeTier: 'medium',
      yearOverYearGrowthPct: 10, reasoning: 'Estimated',
    });
  }

  // ── Market Demand Estimation ──────────────────────────────
  async estimateMarketDemand(keyword) {
    const prompt = `You are a dropshipping market analyst.

Estimate buyer demand for this product: "${keyword}"

Return JSON only (no markdown):
{
  "monthlySearchVolume": <estimated number>,
  "buyerIntentScore": <1-10>,
  "impulseBuyPotential": <1-10>,
  "repeatPurchasePotential": <1-10>,
  "problemSolvingStrength": <1-10 where 10 = extreme pain point>,
  "giftPotential": <1-10>,
  "targetDemographics": ["list of buyer segments"],
  "priceElasticity": "low|medium|high",
  "demandType": "impulse|considered|utility|luxury",
  "overallDemandScore": <1-10>
}`;

    const response = await this.ai.messages.create({
      model: config.quinn.model,
      max_tokens: 512,
      messages: [{ role: 'user', content: prompt }],
    });
    return this._parseJSON(response.content[0].text, {
      monthlySearchVolume: 10000, buyerIntentScore: 5, impulseBuyPotential: 5,
      repeatPurchasePotential: 5, problemSolvingStrength: 5, giftPotential: 5,
      targetDemographics: ['general consumers'], priceElasticity: 'medium',
      demandType: 'utility', overallDemandScore: 5,
    });
  }

  // ── Social Engagement Estimation ─────────────────────────
  async estimateSocialEngagement(keyword) {
    const prompt = `You are a social media marketing expert for e-commerce.

Evaluate the social media content potential for: "${keyword}"

Return JSON only (no markdown):
{
  "tiktokViralPotential": <1-10>,
  "contentFormatsBestSuited": ["list of formats like before-after, unboxing, etc"],
  "hookStrengthIn3Seconds": <1-10 — can it wow someone in 3 seconds?>,
  "ugcPotential": <1-10 — will customers create content naturally?>,
  "influencerFit": <1-10 — do micro-influencers naturally use this?>,
  "hashtagyNiches": ["relevant TikTok/Instagram communities"],
  "estimatedOrganic CAC": "<low $0-5 | medium $5-20 | high $20+>",
  "bestPlatforms": ["ranked list of platforms for this product"],
  "contentAngle": "<best content angle in one sentence>",
  "overallSocialScore": <1-10>
}`;

    const response = await this.ai.messages.create({
      model: config.quinn.model,
      max_tokens: 600,
      messages: [{ role: 'user', content: prompt }],
    });
    return this._parseJSON(response.content[0].text, {
      tiktokViralPotential: 5, contentFormatsBestSuited: ['video'],
      hookStrengthIn3Seconds: 5, ugcPotential: 5, influencerFit: 5,
      hashtagNiches: [], estimatedOrganicCAC: 'medium $5-20',
      bestPlatforms: ['tiktok'], contentAngle: 'Problem/solution',
      overallSocialScore: 5,
    });
  }

  // ── Batch Research Multiple Seeds ────────────────────────
  async batchResearch(seeds, limit = 3) {
    const pLimit = (await import('p-limit')).default;
    const limiter = pLimit(limit);
    const results = await Promise.all(
      seeds.map(seed => limiter(() => this.researchProduct(seed)))
    );
    return results;
  }

  // ── SerpAPI Integration ───────────────────────────────────
  async _serpTrendSearch(keyword) {
    try {
      const response = await axios.get(this.serpApiBase, {
        params: {
          q: keyword,
          api_key: config.serpApi.apiKey,
          engine: 'google_trends',
          data_type: 'TIMESERIES',
        },
        timeout: 10000,
      });
      const data = response.data;
      return {
        trendDirection: this._deriveTrendDirection(data),
        trendVelocity: 7,
        seasonality: 'evergreen',
        peakMonths: [],
        googleTrendsEstimate: data?.interest_over_time?.timeline_data?.slice(-1)[0]?.values?.[0]?.value || 50,
        searchVolumeTier: 'medium',
        yearOverYearGrowthPct: 15,
        reasoning: 'Live SerpAPI data',
      };
    } catch {
      return await this._aiEstimateTrend(keyword);
    }
  }

  _deriveTrendDirection(serpData) {
    const timeline = serpData?.interest_over_time?.timeline_data || [];
    if (timeline.length < 4) return 'stable';
    const recent = timeline.slice(-4).map(d => d.values?.[0]?.value || 0);
    const avg = recent.reduce((a, b) => a + b, 0) / recent.length;
    const first = recent[0], last = recent[recent.length - 1];
    if (last > first * 1.15) return 'rising';
    if (last < first * 0.85) return 'declining';
    return 'stable';
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
