// ============================================================
// DROPSHIP INTELLIGENCE AGENT — MAIN ORCHESTRATOR
// Coordinates all modules into a unified research + strategy loop
// ============================================================

import { readFile, writeFile } from 'fs/promises';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config } from './config.js';

import { runProductScout }    from './modules/product-scout.js';
import { runChannelScout }    from './modules/channel-scout.js';
import { scoreProducts, scoreChannels, scoreMatches, labelWinners } from './modules/scorer.js';
import { generateContentStrategy, generateQuickHooks } from './modules/content.js';
import { Reporter } from './modules/reporter.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

export class DropshipAgent {

  constructor() {
    this.reporter = new Reporter(join(__dirname, 'reports'));
    this.dbPath   = join(__dirname, 'data', 'products.json');
  }

  // ──────────────────────────────────────────────────────────
  // FULL SCAN — the main pipeline
  // Runs product scout → channel scout → scoring → content → report
  // ──────────────────────────────────────────────────────────
  async runFullScan({
    niche       = null,
    maxProducts = config.agent.topOpportunitiesCount,
    maxChannels = 8,
    includeContent = true,
    onProgress  = null,
  } = {}) {

    const progress = (msg) => {
      if (onProgress) onProgress(msg);
      else console.log(`  ${msg}`);
    };

    console.log('\n' + '═'.repeat(60));
    console.log('  DROPSHIP INTELLIGENCE AGENT — FULL SCAN');
    console.log('═'.repeat(60));
    const startTime = Date.now();

    // ── Step 1: Scout Products ─────────────────────────────
    progress('Step 1/5 — Scouting product opportunities...');
    const rawProducts = await runProductScout({
      niche,
      maxProducts,
      onProgress: progress,
    });
    progress(`Found ${rawProducts.length} raw product candidates`);

    // ── Step 2: Scout Channels ─────────────────────────────
    progress('Step 2/5 — Scouting attention channels...');
    const rawChannels = await runChannelScout({
      maxChannels,
      onProgress: progress,
    });
    progress(`Found ${rawChannels.length} raw channels`);

    // ── Step 3: Score Everything ───────────────────────────
    progress('Step 3/5 — Scoring all opportunities...');
    const rankedProducts = scoreProducts(rawProducts);
    const rankedChannels = scoreChannels(rawChannels);

    // Cross-match: score every product × channel combination
    const allMatches = scoreMatches(rankedProducts, rankedChannels);
    const topMatches = allMatches.slice(0, 15);

    // Label special winners
    const winners = labelWinners(rankedProducts, rankedChannels, allMatches);
    progress(`Scored and ranked ${rankedProducts.length} products × ${rankedChannels.length} channels`);

    // ── Step 4: Generate Content Strategies (top 3) ────────
    let contentStrategies = [];
    if (includeContent && rankedProducts.length > 0) {
      progress('Step 4/5 — Generating content strategies for top 3 products...');
      const top3 = rankedProducts.slice(0, 3);
      for (const product of top3) {
        try {
          const strategy = await generateContentStrategy(product, progress);
          contentStrategies.push({ product: product.name, strategy });
        } catch (err) {
          progress(`Content strategy failed for ${product.name}: ${err.message}`);
          contentStrategies.push({ product: product.name, strategy: null });
        }
      }
    }

    // ── Step 5: Report ─────────────────────────────────────
    progress('Step 5/5 — Generating reports...');
    const scanResult = {
      timestamp: new Date().toISOString(),
      niche: niche || 'all niches',
      summary: {
        productsAnalyzed: rawProducts.length,
        channelsAnalyzed: rawChannels.length,
        matchesGenerated: allMatches.length,
        durationSeconds: Math.round((Date.now() - startTime) / 1000),
      },
      rankedProducts,
      rankedChannels,
      topMatches,
      contentStrategies,
      winners,
    };

    const paths = await this.reporter.generateReport(scanResult);
    await this.appendToProductDB(rankedProducts);

    this.reporter.printSummary(scanResult);

    progress(`Scan complete in ${scanResult.summary.durationSeconds}s`);
    progress(`JSON: ${paths.jsonPath}`);
    progress(`Markdown: ${paths.mdPath}`);

    return scanResult;
  }

