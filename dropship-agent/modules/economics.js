// ============================================================
// MODULE: ECONOMICS CALCULATOR
// Calculates unit economics: COGS, shipping, margins,
// CAC tolerance, break-even, LTV, and profit scenarios
// ============================================================

import config from '../config.js';

export class EconomicsCalculator {

  constructor(quinnClient) {
    this.ai = quinnClient;
  }

  // ── Main: Full Unit Economics Analysis ───────────────────
  async analyze(productName, overrides = {}) {
    console.log(`  [Economics] Calculating: "${productName}"`);

    const baseline = await this._estimateBaseline(productName);
    const merged = { ...baseline, ...overrides };

    return {
      product: productName,
      baseline: merged,
      scenarios: this._buildScenarios(merged),
      breakEven: this._calculateBreakEven(merged),
      cacThresholds: this._calculateCACThresholds(merged),
      marginAnalysis: this._analyzeMargin(merged),
      verdict: this._renderVerdict(merged),
      timestamp: new Date().toISOString(),
    };
  }

  // ── AI-Based Baseline Estimation ─────────────────────────
  async _estimateBaseline(productName) {
    const prompt = `You are a dropshipping financial analyst and sourcing expert.

Estimate realistic unit economics for dropshipping: "${productName}"

Assume standard China-to-US supply chain via AliExpress/CJ Dropshipping.
Be conservative and realistic — not optimistic.

Return JSON only (no markdown):
{
  "productCostUSD": <supplier/landed cost per unit>,
  "shippingCostUSD": <cost to ship to customer, estimate ePacket or similar>,
  "packagingCostUSD": <custom packaging if applicable, else 0>,
  "totalCOGS": <sum of above>,
  "suggestedRetailPrice": <realistic market selling price>,
  "priceFloor": <minimum price market will bear>,
  "priceCeiling": <maximum price without resistance>,
  "grossMarginUSD": <retail price minus COGS>,
  "grossMarginPct": <percentage>,
  "paymentProcessingFeeUSD": <estimate 2.9% + $0.30 of retail>,
  "netMarginAfterFeesUSD": <after payment processing>,
  "returnRiskPct": <estimated return rate %>,
  "chargebackRiskScore": <1-10>,
  "fragilityScore": <1-10 — how likely to break in shipping>,
  "aovPotential": <estimated average order value with potential upsells>,
  "ltvMultiple": <expected repeat purchases in year 1, e.g. 1.5 for once + 50% reorder>,
  "subscriptionPotential": <true/false>,
  "estimatedDaysToSource": <how many days from decision to first sale>,
  "tariffRisk": "low|medium|high",
  "notes": "<any important caveats>"
}`;

    const r = await this.ai.messages.create({
      model: config.quinn.model,
      max_tokens: 700,
      messages: [{ role: 'user', content: prompt }],
    });
    return this._parseJSON(r.content[0].text, {
      productCostUSD: 12, shippingCostUSD: 5, packagingCostUSD: 1,
      totalCOGS: 18, suggestedRetailPrice: 45, priceFloor: 29, priceCeiling: 79,
      grossMarginUSD: 27, grossMarginPct: 60, paymentProcessingFeeUSD: 1.61,
      netMarginAfterFeesUSD: 25.39, returnRiskPct: 5, chargebackRiskScore: 2,
      fragilityScore: 2, aovPotential: 55, ltvMultiple: 1.2,
      subscriptionPotential: false, estimatedDaysToSource: 3,
      tariffRisk: 'medium', notes: 'Default estimate',
    });
  }

  // ── Scenario Modeling ─────────────────────────────────────
  _buildScenarios(b) {
    const vol = { conservative: 50, base: 150, optimistic: 400 }; // monthly units
    return Object.entries(vol).reduce((acc, [label, units]) => {
      const revenue = units * b.suggestedRetailPrice;
      const cogs = units * b.totalCOGS;
      const returns = Math.floor(units * (b.returnRiskPct / 100));
      const netUnits = units - returns;
      const netRevenue = netUnits * b.suggestedRetailPrice;
      const grossProfit = netRevenue - cogs;
      acc[label] = {
        monthlyUnits: units,
        monthlyRevenue: Math.round(revenue),
        netRevenue: Math.round(netRevenue),
        grossProfit: Math.round(grossProfit),
        estimatedAdSpend: label === 'conservative' ? units * 8 : label === 'base' ? units * 10 : units * 12,
        netProfit: Math.round(grossProfit - (label === 'conservative' ? units * 8 : label === 'base' ? units * 10 : units * 12)),
      };
      return acc;
    }, {});
  }

