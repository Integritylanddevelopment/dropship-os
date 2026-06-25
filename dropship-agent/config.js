// ============================================================
// DROPSHIP INTELLIGENCE AGENT — CONFIGURATION
// ============================================================

export const config = {

  // ── API Keys ──────────────────────────────────────────────
  // Set these as environment variables or replace directly
  quinn: {
    bridgeUrl: process.env.QUINN_BRIDGE_URL || 'http://127.0.0.1:8765',
    model: process.env.SHIPSTACK_MODEL || 'qwen2.5:7b',
    maxTokens: 8096,
  },

  serpApi: {
    // SerpAPI for real Google/TikTok/Amazon search results
    // https://serpapi.com — free tier: 100 searches/month
    apiKey: process.env.SERP_API_KEY || 'YOUR_SERP_API_KEY',
    enabled: !!process.env.SERP_API_KEY,
  },

  // ── Agent Behavior ────────────────────────────────────────
  agent: {
    maxConcurrentResearch: 3,       // parallel research threads
    scanIntervalMinutes: 60,        // how often monitor mode rescans
    topOpportunitiesCount: 10,      // how many products to return per scan
    minOpportunityScore: 6.0,       // minimum score to include in report
    autoSaveReports: true,
    reportsDir: './reports',
  },

  // ── Scoring Weights ───────────────────────────────────────
  scoring: {
    demand:       0.25,   // 25% weight
    competition:  0.20,   // 20% — INVERSE (low competition = high score)
    attentionCost: 0.20,  // 20% — INVERSE (cheap attention = high score)
    margin:       0.20,   // 20%
    launchSpeed:  0.15,   // 15%
  },

  // ── Opportunity Thresholds ────────────────────────────────
  thresholds: {
    minGrossMarginPct: 50,          // reject anything under 50% GM
    maxLandedCostUSD:  35,          // cap on sourcing cost for low-risk entry
    minSellingPriceUSD: 15,         // minimum viable AOV
    maxReturnRiskScore: 6,          // 1-10 scale; reject above 6
    maxCompetitionScore: 7,         // 1-10 scale; reject above 7
  },

  // ── Platform CPM Benchmarks (April 2026) ─────────────────
  platforms: {
    tiktok_organic: { cpm: 0,    cpc: 0,    label: 'TikTok Organic', tier: 'free' },
    tiktok_paid:    { cpm: 6,    cpc: 0.80, label: 'TikTok Paid Ads', tier: 'paid' },
    tiktok_spark:   { cpm: 4,    cpc: 0.60, label: 'TikTok Spark Ads', tier: 'paid' },
    pinterest:      { cpm: 3,    cpc: 0.50, label: 'Pinterest', tier: 'paid' },
    reddit:         { cpm: 2,    cpc: 0.80, label: 'Reddit Ads', tier: 'paid' },
    instagram:      { cpm: 9,    cpc: 1.20, label: 'Instagram', tier: 'paid' },
    facebook:       { cpm: 10,   cpc: 1.50, label: 'Facebook', tier: 'paid' },
    google_shopping:{ cpm: 15,   cpc: 2.50, label: 'Google Shopping', tier: 'paid' },
    youtube_shorts: { cpm: 5,    cpc: 0.90, label: 'YouTube Shorts', tier: 'paid' },
  },

  // ── Product Category Research Seeds ──────────────────────
  researchSeeds: [
    'health wellness gadgets trending 2026',
    'home decor aesthetic products viral TikTok 2026',
    'pet accessories low competition high margin',
    'beauty skincare tool dropship winning product',
    'kitchen gadget problem solving viral',
    'sleep anxiety wellness product trending',
    'fitness recovery tool home use',
    'eco sustainable home products',
    'tech gadget gift impulse buy',
    'self care personal wellness tool',
  ],

  // ── Content Strategy Templates ────────────────────────────
  contentHooks: {
    problemSolution: 'You have [PROBLEM]. This [PRODUCT] fixes it in [TIME].',
    beforeAfter:     'Before: [STATE]. After [DAYS] days with [PRODUCT]: [RESULT].',
    socialProof:     '[NUMBER] people bought this. Here is why.',
    curiosity:       'I cannot believe this actually works.',
    urgency:         'This [PRODUCT] keeps selling out. Here is why.',
    educational:     'Did you know [FACT]? This is why [PRODUCT] exists.',
  },

  // ── Virality Signals ──────────────────────────────────────
  viralitySignals: {
    highScore: ['before/after', 'satisfying', '3-second wow', 'problem solved', 'transformation'],
    medScore:  ['unboxing', 'review', 'how-to', 'comparison'],
    lowScore:  ['talking head', 'logo reveal', 'static image'],
  },

  // ── Search Behavior ───────────────────────────────────────
  search: {
    delayMs: 1200,    // polite delay between searches
    maxRetries: 2,
  },

  // ── Dashboard / Server ────────────────────────────────────
  server: {
    port: process.env.PORT || 3737,
    host: 'localhost',
  },

};

// ── Path helpers ───────────────────────────────────────────────
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
const __dirname = dirname(fileURLToPath(import.meta.url));

config.paths = {
  root:      __dirname,
  reports:   resolve(__dirname, 'reports'),
  data:      resolve(__dirname, 'data'),
  dashboard: resolve(__dirname, 'dashboard'),
};

export function validateConfig() {
  const errors = [];
  if (!config.quinn.bridgeUrl) {
    errors.push('Quinn bridge URL is not set. Start Quinn bridge at http://127.0.0.1:8765.');
  }
  return errors;
}

export default config;
