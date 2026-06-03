// ============================================================
// CHANNEL SCOUT AGENT — Finds cheapest content distribution
// ============================================================

import Anthropic from '@anthropic-ai/sdk';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config } from '../config.js';
import { search, formatSearchResults } from './web-search.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const client    = new Anthropic({ apiKey: config.anthropic.apiKey });

// Load platform baseline data
let platformData = { platforms: {} };
try {
  platformData = JSON.parse(
    readFileSync(resolve(__dirname, '../data/platforms.json'), 'utf-8')
  );
} catch { /* use defaults */ }

// ── Tool definitions for Claude ──────────────────────────────
const CHANNEL_TOOLS = [
  {
    name: 'research_channel_costs',
    description: 'Research ad costs, CPM, CPC, and CAC for a specific content distribution channel',
    input_schema: {
      type: 'object',
      properties: {
        channel: { type: 'string', description: 'Platform or channel name (e.g. TikTok, Pinterest, Reddit)' },
      },
      required: ['channel'],
    },
  },
  {
    name: 'research_channel_saturation',
    description: 'Research how saturated a channel is with dropshipping advertisers and organic sellers',
    input_schema: {
      type: 'object',
      properties: {
        channel: { type: 'string', description: 'Channel to research' },
      },
      required: ['channel'],
    },
  },
  {
    name: 'research_underpriced_attention',
    description: 'Search for information about underpriced attention or arbitrage opportunities on specific platforms',
    input_schema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Specific search query about cheap attention arbitrage' },
      },
      required: ['query'],
    },
  },
  {
    name: 'record_channel_opportunity',
    description: 'Record a scored channel opportunity after research',
    input_schema: {
      type: 'object',
      properties: {
        name:                  { type: 'string', description: 'Channel name' },
        type:                  { type: 'string', enum: ['organic', 'paid', 'hybrid'], description: 'Traffic type' },
        cpm:                   { type: 'number', description: 'Average CPM in USD (0 if organic)' },
        cpc:                   { type: 'number', description: 'Average CPC in USD' },
        avgCac:                { type: 'number', description: 'Average customer acquisition cost in USD' },
        cpmScore:              { type: 'number', description: '1-10 scale, higher = more expensive (BAD)' },
        audienceQualityScore:  { type: 'number', description: '1-10, buyer intent and quality' },
        competitionScore:      { type: 'number', description: '1-10, higher = more saturated (BAD)' },
        scalabilityScore:      { type: 'number', description: '1-10, how well it scales' },
        conversionScore:       { type: 'number', description: '1-10, conversion quality' },
        organicPotential:      { type: 'string', enum: ['none', 'low', 'medium', 'high', 'unlimited'] },
        paidPotential:         { type: 'string', enum: ['none', 'low', 'medium', 'high', 'excellent'] },
        bestContentType:       { type: 'string', description: 'Best content format for this channel' },
        bestOfferType:         { type: 'string', description: 'Best type of product/offer to run here' },
        speedToTest:           { type: 'string', enum: ['hours', 'days', 'weeks'] },
        mainWeakness:          { type: 'string' },
        whyUnderpriced:        { type: 'string', description: 'Why this channel is an attention arbitrage opportunity' },
        hasPaid:               { type: 'boolean' },
        isPaidOnly:            { type: 'boolean' },
        audienceAge:           { type: 'string' },
        bestFor:               { type: 'array', items: { type: 'string' } },
        contentFormats:        { type: 'array', items: { type: 'string' } },
      },
      required: ['name', 'cpmScore', 'audienceQualityScore', 'competitionScore'],
    },
  },
];

// ── Tool execution ───────────────────────────────────────────
async function executeTool(toolName, toolInput) {
  switch (toolName) {
    case 'research_channel_costs': {
      const queries = [
        `${toolInput.channel} advertising CPM CPC 2026`,
        `${toolInput.channel} ads cost per click average`,
        `${toolInput.channel} ecommerce dropshipping ad performance`,
      ];
      const results = [];
      for (const q of queries.slice(0, 2)) {
        const res = await search(q, 4);
        results.push(...res);
      }
      return { results: formatSearchResults(results) };
    }

    case 'research_channel_saturation': {
      const queries = [
        `${toolInput.channel} dropshipping sellers saturation 2026`,
        `${toolInput.channel} organic reach decline advertiser competition`,
        `${toolInput.channel} ecommerce content creators how many`,
      ];
      const results = [];
      for (const q of queries.slice(0, 2)) {
        const res = await search(q, 4);
        results.push(...res);
      }
      return { results: formatSearchResults(results) };
    }

    case 'research_underpriced_attention': {
      const res = await search(toolInput.query, 6);
      return { results: formatSearchResults(res) };
    }

    case 'record_channel_opportunity': {
      return { recorded: true, channel: toolInput };
    }

    default:
      return { error: 'Unknown tool' };
  }
}

