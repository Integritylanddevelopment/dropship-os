// ============================================================
// PRODUCT SCOUT AGENT — Finds and scores product opportunities
// ============================================================

import Anthropic from '@anthropic-ai/sdk';
import { config } from '../config.js';
import { search, multiSearch, formatSearchResults } from './web-search.js';

const client = new Anthropic({ apiKey: config.anthropic.apiKey });

// ── Tool definitions for Claude ──────────────────────────────
const PRODUCT_TOOLS = [
  {
    name: 'search_product_demand',
    description: 'Search for buyer demand signals, trending searches, and social engagement for a product or niche',
    input_schema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query for demand research' },
        platform: { type: 'string', enum: ['google', 'tiktok', 'amazon', 'general'], description: 'Where to focus the search' },
      },
      required: ['query'],
    },
  },
  {
    name: 'check_competition',
    description: 'Research how many sellers are competing in a product niche and their strength',
    input_schema: {
      type: 'object',
      properties: {
        product: { type: 'string', description: 'Product name or category to analyze' },
      },
      required: ['product'],
    },
  },
  {
    name: 'estimate_product_margins',
    description: 'Research pricing, cost estimates, and margin potential for a product',
    input_schema: {
      type: 'object',
      properties: {
        product: { type: 'string', description: 'Product to research pricing for' },
      },
      required: ['product'],
    },
  },
  {
    name: 'record_product_opportunity',
    description: 'Record a scored product opportunity after research is complete',
    input_schema: {
      type: 'object',
      properties: {
        name:               { type: 'string' },
        category:           { type: 'string' },
        targetBuyer:        { type: 'string' },
        whyTheyWantIt:      { type: 'string' },
        sellingPrice:       { type: 'number', description: 'USD retail price' },
        landedCost:         { type: 'number', description: 'USD cost to source + ship' },
        grossMarginPct:     { type: 'number', description: 'Percentage gross margin' },
        demandScore:        { type: 'number', description: '1-10, higher = more demand' },
        competitionScore:   { type: 'number', description: '1-10, higher = more competition (BAD)' },
        attentionCostScore: { type: 'number', description: '1-10, higher = more expensive attention (BAD)' },
        marginScore:        { type: 'number', description: '1-10, higher = better margin' },
        launchSpeedScore:   { type: 'number', description: '1-10, higher = faster to launch' },
        visualHookStrength: { type: 'number', description: '1-10, how visually compelling in 3 seconds' },
        impulseBuy:         { type: 'boolean' },
        videoFriendly:      { type: 'boolean' },
        bestContentHook:    { type: 'string', description: 'Best 1-sentence hook for this product' },
        bestPlatform:       { type: 'string', description: 'Best platform to sell this on' },
        gapReason:          { type: 'string', description: 'Why this is an inefficient market — buyers vs sellers gap' },
      },
      required: ['name', 'demandScore', 'competitionScore', 'marginScore'],
    },
  },
];

// ── Tool execution ───────────────────────────────────────────
async function executeTool(toolName, toolInput) {
  switch (toolName) {
    case 'search_product_demand': {
      const queries = [
        toolInput.query,
        `${toolInput.query} trending 2026`,
        `${toolInput.query} TikTok viral`,
        `${toolInput.query} buyer reviews`,
      ];
      const results = await multiSearch(queries.slice(0, 2), 5);
      return { results: formatSearchResults(results), query: toolInput.query };
    }

    case 'check_competition': {
      const queries = [
        `${toolInput.product} dropshipping competition sellers`,
        `${toolInput.product} Amazon sellers how many`,
        `${toolInput.product} market saturation`,
      ];
      const results = await multiSearch(queries.slice(0, 2), 5);
      return { results: formatSearchResults(results), product: toolInput.product };
    }

    case 'estimate_product_margins': {
      const queries = [
        `${toolInput.product} wholesale price AliExpress`,
        `${toolInput.product} retail price average`,
        `${toolInput.product} profit margin dropshipping`,
      ];
      const results = await multiSearch(queries.slice(0, 2), 5);
      return { results: formatSearchResults(results), product: toolInput.product };
    }

    case 'record_product_opportunity': {
      // Just return the data — the orchestrator collects it
      return { recorded: true, product: toolInput };
    }

    default:
      return { error: 'Unknown tool' };
  }
}

// ── Main product scout function ──────────────────────────────
export async function runProductScout({ niche = null, maxProducts = 10, onProgress = null } = {}) {
  const nicheContext = niche
    ? `Focus specifically on: ${niche}`
    : 'Research broadly across all dropshipping niches — health, home, beauty, pets, fitness, kitchen, self-care, tech accessories';

  const systemPrompt = `You are a ruthless product scout for a dropshipping intelligence operation.

Your mission: Find ${maxProducts} product opportunities where:
- Buyer demand is REAL and measurable
- Seller competition is WEAKER than expected
- The product can be shown visually in under 3 seconds
- Gross margin is strong after sourcing + shipping
- The market has more buyers than active sellers

${nicheContext}

Use your search tools aggressively. Search for:
1. Trending products on TikTok, Instagram, and Amazon
2. Competition levels (how many sellers, how strong are their listings)
3. Pricing data (source cost vs. retail price = margin)
4. Buyer demand signals (search volume, social engagement)

PRIME DIRECTIVE: Do NOT return obvious saturated products. Find inefficient markets where buyers exist but strong sellers don't.

After researching, use record_product_opportunity to save each product with honest scoring.
Scoring rules:
- demandScore: 1-10 (higher = more buyer demand)
- competitionScore: 1-10 (LOWER IS BETTER — 10 means totally saturated)
- marginScore: 1-10 (higher = better profit potential)
- launchSpeedScore: 1-10 (higher = faster to start selling)
- attentionCostScore: 1-10 (LOWER IS BETTER — 10 means very expensive to get eyeballs)
- visualHookStrength: 1-10 (can this product hook someone in 3 seconds of video?)

Record all ${maxProducts} products before finishing.`;

  const messages = [
    {
      role: 'user',
      content: `Run a full product opportunity scan. Find ${maxProducts} products with high demand, low competition, and strong margins. Research thoroughly, then record each product using the record_product_opportunity tool. Be ruthless — only find real gaps, not obvious saturated markets.`,
    },
  ];

  const products = [];
  let continueLoop = true;

  while (continueLoop) {
    if (onProgress) onProgress(`Researching products... (found ${products.length} so far)`);

    const response = await client.messages.create({
      model:      config.anthropic.model,
      max_tokens: config.anthropic.maxTokens,
      system:     systemPrompt,
      tools:      PRODUCT_TOOLS,
      messages,
    });

    // Add assistant turn
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

        if (block.name === 'record_product_opportunity' && result.product) {
          products.push(result.product);
          if (onProgress) onProgress(`Recorded product: ${result.product.name} (${products.length}/${maxProducts})`);
        }

        toolResults.push({
          type:        'tool_result',
          tool_use_id: block.id,
          content:     JSON.stringify(result),
        });
      }

      messages.push({ role: 'user', content: toolResults });

      // Stop if we have enough products
      if (products.length >= maxProducts) continueLoop = false;
    } else {
      continueLoop = false;
    }
  }

  return products;
}
