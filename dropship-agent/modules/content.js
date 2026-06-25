// ============================================================
// MODULE: CONTENT STRATEGIST
// Generates content hooks, video scripts, piggybacking targets,
// UGC briefs, and platform-specific copy for each product
// ============================================================

import { config } from '../config.js';
import { search, formatSearchResults } from './web-search.js';

// Quinn bridge wrapper — mimics Anthropic SDK interface, routes through Quinn
function createQuinnClient() {
  return {
    messages: {
      async create(params) {
        const body = { ...params };
        const r = await fetch(`${config.quinn.bridgeUrl}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: AbortSignal.timeout(120000),
        });
        if (!r.ok) throw new Error(`Quinn bridge error: ${r.status}`);
        return r.json();
      }
    }
  };
}
const client = createQuinnClient();

// ── Tool Definitions ─────────────────────────────────────────
const CONTENT_TOOLS = [
  {
    name: 'research_viral_content',
    description: 'Search for currently viral content formats and hooks for a product category',
    input_schema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query to find viral content examples' },
      },
      required: ['query'],
    },
  },
  {
    name: 'find_piggyback_targets',
    description: 'Find viral creators and content to piggyback off of for a product niche',
    input_schema: {
      type: 'object',
      properties: {
        niche: { type: 'string', description: 'Product niche or category' },
      },
      required: ['niche'],
    },
  },
  {
    name: 'record_content_strategy',
    description: 'Record the complete content strategy for a product',
    input_schema: {
      type: 'object',
      properties: {
        productName:        { type: 'string' },
        primaryHook:        { type: 'string', description: 'The #1 best opening hook (first 3 seconds)' },
        hookFormats: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              format: { type: 'string' },
              hook:   { type: 'string' },
              angle:  { type: 'string' },
            },
          },
          description: 'Multiple hook variations ranked by viral potential',
        },
        tiktokScript:       { type: 'string', description: '15-30 second TikTok script' },
        pinterestCaption:   { type: 'string', description: 'Pinterest pin caption (SEO-optimized)' },
        redditPostTitle:    { type: 'string', description: 'Reddit post title that feels native' },
        emailSubjectLine:   { type: 'string', description: 'Email subject line for cold traffic' },
        ugcBrief:           { type: 'string', description: 'Brief for UGC creators to follow' },
        piggybackTargets:   { type: 'array', items: { type: 'string' }, description: 'Creators or trending formats to piggyback off' },
        hashtagStack:       { type: 'array', items: { type: 'string' }, description: 'Optimal hashtag mix' },
        contentCalendar: {
          type: 'object',
          properties: {
            week1: { type: 'string' },
            week2: { type: 'string' },
            week3: { type: 'string' },
            week4: { type: 'string' },
          },
          description: '30-day organic content plan',
        },
        viralCopyFormula:   { type: 'string', description: 'The Gary V formula for this product: document, piggyback, or create' },
        estimatedOrganicReach: { type: 'string', description: 'Estimated reach if 3 posts/day for 30 days' },
      },
      required: ['productName', 'primaryHook', 'tiktokScript'],
    },
  },
];

// ── Tool Execution ────────────────────────────────────────────
async function executeTool(name, input) {
  switch (name) {
    case 'research_viral_content': {
      const queries = [
        `${input.query} viral TikTok 2026 hook`,
        `${input.query} content format most views`,
      ];
      const results = [];
      for (const q of queries) {
        const r = await search(q, 5);
        results.push(...r);
      }
      return { results: formatSearchResults(results) };
    }

    case 'find_piggyback_targets': {
      const queries = [
        `${input.niche} TikTok creator 1 million views 2026`,
        `${input.niche} viral video format trending`,
        `${input.niche} Instagram reel most shared`,
      ];
      const results = [];
      for (const q of queries.slice(0, 2)) {
        const r = await search(q, 5);
        results.push(...r);
      }
      return { results: formatSearchResults(results) };
    }

    case 'record_content_strategy':
      return { recorded: true, strategy: input };

    default:
      return { error: 'Unknown tool' };
  }
}

// ── Main: Generate content strategy for a product ────────────
export async function generateContentStrategy(product, onProgress = null) {
  const productName = product.name || product;
  const category    = product.category || 'consumer product';
  const hook        = product.bestContentHook || '';
  const platform    = product.bestPlatform || 'TikTok';

  const systemPrompt = `You are a viral content strategist and Gary Vaynerchuk-trained media operator.

Your philosophy:
- Find what is ALREADY working and remix it with this product
- Document, don't create — capture real moments
- Piggyback off existing viral trends rather than building from scratch
- Post 2-3x daily minimum during ramp phase
- Organic first, paid amplification only on proven winners
- The first 3 seconds are everything — lose them and you lose everyone

Product being strategized: "${productName}" (${category})
Known best hook: "${hook}"
Best platform: ${platform}

Your mission: Build the complete content playbook for launching this product organically to its first 1,000 sales.

Use your tools to:
1. Research currently viral content formats in this niche
2. Find specific creators and trends to piggyback off
3. Record the complete strategy using record_content_strategy

Be extremely specific — give actual scripts, real hook lines, real hashtags. Not templates.`;

  const messages = [
    {
      role: 'user',
      content: `Build the complete organic content launch strategy for: ${productName}. Research what viral content already exists in this space, find piggyback targets, then record the full strategy. Give me real scripts, not templates.`,
    },
  ];

  let strategy = null;
  let continueLoop = true;

  while (continueLoop) {
    if (onProgress) onProgress(`Generating content strategy for ${productName}...`);

    const response = await client.messages.create({
      model:      config.quinn.model,
      max_tokens: config.quinn.maxTokens,
      system:     systemPrompt,
      tools:      CONTENT_TOOLS,
      messages,
    });

    messages.push({ role: 'assistant', content: response.content });

    if (response.stop_reason === 'end_turn') {
      continueLoop = false;
    } else if (response.stop_reason === 'tool_use') {
      const toolResults = [];

      for (const block of response.content) {
        if (block.type !== 'tool_use') continue;
        const result = await executeTool(block.name, block.input);

        if (block.name === 'record_content_strategy' && result.strategy) {
          strategy = result.strategy;
          if (onProgress) onProgress(`Content strategy recorded for ${productName}`);
          continueLoop = false;
        }

        toolResults.push({ type: 'tool_result', tool_use_id: block.id, content: JSON.stringify(result) });
      }

      if (toolResults.length > 0) {
        messages.push({ role: 'user', content: toolResults });
      }
    } else {
      continueLoop = false;
    }
  }

  return strategy || { productName, primaryHook: hook, tiktokScript: 'Not generated', error: 'Strategy generation incomplete' };
}

// ── Batch: Generate strategies for multiple products ─────────
export async function generateBatchStrategies(products, onProgress = null) {
  const strategies = [];
  for (const product of products) {
    const strategy = await generateContentStrategy(product, onProgress);
    strategies.push({ product: product.name || product, strategy });
  }
  return strategies;
}

// ── Quick: Generate hooks only (fast, no tool loop) ──────────
export async function generateQuickHooks(productName, count = 5) {
  const prompt = `Generate ${count} viral content hooks for: "${productName}"

Return JSON array only:
[
  { "format": "problem_solution", "hook": "<3-second opener>", "platform": "TikTok" },
  { "format": "before_after", "hook": "<3-second opener>", "platform": "TikTok" },
  { "format": "social_proof", "hook": "<3-second opener>", "platform": "Instagram" },
  { "format": "curiosity", "hook": "<3-second opener>", "platform": "TikTok" },
  { "format": "educational", "hook": "<3-second opener>", "platform": "Pinterest" }
]

Rules:
- Each hook must be 10 words or less
- Must create instant curiosity or recognize a pain in 3 seconds
- No generic hooks — be product-specific`;

  const r = await client.messages.create({
    model: config.quinn.model,
    max_tokens: 600,
    messages: [{ role: 'user', content: prompt }],
  });

  try {
    const cleaned = r.content[0].text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    return JSON.parse(cleaned);
  } catch {
    return [];
  }
}
