// ============================================================
// MODULE: REPORTER
// Generates formatted opportunity reports in multiple formats:
// Markdown, JSON, and HTML dashboard-ready JSON
// ============================================================

import { writeFile, mkdir } from 'fs/promises';
import { join } from 'path';
import { config } from '../config.js';

export class Reporter {

  constructor(reportsDir = './reports') {
    this.reportsDir = reportsDir;
  }

  async ensureDir() {
    try { await mkdir(this.reportsDir, { recursive: true }); } catch { /* exists */ }
  }

  // ── Main: Generate full report from scan results ─────────
  async generateReport(scanResult) {
    await this.ensureDir();
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const base = join(this.reportsDir, `scan-${ts}`);

    await Promise.all([
      this.saveJSON(scanResult, `${base}.json`),
      this.saveMarkdown(scanResult, `${base}.md`),
      this.saveDashboardData(scanResult, join(this.reportsDir, 'latest.json')),
    ]);

    console.log(`\n  Reports saved to: ${this.reportsDir}`);
    return { jsonPath: `${base}.json`, mdPath: `${base}.md` };
  }

  // ── JSON Report ───────────────────────────────────────────
  async saveJSON(data, path) {
    await writeFile(path, JSON.stringify(data, null, 2), 'utf-8');
  }

  // ── Dashboard-Ready JSON ──────────────────────────────────
  async saveDashboardData(data, path) {
    const dash = {
      lastUpdated: new Date().toISOString(),
      summary: data.summary,
      topProducts: (data.rankedProducts || []).slice(0, 10),
      topChannels: (data.rankedChannels || []).slice(0, 8),
      topMatches: (data.topMatches || []).slice(0, 10),
      winners: data.winners,
      platformCPMs: config.platforms,
    };
    await writeFile(path, JSON.stringify(dash, null, 2), 'utf-8');
  }

  // ── Markdown Report ───────────────────────────────────────
  async saveMarkdown(data, path) {
    const lines = [];
    const { rankedProducts, rankedChannels, topMatches, winners, summary } = data;

    lines.push(`# DROPSHIP INTELLIGENCE REPORT`);
    lines.push(`**Generated:** ${new Date().toLocaleString()}`);
    lines.push(`**Products Analyzed:** ${summary?.productsAnalyzed || 0} | **Channels Analyzed:** ${summary?.channelsAnalyzed || 0}`);
    lines.push('');

    // ── Winner Labels ──────────────────────────────────────
    if (winners) {
      lines.push('## WINNER LABELS');
      lines.push('');
      if (winners.bestOverallProduct)    lines.push(`🥇 **Best Overall Product:** ${winners.bestOverallProduct.name} (${winners.bestOverallProduct.overallScore}/10)`);
      if (winners.bestMarginProduct)     lines.push(`💰 **Best Margin:** ${winners.bestMarginProduct.name} — ${winners.bestMarginProduct.grossMarginPct || '?'}% GM`);
      if (winners.bestLowCompProduct)    lines.push(`🔵 **Best Low Competition:** ${winners.bestLowCompProduct.name}`);
      if (winners.bestFastLaunch)        lines.push(`🚀 **Best Fast Launch:** ${winners.bestFastLaunch.name}`);
      if (winners.bestCheapAttention)    lines.push(`💚 **Best Cheap Attention Channel:** ${winners.bestCheapAttention.name} — CPM $${winners.bestCheapAttention.cpm || 0}`);
      if (winners.bestOrganicChannel)    lines.push(`🆓 **Best Organic Channel:** ${winners.bestOrganicChannel.name}`);
      lines.push('');
    }

    // ── Top Products ───────────────────────────────────────
    lines.push('## TOP PRODUCT OPPORTUNITIES');
    lines.push('');
    for (let i = 0; i < Math.min(rankedProducts?.length || 0, 10); i++) {
      const p = rankedProducts[i];
      lines.push(`### #${i + 1} — ${p.name} (Score: ${p.overallScore}/10 — ${p.scoreLabel})`);
      if (p.recommendation) lines.push(`> ${p.recommendation}`);
      lines.push('');
      lines.push(`**Why they want it:** ${p.whyTheyWantIt || 'N/A'}`);
      lines.push(`**Target buyer:** ${p.targetBuyer || 'N/A'}`);
      lines.push(`**Selling price:** $${p.sellingPrice || '?'} | **Landed cost:** $${p.landedCost || '?'} | **Gross margin:** ${p.grossMarginPct || '?'}%`);
      lines.push(`**Best platform:** ${p.bestPlatform || 'N/A'} | **Best hook:** ${p.bestContentHook || 'N/A'}`);
      lines.push(`**Gap:** ${p.gapReason || 'N/A'}`);
      lines.push('');
      lines.push(`| Demand | Competition | Attention Cost | Margin | Launch Speed | **OVERALL** |`);
      lines.push(`|--------|-------------|----------------|--------|--------------|-------------|`);
      const s = p.scores || {};
      lines.push(`| ${s.demand || '?'}/10 | ${s.competition || '?'}/10 | ${s.attention || '?'}/10 | ${s.margin || '?'}/10 | ${s.launch || '?'}/10 | **${p.overallScore}/10** |`);
      lines.push('');
    }

    // ── Top Channels ───────────────────────────────────────
    lines.push('## TOP TRAFFIC CHANNELS');
    lines.push('');
    lines.push('| # | Channel | CPM | CPC | Avg CAC | Score | Organic Potential |');
    lines.push('|---|---------|-----|-----|---------|-------|-------------------|');
    for (let i = 0; i < Math.min(rankedChannels?.length || 0, 8); i++) {
      const c = rankedChannels[i];
      lines.push(`| ${i + 1} | ${c.name} | $${c.cpm ?? 0} | $${c.cpc ?? 0} | $${c.avgCac ?? '?'} | ${c.overallScore}/10 | ${c.organicPotential || 'N/A'} |`);
    }
    lines.push('');

    // ── Top Product-Channel Matches ────────────────────────
    if (topMatches?.length > 0) {
      lines.push('## TOP PRODUCT × CHANNEL MATCHES');
      lines.push('');
      lines.push('| Product | Channel | Match Score | Est. CAC | Net Margin |');
      lines.push('|---------|---------|-------------|----------|------------|');
      for (const m of topMatches.slice(0, 10)) {
        lines.push(`| ${m.product} | ${m.channel} | ${m.matchScore}/10 | ${m.estimatedCAC} | ${m.estimatedNetMargin} |`);
      }
      lines.push('');
    }

    // ── Traffic Arbitrage Playbook ─────────────────────────
    lines.push('## TRAFFIC ARBITRAGE PLAYBOOK');
    lines.push('');
    lines.push('**Phase 1 — Organic Validation (Week 1-4)**');
    lines.push('- Post 2-3x daily on TikTok/Instagram/Pinterest — zero ad spend');
    lines.push('- Use all 5 hook formats in the first week to find the winner');
    lines.push('- Piggyback trending sounds and formats in your niche');
    lines.push('');
    lines.push('**Phase 2 — Amplify Winners (Week 4-8)**');
    lines.push('- Boost top organic videos as Spark Ads ($10-50/day)');
    lines.push('- Launch Pinterest Shopping ads with product catalog');
    lines.push('- Test Reddit promoted posts in niche subreddits ($5/day)');
    lines.push('');
    lines.push('**Phase 3 — Arbitrage Scaling (Week 8+)**');
    lines.push('- Kill any channel where CAC exceeds 20% of AOV');
    lines.push('- Double budget on lowest-CAC channel weekly');
    lines.push('- Layer email/SMS to reduce future acquisition costs');
    lines.push('');

    // ── Content Strategy Summary ───────────────────────────
    if (data.contentStrategies?.length > 0) {
      lines.push('## CONTENT STRATEGIES');
      lines.push('');
      for (const cs of data.contentStrategies) {
        const s = cs.strategy;
        if (!s?.productName) continue;
        lines.push(`### ${s.productName}`);
        lines.push(`**Primary Hook:** ${s.primaryHook}`);
        if (s.tiktokScript) {
          lines.push('');
          lines.push('**TikTok Script:**');
          lines.push(`> ${s.tiktokScript.split('\n').join('\n> ')}`);
        }
        if (s.piggybackTargets?.length > 0) {
          lines.push(`**Piggyback Targets:** ${s.piggybackTargets.join(', ')}`);
        }
        if (s.hashtagStack?.length > 0) {
          lines.push(`**Hashtags:** ${s.hashtagStack.join(' ')}`);
        }
        lines.push('');
      }
    }

    lines.push('---');
    lines.push(`*Report by Dropship Intelligence Agent | ${new Date().toISOString()}*`);

    await writeFile(path, lines.join('\n'), 'utf-8');
  }

