#!/usr/bin/env node
// ============================================================
// DROPSHIP INTELLIGENCE AGENT — CLI ENTRY POINT
// ============================================================
// Usage:
//   node index.js                     → interactive menu
//   node index.js scan                → full scan (all niches)
//   node index.js scan --niche "pets" → scan specific niche
//   node index.js products            → products only
//   node index.js channels            → channels only
//   node index.js research "product"  → quick research
//   node index.js content "product"   → generate content strategy
//   node index.js monitor             → continuous monitor mode
//   node index.js dashboard           → serve web dashboard
//   node index.js history             → view scan history
// ============================================================

import { Command } from 'commander';
import { createServer } from 'http';
import { readFile } from 'fs/promises';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { DropshipAgent } from './agent.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const program   = new Command();
const agent     = new DropshipAgent();

program
  .name('dropship-agent')
  .description('AI-powered dropshipping intelligence agent')
  .version('1.0.0');

// ── FULL SCAN ─────────────────────────────────────────────────
program
  .command('scan')
  .description('Run a full product + channel scan')
  .option('-n, --niche <niche>', 'Focus on a specific niche')
  .option('-p, --products <number>', 'Number of products to scout', '10')
  .option('-c, --channels <number>', 'Number of channels to scout', '8')
  .option('--no-content', 'Skip content strategy generation')
  .action(async (opts) => {
    try {
      await agent.runFullScan({
        niche:          opts.niche || null,
        maxProducts:    parseInt(opts.products),
        maxChannels:    parseInt(opts.channels),
        includeContent: opts.content !== false,
      });
    } catch (err) {
      console.error('Scan failed:', err.message);
      process.exit(1);
    }
  });

// ── PRODUCTS ONLY ─────────────────────────────────────────────
program
  .command('products [niche]')
  .description('Scout and score products only')
  .option('-p, --max <number>', 'Max products', '10')
  .action(async (niche, opts) => {
    try {
      const products = await agent.scanProducts(niche || 'all niches', parseInt(opts.max));
      console.log('\nTOP PRODUCTS:');
      products.slice(0, 10).forEach((p, i) => {
        console.log(`  ${i+1}. ${p.name} — ${p.overallScore}/10 (${p.scoreLabel})`);
        console.log(`     Margin: ${p.grossMarginPct}% | Platform: ${p.bestPlatform}`);
      });
    } catch (err) {
      console.error('Products scan failed:', err.message);
      process.exit(1);
    }
  });

// ── CHANNELS ONLY ─────────────────────────────────────────────
program
  .command('channels')
  .description('Scout and rank attention channels only')
  .option('-c, --max <number>', 'Max channels', '10')
  .action(async (opts) => {
    try {
      const channels = await agent.scanChannels(parseInt(opts.max));
      console.log('\nTOP CHANNELS (cheapest attention first):');
      channels.slice(0, 10).forEach((c, i) => {
        console.log(`  ${i+1}. ${c.name.padEnd(30)} CPM: $${String(c.cpm ?? 0).padEnd(6)} Score: ${c.overallScore}/10`);
        console.log(`     ${c.whyUnderpriced || c.type || ''}`);
      });
    } catch (err) {
      console.error('Channel scan failed:', err.message);
      process.exit(1);
    }
  });

// ── QUICK RESEARCH ────────────────────────────────────────────
program
  .command('research <product>')
  .description('Quick research a specific product')
  .action(async (product) => {
    try {
      const result = await agent.quickResearch(product);
      console.log(`\nQUICK RESEARCH: ${product}`);
      console.log('\nBest Content Hooks:');
      (result.hooks || []).forEach((h, i) => {
        console.log(`  ${i+1}. [${h.format}] "${h.hook}" — ${h.platform}`);
      });
      console.log('\nBest Channels:');
      (result.bestChannels || []).slice(0, 5).forEach((c, i) => {
        console.log(`  ${i+1}. ${c.name} — $${c.cpm ?? 0} CPM | Score: ${c.overallScore}/10`);
      });
    } catch (err) {
      console.error('Research failed:', err.message);
      process.exit(1);
    }
  });

// ── CONTENT STRATEGY ──────────────────────────────────────────
program
  .command('content <product>')
  .description('Generate viral content strategy for a product')
  .option('-c, --channel <channel>', 'Target platform', 'TikTok')
  .action(async (product, opts) => {
    try {
      const strategy = await agent.generateContent(product, opts.channel);
      console.log(`\nCONTENT STRATEGY: ${product}`);
      console.log(`\nPrimary Hook: "${strategy.primaryHook}"`);
      console.log(`\nTikTok Script:\n${strategy.tiktokScript}`);
      if (strategy.piggybackTargets?.length > 0) {
        console.log(`\nPiggyback Targets: ${strategy.piggybackTargets.join(', ')}`);
      }
      if (strategy.hashtagStack?.length > 0) {
        console.log(`\nHashtags: ${strategy.hashtagStack.join(' ')}`);
      }
      if (strategy.contentCalendar) {
        console.log('\n30-Day Content Calendar:');
        Object.entries(strategy.contentCalendar).forEach(([week, plan]) => {
          console.log(`  ${week}: ${plan}`);
        });
      }
    } catch (err) {
      console.error('Content generation failed:', err.message);
      process.exit(1);
    }
  });

