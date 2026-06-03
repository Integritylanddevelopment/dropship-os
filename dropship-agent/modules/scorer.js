// ============================================================
// UNIFIED SCORING ENGINE
// ============================================================

import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

let scoringMatrix;
try {
  scoringMatrix = JSON.parse(
    readFileSync(resolve(__dirname, '../data/scoring-matrix.json'), 'utf-8')
  );
} catch {
  scoringMatrix = { weights: { demand: 0.25, competition: 0.20, attentionCost: 0.20, margin: 0.20, launchSpeed: 0.15 } };
}

// ── Score a single product object ───────────────────────────
export function scoreProduct(product) {
  const w = scoringMatrix.weights;

  // Normalize all subscores to 0-10
  const demand      = clamp(product.demandScore      ?? 5, 0, 10);
  const competition = clamp(10 - (product.competitionScore ?? 5), 0, 10); // INVERTED
  const attention   = clamp(10 - (product.attentionCostScore ?? 5), 0, 10); // INVERTED
  const margin      = clamp(product.marginScore      ?? 5, 0, 10);
  const launch      = clamp(product.launchSpeedScore ?? 5, 0, 10);

  const overall = (
    demand      * w.demand       +
    competition * w.competition  +
    attention   * w.attentionCost +
    margin      * w.margin       +
    launch      * w.launchSpeed
  );

  return {
    ...product,
    scores: { demand, competition, attention, margin, launch },
    overallScore: Math.round(overall * 10) / 10,
    scoreLabel: getScoreLabel(overall),
    recommendation: getProductRecommendation(overall, product),
  };
}

// ── Score a single channel object ───────────────────────────
export function scoreChannel(channel) {
  const attentionCost  = clamp(10 - (channel.cpmScore ?? 5), 0, 10); // INVERTED
  const audienceQuality = clamp(channel.audienceQualityScore ?? 5, 0, 10);
  const competition    = clamp(10 - (channel.competitionScore ?? 5), 0, 10); // INVERTED
  const scalability    = clamp(channel.scalabilityScore ?? 5, 0, 10);
  const conversion     = clamp(channel.conversionScore ?? 5, 0, 10);

  const overall = (
    attentionCost   * 0.30 +
    audienceQuality * 0.25 +
    competition     * 0.20 +
    scalability     * 0.15 +
    conversion      * 0.10
  );

  return {
    ...channel,
    scores: { attentionCost, audienceQuality, competition, scalability, conversion },
    overallScore: Math.round(overall * 10) / 10,
    scoreLabel: getScoreLabel(overall),
  };
}

// ── Score a product-channel match ───────────────────────────
export function scoreMatch(product, channel) {
  const audienceAlignment = estimateAudienceAlignment(product, channel);
  const marginAfterCAC    = estimateMarginAfterCAC(product, channel);
  const contentFit        = estimateContentFit(product, channel);
  const testSpeed         = estimateTestSpeed(product, channel);

  const overall = (
    audienceAlignment * 0.30 +
    marginAfterCAC    * 0.30 +
    contentFit        * 0.25 +
    testSpeed         * 0.15
  );

  const cac = channel.avgCac || estimateCAC(channel);
  const netMargin = (product.sellingPrice || 30) - (product.landedCost || 12) - cac;
  const netMarginPct = Math.round((netMargin / (product.sellingPrice || 30)) * 100);

  return {
    product: product.name,
    channel: channel.name,
    productScore:   product.overallScore,
    channelScore:   channel.overallScore,
    matchScore:     Math.round(overall * 10) / 10,
    estimatedCAC:   `$${cac.toFixed(0)}`,
    estimatedNetMargin: `${netMarginPct}%`,
    whyItWorks:     buildMatchRationale(product, channel, overall),
    scores: { audienceAlignment, marginAfterCAC, contentFit, testSpeed },
  };
}

// ── Batch score arrays ───────────────────────────────────────
export function scoreProducts(products) {
  return products.map(scoreProduct).sort((a, b) => b.overallScore - a.overallScore);
}

export function scoreChannels(channels) {
  return channels.map(scoreChannel).sort((a, b) => b.overallScore - a.overallScore);
}

export function scoreMatches(products, channels) {
  const matches = [];
  for (const product of products) {
    for (const channel of channels) {
      matches.push(scoreMatch(product, channel));
    }
  }
  return matches.sort((a, b) => b.matchScore - a.matchScore);
}