  // ──────────────────────────────────────────────────────────
  // QUICK RESEARCH — lightweight single-product analysis
  // ──────────────────────────────────────────────────────────
  async quickResearch(productName) {
    console.log(`\n  Quick Research: "${productName}"`);

    const [hooks, channelRankings] = await Promise.all([
      generateQuickHooks(productName, 5),
      runChannelScout({ maxChannels: 5 }),
    ]);

    const rankedChannels = scoreChannels(channelRankings);

    return {
      product: productName,
      hooks,
      bestChannels: rankedChannels.slice(0, 5),
      timestamp: new Date().toISOString(),
    };
  }

  // ──────────────────────────────────────────────────────────
  // CONTENT ONLY — generate content strategy for an existing product
  // ──────────────────────────────────────────────────────────
  async generateContent(productName, channel = 'TikTok') {
    console.log(`\n  Generating content strategy: "${productName}" on ${channel}`);
    const strategy = await generateContentStrategy(
      { name: productName, bestPlatform: channel },
    );
    return strategy;
  }

  // ──────────────────────────────────────────────────────────
  // CHANNEL SCAN ONLY — find cheapest attention right now
  // ──────────────────────────────────────────────────────────
  async scanChannels(maxChannels = 10) {
    console.log(`\n  Scanning ${maxChannels} attention channels...`);
    const raw = await runChannelScout({ maxChannels });
    const ranked = scoreChannels(raw);
    return ranked;
  }

  // ──────────────────────────────────────────────────────────
  // PRODUCT SCAN ONLY — find products in a specific niche
  // ──────────────────────────────────────────────────────────
  async scanProducts(niche, maxProducts = 10) {
    console.log(`\n  Scanning products in: "${niche}"`);
    const raw = await runProductScout({ niche, maxProducts });
    const ranked = scoreProducts(raw);
    return ranked;
  }

  // ──────────────────────────────────────────────────────────
  // MONITOR MODE — continuous scan loop
  // ──────────────────────────────────────────────────────────
  async startMonitor(intervalMinutes = config.agent.scanIntervalMinutes) {
    console.log(`\n  Monitor mode started — scanning every ${intervalMinutes} minutes`);
    const cron = (await import('node-cron')).default;
    const schedule = `*/${intervalMinutes} * * * *`;
    cron.schedule(schedule, async () => {
      console.log(`\n  [Monitor] Running scheduled scan at ${new Date().toLocaleTimeString()}`);
      try {
        await this.runFullScan({ includeContent: false });
      } catch (err) {
        console.error(`  [Monitor] Scan failed: ${err.message}`);
      }
    });
    // Run once immediately
    await this.runFullScan({ includeContent: false });
  }

  // ──────────────────────────────────────────────────────────
  // DB HELPERS
  // ──────────────────────────────────────────────────────────
  async appendToProductDB(products) {
    try {
      const raw = await readFile(this.dbPath, 'utf-8');
      const db = JSON.parse(raw);
      db.lastUpdated = new Date().toISOString();

      for (const p of products) {
        const existing = db.tracked.findIndex(t => t.name === p.name);
        const entry = { ...p, lastSeen: new Date().toISOString() };
        if (existing >= 0) {
          db.tracked[existing] = entry;
        } else {
          db.tracked.push(entry);
        }
      }

      db.scanHistory.push({
        timestamp: new Date().toISOString(),
        productsFound: products.length,
        topProduct: products[0]?.name,
        topScore: products[0]?.overallScore,
      });

      // Keep scan history to last 50 entries
      if (db.scanHistory.length > 50) db.scanHistory = db.scanHistory.slice(-50);

      await writeFile(this.dbPath, JSON.stringify(db, null, 2), 'utf-8');
    } catch (err) {
      console.error(`  DB write failed: ${err.message}`);
    }
  }

  async getProductDB() {
    try {
      const raw = await readFile(this.dbPath, 'utf-8');
      return JSON.parse(raw);
    } catch {
      return { tracked: [], watchlist: [], rejected: [], scanHistory: [] };
    }
  }
}
