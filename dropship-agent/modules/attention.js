// ============================================================
// MODULE: ATTENTION TRACKER
// Tracks and ranks platform CPMs, estimates CAC per platform,
// and routes products to the cheapest available attention
// ============================================================

import { readFile } from 'fs/promises';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import config from '../config.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

export class AttentionTracker {

  constructor(quinnClient) {
    this.ai = quinnClient;
    this.platformData = null;
  }

  async init() {
    const raw = await readFile(join(__dirname, '../data/platforms.json'), 'utf-8');
    this.platformData = JSON.parse(raw);
  }

  // ── Main: Get attention profile for a product ─────────────
  async getAttentionProfile(product) {
    const name = typeof product === 'string' ? product : product.query;
    if (!this.platformData) await this.init();

    const [rankings, organicStrategy] = await Promise.all([
      this.rankPlatformsByEfficiency(name),
      this.getOrganicOpportunity(name),
    ]);

    const cheapestPlatform = rankings[0];
    const bestOrganicChannel = organicStrategy.bestChannel;

    return {
      product: name,
      platformRankings: rankings,
      organicStrategy,
      cheapestPaidChannel: cheapestPlatform,
      bestOrganicChannel,
      estimatedBlendedCAC: this._estimateBlendedCAC(rankings, organicStrategy),
      attentionArbitrageOpportunity: this._findArbitrageGap(rankings),
      recommendedLaunchStack: this._buildLaunchStack(rankings, organicStrategy),
      timestamp: new Date().toISOString(),
    };
  }

  // ── Platform Efficiency Ranking ───────────────────────────
  async rankPlatformsByEfficiency(productName) {
    const prompt = `You are a paid media buyer and traffic arbitrage expert.

For the product: "${productName}"

Rank these platforms by CHEAPEST effective cost per acquisition (CAC) for this specific product.
Consider: buyer intent, creative match, audience fit, auction competition.

Platforms to rank: TikTok Organic, TikTok Spark Ads, Pinterest, Reddit Ads, Instagram, Facebook, YouTube Shorts, Google Shopping

Return a JSON array ranked from CHEAPEST to MOST EXPENSIVE CAC:
[
  {
    "platform": "<platform name>",
    "platformKey": "<one of: tiktok_organic|tiktok_spark|pinterest|reddit|instagram|facebook|youtube_shorts|google_shopping>",
    "estimatedCAC": <$ number or 0 for organic>,
    "estimatedCPM": <$ number>,
    "estimatedCPC": <$ number>,
    "fitScore": <1-10 — how well does this product fit this platform?>,
    "reasoning": "<one sentence>",
    "contentRequirements": "<what type of content works here>",
    "audienceMatch": "poor|fair|good|excellent"
  }
]`;

    const r = await this.ai.messages.create({
      model: config.quinn.model,
      max_tokens: 1200,
      messages: [{ role: 'user', content: prompt }],
    });

    const parsed = this._parseJSON(r.content[0].text, null);
    if (!parsed) return this._defaultPlatformRankings();

    // Merge with static benchmark data
    return parsed.map(p => ({
      ...p,
      benchmarkCPM: config.platforms[p.platformKey]?.cpm ?? p.estimatedCPM,
      benchmarkCPC: config.platforms[p.platformKey]?.cpc ?? p.estimatedCPC,
    }));
  }

  // ── Organic Traffic Opportunity ───────────────────────────
  async getOrganicOpportunity(productName) {
    const prompt = `You are an organic content and SEO strategist for e-commerce.

Evaluate organic (zero ad spend) traffic potential for: "${productName}"

Return JSON only (no markdown):
{
  "bestChannel": "tiktok|pinterest|instagram|youtube|reddit|google_seo",
  "organicPotential": <1-10>,
  "viralityCoefficient": <1-10 — how likely one post goes viral?>,
  "contentHalfLife": "hours|days|weeks|months|years",
  "pinInterestEvergreen": <true/false — will Pinterest traffic compound over time?>,
  "seoOpportunity": <1-10 — can this rank on Google organically?>,
  "redditCommunityFit": <1-10 — are there subreddits full of buyers?>,
  "estimatedOrganicCACRange": "<e.g. $0-5>",
  "timeToFirstOrganicSale": "<estimate: hours|days|weeks>",
  "topOrganicStrategies": [
    "<strategy 1>",
    "<strategy 2>",
    "<strategy 3>"
  ]
}`;

    const r = await this.ai.messages.create({
      model: config.quinn.model,
      max_tokens: 600,
      messages: [{ role: 'user', content: prompt }],
    });
    return this._parseJSON(r.content[0].text, {
      bestChannel: 'tiktok', organicPotential: 6, viralityCoefficient: 5,
      contentHalfLife: 'days', pinInterestEvergreen: false, seoOpportunity: 5,
      redditCommunityFit: 5, estimatedOrganicCACRange: '$5-20',
      timeToFirstOrganicSale: 'days',
      topOrganicStrategies: ['Short video', 'Before/after', 'Problem/solution'],
    });
  }