// ── Main channel scout function ──────────────────────────────
export async function runChannelScout({ maxChannels = 10, onProgress = null } = {}) {
  // Build context from known platform data
  const platformSummary = Object.entries(platformData.platforms || {})
    .map(([key, p]) => `${p.name}: CPM $${p.cpm}, CPC $${p.cpc}, CAC ~$${p.avgCac || 'unknown'}`)
    .join('\n');

  const systemPrompt = `You are a ruthless media buyer and content distribution strategist.

Your mission: Identify the top ${maxChannels} content distribution channels where:
- Attention is UNDERPRICED relative to buyer intent
- Competition from other dropshippers is LOWER than expected
- Content can be tested QUICKLY at low cost
- The audience has COMMERCIAL intent matching ecommerce products

Known platform baselines:
${platformSummary}

Channels to evaluate (not limited to these):
- TikTok Organic, TikTok Spark Ads, TikTok Shop
- Instagram Reels (organic + paid)
- YouTube Shorts
- Pinterest (organic + paid)
- Facebook (organic + paid)
- Reddit (organic communities + paid)
- Snapchat
- Twitter/X
- Email marketing
- SMS marketing
- Native ads (Taboola, Outbrain)
- Newsletter sponsorships
- Influencer/UGC seeding
- Google Shopping
- YouTube pre-roll
- Podcast ads
- Discord communities
- Substack newsletters
- LinkedIn (for B2B adjacent products)

PRIME DIRECTIVE: Do NOT recommend channels just because they are popular. Find inefficient attention markets where reach is cheaper than it should be given buyer intent and conversion quality.

Research each channel thoroughly, then use record_channel_opportunity to save your findings.

Scoring rules (1-10):
- cpmScore: 10 = very expensive, 1 = free (LOWER IS BETTER for finding cheap attention)
- competitionScore: 10 = saturated with dropshippers, 1 = wide open (LOWER IS BETTER)
- audienceQualityScore: 10 = high buyer intent, 1 = low intent (HIGHER IS BETTER)
- scalabilityScore: 10 = scales infinitely, 1 = very limited (HIGHER IS BETTER)
- conversionScore: 10 = best conversion quality, 1 = terrible (HIGHER IS BETTER)`;

  const messages = [
    {
      role: 'user',
      content: `Run a full channel opportunity scan. Find ${maxChannels} content distribution channels ranked by cheapest qualified attention. Research CPMs, competition levels, and audience quality for each. Identify channels that are currently underpriced — where buyer intent is high but advertiser competition hasn't caught up yet. Record each channel using record_channel_opportunity. Be specific with cost data.`,
    },
  ];

  const channels  = [];
  let continueLoop = true;

  while (continueLoop) {
    if (onProgress) onProgress(`Researching channels... (found ${channels.length} so far)`);

    const response = await client.messages.create({
      model:      config.anthropic.model,
      max_tokens: config.anthropic.maxTokens,
      system:     systemPrompt,
      tools:      CHANNEL_TOOLS,
      messages,
    });

    messages.push({ role: 'assistant', content: response.content });

    if (response.stop_reason === 'end_turn') {
      continueLoop = false;
      break;
    }

    if (response.stop_reason === 'tool_use') {
      const toolResults = [];

      for (const block of response.content) {
        if (block.type !== 'tool_use') continue;

        const result = await executeTool(block.name, block.input);

        if (block.name === 'record_channel_opportunity' && result.channel) {
          channels.push(result.channel);
          if (onProgress) onProgress(`Recorded channel: ${result.channel.name} (${channels.length}/${maxChannels})`);
        }

        toolResults.push({
          type:        'tool_result',
          tool_use_id: block.id,
          content:     JSON.stringify(result),
        });
      }

      messages.push({ role: 'user', content: toolResults });

      if (channels.length >= maxChannels) continueLoop = false;
    } else {
      continueLoop = false;
    }
  }

  return channels;
}