  // ── Break-Even Analysis ───────────────────────────────────
  _calculateBreakEven(b) {
    // Fixed costs per month assumed: $97 (Shopify) + $30 (apps) + $20 (misc) = $147
    const fixedCosts = 147;
    const contributionMarginPerUnit = b.grossMarginUSD - b.paymentProcessingFeeUSD;
    const breakEvenUnits = Math.ceil(fixedCosts / contributionMarginPerUnit);
    const breakEvenRevenue = Math.round(breakEvenUnits * b.suggestedRetailPrice);
    return {
      monthlyFixedCosts: fixedCosts,
      contributionMarginPerUnit: Math.round(contributionMarginPerUnit * 100) / 100,
      breakEvenUnitsPerMonth: breakEvenUnits,
      breakEvenRevenue,
      daysToBreakEven: Math.ceil(breakEvenUnits / 5), // assume 5 units/day at start
    };
  }

  // ── CAC Thresholds ────────────────────────────────────────
  _calculateCACThresholds(b) {
    const maxCACForProfit = b.grossMarginUSD * 0.40;  // spend max 40% of GM on acquisition
    const maxCACBreakEven = b.grossMarginUSD - b.paymentProcessingFeeUSD;
    const targetCAC = b.grossMarginUSD * 0.25;        // ideal: 25% of GM on acquisition
    return {
      targetCACForHealthyMargin: Math.round(targetCAC * 100) / 100,
      maxCACForAnyProfit: Math.round(maxCACBreakEven * 100) / 100,
      recommendedMaxCAC: Math.round(maxCACForProfit * 100) / 100,
      cacToGMRatioTarget: '25%',
      ifLTVApplied: b.ltvMultiple > 1.1
        ? `With ${b.ltvMultiple}x LTV, you can afford up to $${Math.round(maxCACForProfit * b.ltvMultiple)} CAC`
        : 'Single-purchase product — CAC discipline critical',
    };
  }

  // ── Margin Quality Analysis ───────────────────────────────
  _analyzeMargin(b) {
    const rating = b.grossMarginPct >= 70 ? 'EXCELLENT'
      : b.grossMarginPct >= 60 ? 'STRONG'
      : b.grossMarginPct >= 50 ? 'ACCEPTABLE'
      : b.grossMarginPct >= 40 ? 'WEAK'
      : 'REJECT';
    return {
      rating,
      grossMarginPct: b.grossMarginPct,
      meetsMinimumThreshold: b.grossMarginPct >= config.thresholds.minGrossMarginPct,
      marginRisk: b.returnRiskPct > 10 ? 'HIGH — high return rate will erode margin' : 'LOW',
      bundleUpsellOpportunity: b.aovPotential > b.suggestedRetailPrice * 1.3,
      recommendedPricingStrategy: b.aovPotential > b.suggestedRetailPrice
        ? `Bundle to push AOV from $${b.suggestedRetailPrice} to $${b.aovPotential}`
        : 'Single SKU pricing — focus on volume',
    };
  }

  // ── Verdict ───────────────────────────────────────────────
  _renderVerdict(b) {
    const issues = [];
    if (b.grossMarginPct < config.thresholds.minGrossMarginPct) issues.push(`Margin ${b.grossMarginPct}% below ${config.thresholds.minGrossMarginPct}% minimum`);
    if (b.totalCOGS > config.thresholds.maxLandedCostUSD) issues.push(`Landed cost $${b.totalCOGS} exceeds $${config.thresholds.maxLandedCostUSD} threshold`);
    if (b.returnRiskPct > 15) issues.push(`High return risk ${b.returnRiskPct}% — consider product quality`);
    if (b.fragilityScore > 7) issues.push('Fragile product — expect shipping damage claims');
    if (b.tariffRisk === 'high') issues.push('High tariff risk — source from non-China supplier');

    return {
      pass: issues.length === 0,
      issues,
      recommendation: issues.length === 0
        ? 'APPROVED — economics support viable dropship operation'
        : `CONDITIONAL — address: ${issues[0]}`,
    };
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