// ── Label winners across the full report ────────────────────
export function labelWinners(products, channels, matches) {
  const labels = {};

  // Product winners
  const sorted = [...products].sort((a, b) => b.overallScore - a.overallScore);
  labels.bestOverallProduct    = sorted[0];
  labels.bestMarginProduct     = [...products].sort((a, b) => b.marginScore - a.marginScore)[0];
  labels.bestLowCompProduct    = [...products].sort((a, b) => a.competitionScore - b.competitionScore)[0];
  labels.bestFastLaunch        = [...products].sort((a, b) => b.launchSpeedScore - a.launchSpeedScore)[0];

  // Channel winners
  labels.bestCheapAttention    = [...channels].sort((a, b) => a.cpmScore - b.cpmScore)[0];
  labels.bestOrganicChannel    = [...channels].filter(c => c.isPaidOnly !== true).sort((a, b) => b.overallScore - a.overallScore)[0];
  labels.bestPaidChannel       = [...channels].filter(c => c.hasPaid).sort((a, b) => b.overallScore - a.overallScore)[0];
  labels.bestScaleChannel      = [...channels].sort((a, b) => b.scalabilityScore - a.scalabilityScore)[0];
  labels.bestHighIntentChannel = [...channels].sort((a, b) => b.audienceQualityScore - a.audienceQualityScore)[0];

  // Match winners
  labels.bestOverallMatch      = matches[0];
  labels.bestMarginMatch       = [...matches].sort((a, b) => parseFloat(b.estimatedNetMargin) - parseFloat(a.estimatedNetMargin))[0];

  return labels;
}

// ── Helpers ──────────────────────────────────────────────────
function clamp(val, min, max) {
  return Math.min(max, Math.max(min, Number(val) || 0));
}

function getScoreLabel(score) {
  if (score >= 9.0) return 'EXCEPTIONAL';
  if (score >= 8.0) return 'STRONG';
  if (score >= 7.0) return 'GOOD';
  if (score >= 6.0) return 'MODERATE';
  if (score >= 5.0) return 'WEAK';
  return 'AVOID';
}

function getProductRecommendation(score, product) {
  if (score >= 8.5) return `Launch ${product.name} immediately. Strong fundamentals across all dimensions.`;
  if (score >= 7.5) return `Test ${product.name} with a small ad budget ($50-150). High potential.`;
  if (score >= 6.5) return `Monitor ${product.name}. Worth a low-cost organic test before paid spend.`;
  return `Skip ${product.name} for now. Watch for improvements in competition or margin.`;
}

function estimateAudienceAlignment(product, channel) {
  const productAudience = (product.targetBuyer || '').toLowerCase();
  const channelAudience = (channel.audienceAge || '').toLowerCase();
  const channelBestFor  = (channel.bestFor || []).join(' ').toLowerCase();
  const productCategory = (product.category || '').toLowerCase();

  let score = 5;
  if (channelBestFor.includes(productCategory) || channelBestFor.includes('visual products')) score += 2;
  if (productAudience.includes('18') || productAudience.includes('25')) score += 1;
  if (channelAudience.includes('18') || channelAudience.includes('25')) score += 1;
  if (channel.name?.toLowerCase().includes('tiktok') && product.impulseBuy) score += 1;

  return clamp(score, 0, 10);
}

function estimateMarginAfterCAC(product, channel) {
  const sellPrice  = product.sellingPrice  || 30;
  const landedCost = product.landedCost    || 12;
  const cac        = channel.avgCac        || estimateCAC(channel);
  const netMargin  = sellPrice - landedCost - cac;
  const netPct     = (netMargin / sellPrice) * 100;

  if (netPct >= 40) return 9;
  if (netPct >= 30) return 8;
  if (netPct >= 20) return 6;
  if (netPct >= 10) return 4;
  return 2;
}

function estimateContentFit(product, channel) {
  const formats   = (channel.contentFormats || []).join(' ').toLowerCase();
  const hook      = (product.visualHookStrength || 5);
  const impulse   = product.impulseBuy ? 1 : 0;

  let score = hook;
  if (formats.includes('video') && product.videoFriendly) score += 1;
  if (formats.includes('static') && !product.videoFriendly) score += 1;
  score += impulse;

  return clamp(score, 0, 10);
}

function estimateTestSpeed(product, channel) {
  const launch   = product.launchSpeedScore || 5;
  const testCost = (channel.cpm || 10) < 5 ? 9 : (channel.cpm || 10) < 10 ? 7 : 5;
  return clamp((launch + testCost) / 2, 0, 10);
}

function estimateCAC(channel) {
  if (channel.cpc && channel.cpc > 0) return channel.cpc * 8; // assume 1/8 conversion
  if (channel.cpm && channel.cpm > 0) return channel.cpm * 1.5;
  return 15;
}

function buildMatchRationale(product, channel, score) {
  const parts = [];
  if (score >= 8) parts.push(`Exceptional fit between ${product.name} and ${channel.name}`);
  else if (score >= 7) parts.push(`Strong potential for ${product.name} on ${channel.name}`);
  else parts.push(`Moderate match for ${product.name} via ${channel.name}`);

  if (channel.cpm === 0) parts.push('Zero paid media cost — pure organic reach available');
  else if ((channel.cpm || 10) < 5) parts.push(`Very cheap CPM ($${channel.cpm}) lowers customer acquisition cost significantly`);

  if (product.visualHookStrength >= 8) parts.push('Product has a strong 3-second visual hook that performs well in feed formats');
  if (product.impulseBuy) parts.push('Impulse purchase potential aligns with fast-scroll platforms');

  return parts.join('. ') + '.';
}