  // ── Traffic Arbitrage Gap Detection ──────────────────────
  _findArbitrageGap(rankings) {
    const cheapest = rankings.slice(0, 2);
    const most_expensive = rankings.slice(-2);
    const cheapestAvgCAC = cheapest.reduce((a, p) => a + (p.estimatedCAC || 0), 0) / cheapest.length;
    const expensiveAvgCAC = most_expensive.reduce((a, p) => a + (p.estimatedCAC || 0), 0) / most_expensive.length;
    const gap = expensiveAvgCAC - cheapestAvgCAC;

    return {
      gapUSD: Math.round(gap),
      cheapestChannels: cheapest.map(p => p.platform),
      mostExpensiveChannels: most_expensive.map(p => p.platform),
      arbitrageStrength: gap > 30 ? 'STRONG' : gap > 15 ? 'MODERATE' : 'WEAK',
      recommendation: gap > 20
        ? `Significant arbitrage: save ~$${Math.round(gap)} CAC by using ${cheapest[0].platform} over ${most_expensive[0].platform}`
        : 'Platform costs are relatively uniform for this product',
    };
  }

  // ── Blended CAC Estimate ──────────────────────────────────
  _estimateBlendedCAC(rankings, organicStrategy) {
    // Assume 60% organic, 40% paid when organic potential is good
    const organicShare = organicStrategy.organicPotential > 6 ? 0.60 : 0.30;
    const paidShare = 1 - organicShare;
    const paidCAC = rankings.filter(p => p.estimatedCAC > 0)[0]?.estimatedCAC || 20;
    const blended = paidCAC * paidShare; // organic portion costs ~$0
    return {
      blendedCAC: Math.round(blended * 10) / 10,
      organicShare: `${Math.round(organicShare * 100)}%`,
      paidShare: `${Math.round(paidShare * 100)}%`,
      cheapestPaidCAC: paidCAC,
    };
  }

  // ── Launch Stack Builder ──────────────────────────────────
  _buildLaunchStack(rankings, organicStrategy) {
    const bestPaid = rankings.filter(p => p.estimatedCAC > 0).slice(0, 2);
    return {
      phase1: {
        label: 'Week 1-4: Organic Validation',
        channel: organicStrategy.bestChannel,
        cost: '$0',
        goal: 'Validate demand before spending on ads',
        actions: organicStrategy.topOrganicStrategies,
      },
      phase2: {
        label: 'Week 4-8: Amplify Winners',
        channels: bestPaid.map(p => p.platform),
        budget: '$10-50/day',
        goal: 'Turn winning organic content into paid Spark Ads / promoted posts',
        actions: ['Boost top organic posts', 'Test retargeting pixel audiences'],
      },
      phase3: {
        label: 'Week 8+: Scale Arbitrage',
        strategy: 'Shift all budget to lowest-CAC channel',
        goal: 'Maximize units at minimum CAC',
        kpi: `Target blended CAC under $${Math.round(rankings[0]?.estimatedCAC * 1.5 || 20)}`,
      },
    };
  }

  _defaultPlatformRankings() {
    return Object.entries(config.platforms).map(([key, p]) => ({
      platform: p.label,
      platformKey: key,
      estimatedCAC: p.cpm > 0 ? p.cpm * 3 : 0,
      estimatedCPM: p.cpm,
      estimatedCPC: p.cpc,
      fitScore: 5,
      reasoning: 'Default benchmark',
      contentRequirements: 'Standard creative',
      audienceMatch: 'fair',
      benchmarkCPM: p.cpm,
      benchmarkCPC: p.cpc,
    })).sort((a, b) => a.estimatedCAC - b.estimatedCAC);
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
