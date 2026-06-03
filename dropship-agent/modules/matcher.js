// ============================================================
// MATCHER — Pairs products to best channels via Claude
// ============================================================

import Anthropic from '@anthropic-ai/sdk';
import { config } from '../config.js';
import { scoreMatches, labelWinners } from './scorer.js';

const client = new Anthropic({ apiKey: config.anthropic.apiKey });

// ── Tool definitions ─────────────────────────────────────────
const MATCH_TOOLS = [
  {
    name: 'record_match',
    description: 'Record a product-channel match with analysis',
    input_schema: {
      type: 'object',
      properties: {
        product:            { type: 'string' },
        channel:            { type: 'string' },
        matchScore:         { type: 'number', description: '1-10 match quality score' },
        estimatedCAC:       { type: 'string', description: 'e.g. $12-18' },
        estimatedNetMargin: { type: 'string', description: 'e.g. 35%' },
        contentStrategy:    { type: 'string', description: 'Specific content approach for this combo' },
        firstTestAction:    { type: 'string', description: 'Exact first step to test this match' },
        whyItWorks:         { type: 'string', description: 'Why this specific product + channel combo wins' },
        riskLevel:          { type: 'string', enum: ['low', 'medium', 'high'] },
        priority:           { type: 'string', enum: ['launch-now', 'test-soon', 'watch-monitor'] },
      },
      required: ['product', 'channel', 'matchScore', 'whyItWorks'],
    },
  },
];

// ── Main matcher function ────────────────────────────────────
export async function runMatcher({ products, channels, onProgress = null } = {}) {
  if (!products?.length || !channels?.length) {
    return { matches: [], labels: {} };
  }

  // First do algorithmic scoring for all combinations
  const scoredProducts = products.map(p => ({
    ...p,
    overallScore: p.overallScore || 6,
  }));
  const scoredChannels = channels.map(c => ({
    ...c,
    overallScore: c.overallScore || 6,
  }));

  const algorithmicMatches = scoreMatches(scoredProducts, scoredChannels);

  // Then use Claude to analyze and enhance the TOP matches with strategic insight
  const topCombos = getTopCombinations(products, channels, 15);

  const systemPrompt = `You are a direct response media strategist and product launch specialist.

You will receive a list of products and channels that have been pre-scored. Your job is to analyze the best product-channel matches and provide:
1. A specific content strategy for each match
2. The exact first test action (specific and actionable)
3. Estimated CAC and net margin
4. Why this specific combination wins

Be ruthless. Only record matches that are genuinely efficient. Focus on:
- Products that can be shown visually on video channels
- Products with impulse buy potential on fast-scroll platforms
- High-margin products that can absorb CAC on paid channels
- Products with strong organic content hooks for zero-cost channels

Use record_match for the top 10 best product-channel combinations.`;

  const productList = products.slice(0, 8).map(p =>
    `• ${p.name} | Price: $${p.sellingPrice || '?'} | Cost: $${p.landedCost || '?'} | Hook: ${p.bestContentHook || 'N/A'} | Demand: ${p.demandScore}/10 | Competition: ${p.competitionScore}/10`
  ).join('\n');

  const channelList = channels.slice(0, 8).map(c =>
    `• ${c.name} | CPM: $${c.cpm || 0} | CAC: ~$${c.avgCac || '?'} | Audience Quality: ${c.audienceQualityScore}/10 | Best For: ${(c.bestFor || []).slice(0, 3).join(', ')}`
  ).join('\n');

  const messages = [
    {
      role: 'user',
      content: `Analyze these products and channels. Find the best 10 matches.

PRODUCTS:
${productList}

CHANNELS:
${channelList}

For each match, give a specific content strategy and exact first test action. Record all 10 using record_match.`,
    },
  ];

  const aiMatches  = [];
  let continueLoop  = true;
  let iterations    = 0;

  while (continueLoop && iterations < 10) {
    iterations++;
    if (onProgress) onProgress(`Analyzing product-channel matches... (${aiMatches.length} found)`);

    const response = await client.messages.create({
      model:      config.anthropic.model,
      max_tokens: config.anthropic.maxTokens,
      system:     systemPrompt,
      tools:      MATCH_TOOLS,
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

        if (block.name === 'record_match' && block.input) {
          aiMatches.push(block.input);
          if (onProgress) onProgress(`Matched: ${block.input.product} → ${block.input.channel}`);
        }

        toolResults.push({
          type:        'tool_result',
          tool_use_id: block.id,
          content:     JSON.stringify({ recorded: true }),
        });
      }

      messages.push({ role: 'user', content: toolResults });

      if (aiMatches.length >= 10) continueLoop = false;
    } else {
      continueLoop = false;
    }
  }

  // Merge AI matches with algorithmic scores
  const enrichedMatches = aiMatches.map(aiMatch => {
    const algoMatch = algorithmicMatches.find(
      m => m.product === aiMatch.product && m.channel === aiMatch.channel
    );
    return {
      ...algoMatch,
      ...aiMatch,
      matchScore: aiMatch.matchScore || algoMatch?.matchScore || 6,
    };
  });

  // If AI didn't produce enough, fill with top algorithmic matches
  if (enrichedMatches.length < 5) {
    for (const am of algorithmicMatches.slice(0, 10 - enrichedMatches.length)) {
      if (!enrichedMatches.find(m => m.product === am.product && m.channel === am.channel)) {
        enrichedMatches.push({ ...am, priority: 'test-soon', riskLevel: 'medium' });
      }
    }
  }

  const sortedMatches = enrichedMatches.sort((a, b) => (b.matchScore || 0) - (a.matchScore || 0));
  const labels        = labelWinners(
    products.map(p => ({ ...p, overallScore: p.overallScore || 6 })),
    channels.map(c => ({ ...c, overallScore: c.overallScore || 6 })),
    sortedMatches
  );

  return { matches: sortedMatches, labels };
}

// ── Helper: get top combinations to analyze ──────────────────
function getTopCombinations(products, channels, maxCombos) {
  const combos = [];
  for (const p of products.slice(0, 6)) {
    for (const c of channels.slice(0, 6)) {
      combos.push({ product: p, channel: c });
    }
  }
  return combos.slice(0, maxCombos);
}
