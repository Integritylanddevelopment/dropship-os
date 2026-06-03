// ============================================================
// WEB SEARCH MODULE — Free & paid search integrations
// ============================================================

import axios from 'axios';
import * as cheerio from 'cheerio';
import { config } from '../config.js';

const delay = (ms) => new Promise(r => setTimeout(r, ms));

// ── DuckDuckGo Search (free, no API key needed) ─────────────
export async function searchDuckDuckGo(query, maxResults = 8) {
  try {
    // DuckDuckGo Instant Answer API
    const ddgRes = await axios.get('https://api.duckduckgo.com/', {
      params: { q: query, format: 'json', no_html: 1, skip_disambig: 1 },
      timeout: 8000,
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; ResearchBot/1.0)' },
    });

    const results = [];
    const data = ddgRes.data;

    // Pull abstract
    if (data.Abstract) {
      results.push({ title: data.Heading || query, snippet: data.Abstract, url: data.AbstractURL });
    }

    // Pull related topics
    if (data.RelatedTopics) {
      for (const topic of data.RelatedTopics.slice(0, maxResults - 1)) {
        if (topic.Text) {
          results.push({ title: topic.Text.split(' - ')[0] || '', snippet: topic.Text, url: topic.FirstURL || '' });
        }
      }
    }

    // If DDG gave us very little, fall back to HTML scrape
    if (results.length < 3) {
      const htmlResults = await searchDuckDuckGoHTML(query, maxResults);
      return htmlResults.length > results.length ? htmlResults : results;
    }

    return results.slice(0, maxResults);
  } catch (err) {
    // Fallback to HTML search
    try {
      return await searchDuckDuckGoHTML(query, maxResults);
    } catch {
      return [{ title: query, snippet: `Research data for: ${query}`, url: '' }];
    }
  }
}

// ── DuckDuckGo HTML Scrape Fallback ─────────────────────────
async function searchDuckDuckGoHTML(query, maxResults = 8) {
  try {
    await delay(1000);
    const res = await axios.get('https://html.duckduckgo.com/html/', {
      params: { q: query },
      timeout: 10000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html',
      },
    });

    const $ = cheerio.load(res.data);
    const results = [];

    $('.result__body').each((i, el) => {
      if (i >= maxResults) return false;
      const title   = $(el).find('.result__title').text().trim();
      const snippet = $(el).find('.result__snippet').text().trim();
      const url     = $(el).find('.result__url').text().trim();
      if (title || snippet) results.push({ title, snippet, url });
    });

    return results;
  } catch {
    return [];
  }
}

// ── SerpAPI Search (higher quality, requires key) ───────────
export async function searchSerpAPI(query, engine = 'google', maxResults = 10) {
  if (!config.serpApi?.apiKey || config.serpApi.apiKey === 'YOUR_SERP_API_KEY') {
    return searchDuckDuckGo(query, maxResults);
  }

  try {
    const res = await axios.get('https://serpapi.com/search', {
      params: { q: query, api_key: config.serpApi.apiKey, engine, num: maxResults },
      timeout: 10000,
    });

    return (res.data.organic_results || []).map(r => ({
      title: r.title || '',
      snippet: r.snippet || '',
      url: r.link || '',
    }));
  } catch {
    return searchDuckDuckGo(query, maxResults);
  }
}

// ── Fetch Page Content ───────────────────────────────────────
export async function fetchPageContent(url, maxChars = 3000) {
  try {
    await delay(800);
    const res = await axios.get(url, {
      timeout: 8000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
      },
    });

    const $ = cheerio.load(res.data);
    $('script, style, nav, footer, header, aside').remove();
    const text = $('body').text().replace(/\s+/g, ' ').trim();
    return text.slice(0, maxChars);
  } catch {
    return '';
  }
}

// ── Unified Search (auto-selects best available) ─────────────
export async function search(query, maxResults = 8) {
  await delay(config.search?.delayMs || 1000);
  return searchDuckDuckGo(query, maxResults);
}

// ── Multi-query Search (runs several queries, combines) ──────
export async function multiSearch(queries, maxPerQuery = 5) {
  const results = [];
  for (const q of queries) {
    const res = await search(q, maxPerQuery);
    results.push(...res.map(r => ({ ...r, query: q })));
    await delay(1200);
  }
  return results;
}

// ── Format search results into a readable context string ─────
export function formatSearchResults(results) {
  return results
    .filter(r => r.snippet || r.title)
    .map((r, i) => `[${i + 1}] ${r.title}\n${r.snippet}\n${r.url ? 'URL: ' + r.url : ''}`)
    .join('\n\n');
}
