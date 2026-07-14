/**
 * Decision Engine — Scores Products
 * 
 * Inputs: Sales data (Amazon, eBay), Supply (AliExpress), Demand (Google Trends, YouTube, Reddit)
 * Output: 0-100 score + recommendation (PURSUE or SKIP)
 * 
 * Decision Rules:
 * ✓ Is it actually selling? (Amazon rank, eBay sold count)
 * ✓ Is demand real? (Google Trends, Reddit mentions, YouTube reviews)
 * ✓ Is supply available? (AliExpress stock, lead time)
 * ✓ Am I jumping into a crowded market? (Competitor count)
 * ✓ Is the margin worth it? (Cost + pricing tiers)
 * ✓ Is it cooling or heating up? (Trend velocity)
 */

export class DecisionEngine {
  constructor() {
    this.weights = {
      sales_proof: 0.25,         // Amazon rank + eBay sold count (25%)
      demand_signal: 0.20,        // Google Trends + YouTube + Reddit (20%)
      supply_available: 0.15,     // AliExpress stock (15%)
      market_saturation: 0.15,    // Competitor count (15%)
      margin_potential: 0.15,     // Cost vs retail (15%)
      trend_velocity: 0.10        // Accelerating vs cooling (10%)
    };
  }

  /**
   * Score a product (0-100)
   * Returns: { overall_score, components, recommendation, reasoning }
   */
  score(product) {
    const components = {
      sales_proof: this.scoreSalesProof(product),
      demand_signal: this.scoreDemandSignal(product),
      supply_available: this.scoreSupplyAvailable(product),
      market_saturation: this.scoreMarketSaturation(product),
      margin_potential: this.scoreMarginPotential(product),
      trend_velocity: this.scoreTrendVelocity(product)
    };

    // Calculate weighted score
    const overallScore = Math.round(
      components.sales_proof * this.weights.sales_proof +
      components.demand_signal * this.weights.demand_signal +
      components.supply_available * this.weights.supply_available +
      components.market_saturation * this.weights.market_saturation +
      components.margin_potential * this.weights.margin_potential +
      components.trend_velocity * this.weights.trend_velocity
    );

    // Generate recommendation
    const recommendation = overallScore >= 70 ? 'PURSUE' : overallScore >= 50 ? 'INVESTIGATE' : 'SKIP';
    const reasoning = this.generateReasoning(product, components, overallScore);

    return {
      overall_score: overallScore,
      recommendation,
      reasoning,
      components,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Score: Is it actually selling? (0-100)
   * 
   * Signals:
   * - Amazon rank < 500 = hot seller (100 points)
   * - Amazon rank < 5000 = good (80 points)
   * - eBay 30-day sales > 50 = proven demand (80 points)
   * - Review velocity > 10/day = active sales (70 points)
   */
  scoreSalesProof(product) {
    let score = 0;
    let signals = 0;

    const amazonRank = product.sales_data.amazon_rank;
    if (amazonRank) {
      if (amazonRank < 500) {
        score += 100;
      } else if (amazonRank < 5000) {
        score += 80;
      } else if (amazonRank < 20000) {
        score += 50;
      } else {
        score += 20;
      }
      signals += 1;
    }

    const ebayySoldCount = product.sales_data.ebay_sold_count_30d;
    if (ebayySoldCount) {
      if (ebayySoldCount > 100) {
        score += 90;
      } else if (ebayySoldCount > 50) {
        score += 80;
      } else if (ebayySoldCount > 10) {
        score += 60;
      } else {
        score += 30;
      }
      signals += 1;
    }

    const reviewVelocity = product.sales_data.amazon_review_velocity;
    if (reviewVelocity) {
      if (reviewVelocity > 20) {
        score += 85;
      } else if (reviewVelocity > 10) {
        score += 70;
      } else if (reviewVelocity > 3) {
        score += 50;
      } else {
        score += 20;
      }
      signals += 1;
    }

    return signals > 0 ? Math.round(score / signals) : 0;
  }

  /**
   * Score: Is demand real? (0-100)
   * 
   * Signals:
   * - Google Trends score > 70 = high demand (90 points)
   * - YouTube reviews > 30 = interest (80 points)
   * - Reddit mentions > 100 = community interest (70 points)
   * - Multiple signals = credibility
   */
  scoreDemandSignal(product) {
    let score = 0;
    let signals = 0;

    const googleTrends = product.demand_signals.google_trends_score;
    if (googleTrends) {
      score += googleTrends; // 0-100 already
      signals += 1;
    }

    const youtubeReviews = product.demand_signals.youtube_review_count;
    if (youtubeReviews) {
      if (youtubeReviews > 50) {
        score += 90;
      } else if (youtubeReviews > 20) {
        score += 80;
      } else if (youtubeReviews > 5) {
        score += 60;
      } else {
        score += 30;
      }
      signals += 1;
    }

    const redditMentions = product.demand_signals.reddit_mentions_30d;
    if (redditMentions) {
      if (redditMentions > 200) {
        score += 90;
      } else if (redditMentions > 100) {
        score += 80;
      } else if (redditMentions > 50) {
        score += 60;
      } else if (redditMentions > 10) {
        score += 40;
      } else {
        score += 20;
      }
      signals += 1;
    }

    return signals > 0 ? Math.round(score / signals) : 0;
  }

  /**
   * Score: Is supply available? (0-100)
   * 
   * Penalties:
   * - No stock = 0 points
   * - Limited stock (< 100 units) = 40 points (RISKY)
   * - Moderate stock (100-1000 units) = 70 points
   * - Healthy stock (> 1000 units) = 100 points
   * 
   * Also check lead time:
   * - > 30 days = risky (reduce by 20 points)
   * - 7-30 days = ok (no penalty)
   * - < 7 days = ideal (bonus 10 points)
   */
  scoreSupplyAvailable(product) {
    let score = 0;

    const stock = product.supply_data.aliexpress_stock;
    if (stock === undefined || stock === null) {
      return 50; // Unknown stock = medium risk
    }

    if (stock === 0) {
      return 0; // No stock = automatic fail
    } else if (stock < 100) {
      score = 40; // Limited stock = risky
    } else if (stock < 1000) {
      score = 70; // Moderate stock = acceptable
    } else {
      score = 100; // Healthy stock = ideal
    }

    // Adjust for lead time
    const leadTime = product.supply_data.supplier_lead_time_days;
    if (leadTime) {
      if (leadTime > 30) {
        score -= 20; // Long lead time = risky
      } else if (leadTime < 7) {
        score = Math.min(score + 10, 100); // Short lead time = bonus
      }
    }

    return Math.max(score, 0);
  }

  /**
   * Score: Is the market flooded? (0-100)
   * 
   * Inverse relationship:
   * - < 500 competitors = 100 points (GOLD MINE)
   * - 500-5000 competitors = 70 points (ACCEPTABLE)
   * - 5000-50000 competitors = 40 points (CROWDED)
   * - > 50000 competitors = 10 points (SATURATED)
   */
  scoreMarketSaturation(product) {
    const competitors = product.market_saturation.competitor_count_estimate;

    if (!competitors || competitors === 0) {
      return 50; // Unknown = medium risk
    }

    if (competitors < 500) {
      return 100;
    } else if (competitors < 5000) {
      return 70;
    } else if (competitors < 50000) {
      return 40;
    } else {
      return 10;
    }
  }

  /**
   * Score: Is the margin worth it? (0-100)
   * 
   * Target margins:
   * - > 100% = 100 points (EXCELLENT)
   * - 50-100% = 85 points (GOOD)
   * - 30-50% = 70 points (ACCEPTABLE)
   * - 15-30% = 40 points (THIN)
   * - < 15% = 10 points (NOT WORTH IT)
   */
  scoreMarginPotential(product) {
    const marginLow = product.pricing.margin_low_percent;
    const marginHigh = product.pricing.margin_high_percent;

    let score = 0;
    let signals = 0;

    if (marginLow) {
      if (marginLow > 100) score += 100;
      else if (marginLow > 50) score += 85;
      else if (marginLow > 30) score += 70;
      else if (marginLow > 15) score += 40;
      else score += 10;
      signals += 1;
    }

    if (marginHigh) {
      if (marginHigh > 100) score += 100;
      else if (marginHigh > 50) score += 85;
      else if (marginHigh > 30) score += 70;
      else if (marginHigh > 15) score += 40;
      else score += 10;
      signals += 1;
    }

    return signals > 0 ? Math.round(score / signals) : 50; // Unknown margin = medium
  }

  /**
   * Score: Is it heating up or cooling off? (0-100)
   * 
   * Velocity multipliers:
   * - Accelerating = +20 points
   * - Stable = +0 points
   * - Decelerating = -30 points
   * 
   * Days on trend:
   * - < 7 days = risky (new, unproven)
   * - 7-30 days = ideal (proven but not saturated yet)
   * - > 30 days = cooling (trend is aging)
   */
  scoreTrendVelocity(product) {
    let score = 50; // Baseline
    let daysOnTrend = product.decision_engine_score?.days_trending || 0;

    // Velocity adjustment
    const velocity = product.decision_engine_score?.trending_velocity;
    if (velocity === 'accelerating') {
      score += 20;
    } else if (velocity === 'decelerating') {
      score -= 30;
    }

    // Days on trend adjustment
    if (daysOnTrend < 7) {
      score -= 15; // Too new = unproven
    } else if (daysOnTrend > 30) {
      score -= 10; // Trend is aging
    }

    return Math.max(score, 0);
  }

  /**
   * Generate human-readable reasoning for the score
   */
  generateReasoning(product, components, overallScore) {
    const reasons = [];

    // Find strongest signals
    const components_sorted = Object.entries(components)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3);

    if (components.sales_proof > 70) {
      reasons.push('✓ Real sales proof from Amazon/eBay');
    } else if (components.sales_proof > 40) {
      reasons.push('~ Limited sales proof');
    } else {
      reasons.push('✗ Weak sales signals');
    }

    if (components.demand_signal > 70) {
      reasons.push('✓ Strong demand signals');
    }

    if (components.supply_available < 40) {
      reasons.push('✗ Supply concerns (low stock or long lead time)');
    }

    if (components.market_saturation < 40) {
      reasons.push('✗ Market is crowded');
    }

    if (components.margin_potential < 40) {
      reasons.push('✗ Margins too thin');
    }

    if (components.trend_velocity < 40) {
      reasons.push('✗ Trend is cooling off');
    }

    return reasons.join(' | ');
  }
}