  // ── Console Summary (no file write) ──────────────────────
  printSummary(data) {
    const { rankedProducts, rankedChannels, winners } = data;
    console.log('\n' + '='.repeat(60));
    console.log('  DROPSHIP INTELLIGENCE — SCAN COMPLETE');
    console.log('='.repeat(60));

    if (winners?.bestOverallProduct) {
      console.log(`\n🥇 BEST OVERALL:   ${winners.bestOverallProduct.name} (${winners.bestOverallProduct.overallScore}/10)`);
    }
    if (winners?.bestCheapAttention) {
      console.log(`💚 CHEAPEST ATTN:  ${winners.bestCheapAttention.name} — CPM $${winners.bestCheapAttention.cpm || 0}`);
    }
    if (winners?.bestMarginProduct) {
      console.log(`💰 BEST MARGIN:    ${winners.bestMarginProduct.name} — ${winners.bestMarginProduct.grossMarginPct || '?'}% GM`);
    }
    if (winners?.bestFastLaunch) {
      console.log(`🚀 FASTEST LAUNCH: ${winners.bestFastLaunch.name}`);
    }
    if (winners?.bestLowCompProduct) {
      console.log(`🔵 LOWEST COMP:    ${winners.bestLowCompProduct.name}`);
    }

    console.log('\n── TOP 5 PRODUCTS ────────────────────────────────────');
    (rankedProducts || []).slice(0, 5).forEach((p, i) => {
      console.log(`  ${i + 1}. ${p.name.padEnd(40)} ${p.overallScore}/10 — ${p.scoreLabel}`);
    });

    console.log('\n── TOP 5 CHANNELS ────────────────────────────────────');
    (rankedChannels || []).slice(0, 5).forEach((c, i) => {
      console.log(`  ${i + 1}. ${c.name.padEnd(30)} CPM $${String(c.cpm ?? 0).padEnd(6)} Score: ${c.overallScore}/10`);
    });

    console.log('\n' + '='.repeat(60));
  }
}