// ── MONITOR MODE ──────────────────────────────────────────────
program
  .command('monitor')
  .description('Start continuous monitoring mode (runs scan on interval)')
  .option('-i, --interval <minutes>', 'Scan interval in minutes', '60')
  .action(async (opts) => {
    try {
      await agent.startMonitor(parseInt(opts.interval));
    } catch (err) {
      console.error('Monitor failed:', err.message);
      process.exit(1);
    }
  });

// ── HISTORY ───────────────────────────────────────────────────
program
  .command('history')
  .description('View scan history and tracked products')
  .action(async () => {
    try {
      const db = await agent.getProductDB();
      console.log(`\nTRACKED PRODUCTS: ${db.tracked.length}`);
      db.tracked.slice(0, 10).forEach((p, i) => {
        console.log(`  ${i+1}. ${p.name} — Score: ${p.overallScore}/10 | Last seen: ${p.lastSeen?.slice(0,10)}`);
      });
      console.log(`\nSCAN HISTORY: ${db.scanHistory.length} scans`);
      db.scanHistory.slice(-5).forEach(s => {
        console.log(`  ${s.timestamp?.slice(0,16)} — ${s.productsFound} products | Top: ${s.topProduct} (${s.topScore})`);
      });
    } catch (err) {
      console.error('History read failed:', err.message);
    }
  });

// ── DASHBOARD SERVER ──────────────────────────────────────────
program
  .command('dashboard')
  .description('Serve the web dashboard at localhost:3737')
  .option('-p, --port <port>', 'Port number', '3737')
  .action(async (opts) => {
    const port = parseInt(opts.port);
    const dashboardDir = join(__dirname, 'dashboard');
    const reportsDir   = join(__dirname, 'reports');

    const server = createServer(async (req, res) => {
      res.setHeader('Access-Control-Allow-Origin', '*');

      try {
        if (req.url === '/' || req.url === '/index.html') {
          const html = await readFile(join(dashboardDir, 'index.html'), 'utf-8');
          res.writeHead(200, { 'Content-Type': 'text/html' });
          res.end(html);

        } else if (req.url === '/api/latest') {
          try {
            const data = await readFile(join(reportsDir, 'latest.json'), 'utf-8');
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(data);
          } catch {
            res.writeHead(404, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'No scan data yet. Run: node index.js scan' }));
          }

        } else if (req.url === '/api/history') {
          const db = await agent.getProductDB();
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(db));

        } else if (req.url === '/api/scan' && req.method === 'POST') {
          res.writeHead(202, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'scan_started', message: 'Scan running in background' }));
          agent.runFullScan({ includeContent: false }).catch(console.error);

        } else {
          res.writeHead(404);
          res.end('Not found');
        }
      } catch (err) {
        res.writeHead(500);
        res.end(err.message);
      }
    });

    server.listen(port, () => {
      console.log(`\n  Dashboard running at: http://localhost:${port}`);
      console.log(`  API endpoints:`);
      console.log(`    GET  /api/latest   — latest scan results`);
      console.log(`    GET  /api/history  — product DB history`);
      console.log(`    POST /api/scan     — trigger new scan`);
      console.log('\n  Press Ctrl+C to stop\n');
    });
  });

// ── DEFAULT: Interactive menu ─────────────────────────────────
program
  .action(async () => {
    console.log('\n╔══════════════════════════════════════════════════════╗');
    console.log('║      DROPSHIP INTELLIGENCE AGENT v1.0                ║');
    console.log('╚══════════════════════════════════════════════════════╝');
    console.log('\nCommands:');
    console.log('  node index.js scan                 Full scan (all niches)');
    console.log('  node index.js scan -n "health"     Scan specific niche');
    console.log('  node index.js products             Scout products only');
    console.log('  node index.js channels             Scout channels only');
    console.log('  node index.js research "product"   Quick product research');
    console.log('  node index.js content "product"    Generate content strategy');
    console.log('  node index.js monitor              Start monitor mode');
    console.log('  node index.js dashboard            Serve web dashboard');
    console.log('  node index.js history              View scan history');
    console.log('\nSetup:');
    console.log('  1. npm install');
    console.log('  2. Start Quinn bridge at http://127.0.0.1:8765');
    console.log('  3. (Optional) Set SERP_API_KEY for live web search');
    console.log('  4. node index.js scan\n');
  });

program.parse(process.argv);

// If no args, show help
if (process.argv.length <= 2) {
  program.help();
}
