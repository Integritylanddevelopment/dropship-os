// ═══════════════════════════════════════════════════════════════
// Dropship OS — Supplier Auto-Search API (Vercel Edge Function)
//
// Automatically searches AliExpress for a product and returns
// real product listings with URLs, images, prices, and ratings.
// Used by the Supplier Wizard to auto-fill product data for
// content generation — no manual browsing required.
//
// GET /api/supplier?product=Silicone+Dog+Collar&supplier=ali
//
// Flow:
//   Supplier Wizard → GET /api/supplier → AliExpress open search
//   → returns top 3 listings → wizard auto-fills product URL
//   → "Push to Production" sends to Prometheus with real link
// ═══════════════════════════════════════════════════════════════

export const config = { runtime: 'edge' };

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

export default async function handler(req) {
  if (req.method === 'OPTIONS') return new Response(null, { status: 200, headers: CORS });

  const url = new URL(req.url);
  const product  = url.searchParams.get('product') || '';
  const supplier = url.searchParams.get('supplier') || 'ali';

  if (!product) return json(400, { error: 'product param required' });

  // ── AliExpress open product search (no API key needed) ────────
  // Uses AliExpress public search page scraped via fetch
  if (supplier === 'ali') {
    const results = await searchAliExpress(product);
    return json(200, { supplier: 'aliexpress', product, results });
  }

  // ── Zendrop — no public search API, return deep link ─────────
  if (supplier === 'zendrop') {
    const q = encodeURIComponent(product);
    return json(200, {
      supplier: 'zendrop',
      product,
      results: [{
        title: product,
        url: `https://app.zendrop.com/find-products?search=${q}`,
        affiliate_url: `https://app.zendrop.com/find-products?search=${q}`,
        image: null,
        price: null,
        source: 'zendrop_search',
        note: 'Zendrop requires login — copy your product ID from the dashboard after searching'
      }]
    });
  }

  // ── CJ Dropshipping search ────────────────────────────────────
  if (supplier === 'cj') {
    const q = encodeURIComponent(product);
    const results = await searchCJ(product);
    return json(200, { supplier: 'cj', product, results });
  }

  return json(400, { error: 'Unknown supplier. Use: ali, zendrop, cj' });
}

// ── AliExpress product search ─────────────────────────────────
async function searchAliExpress(product) {
  const q = encodeURIComponent(product);

  // AliExpress affiliate deep search URL — works without API key
  // Returns search results page; we extract structured data from it
  const searchUrl = `https://www.aliexpress.com/wholesale?SearchText=${q}&SortType=total_transy_desc&shipCountry=US`;

  try {
    const res = await fetch(searchUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
      },
      signal: AbortSignal.timeout(8000),
    });

    if (!res.ok) return fallbackAliResults(product);

    const html = await res.text();

    // Extract product data from AliExpress JSON embedded in page
    const products = parseAliExpressProducts(html, product);
    if (products.length > 0) return products;

    return fallbackAliResults(product);
  } catch {
    return fallbackAliResults(product);
  }
}

function parseAliExpressProducts(html, productName) {
  const results = [];

  // AliExpress embeds product data in window._dida_config_ or mods JSON
  const jsonMatch = html.match(/"mods":\{"itemList":\{"content":(\[.*?\])/s)
    || html.match(/window\.__INIT_DATA__\s*=\s*(\{.*?"itemList".*?\});/s);

  if (jsonMatch) {
    try {
      let items;
      if (jsonMatch[1].startsWith('[')) {
        items = JSON.parse(jsonMatch[1]);
      } else {
        const data = JSON.parse(jsonMatch[1]);
        items = data?.mods?.itemList?.content || [];
      }

      for (const item of items.slice(0, 5)) {
        const id = item.productId || item.itemId || item.item?.itemId;
        const title = item.title?.displayTitle || item.name || item.item?.title || productName;
        const price = item.prices?.salePrice?.minPrice || item.item?.sku?.def?.promotionPrice || null;
        const image = item.image?.imgUrl || item.item?.image?.imgUrl;
        const sales = item.trade?.tradeDesc || '';

        if (id) {
          results.push({
            title: String(title).replace(/<[^>]+>/g, '').trim(),
            url: `https://www.aliexpress.com/item/${id}.html`,
            affiliate_url: `https://s.click.aliexpress.com/e/_aliexpress_item_${id}`,
            image: image ? (image.startsWith('//') ? 'https:' + image : image) : null,
            price: price ? `$${price}` : null,
            sales: sales || null,
            source: 'aliexpress_search',
            product_id: String(id),
          });
        }
      }
    } catch {
      // parsing failed, fall through
    }
  }

  // Regex fallback — extract item IDs from href links
  if (results.length === 0) {
    const itemPattern = /\/item\/(\d{10,}?)\.html/g;
    const imgPattern = /"imgUrl":"(\/\/[^"]+\.jpg[^"]*)"/g;
    const pricePattern = /"minPrice":"?(\d+\.?\d*)"?/g;

    const ids = [];
    let m;
    while ((m = itemPattern.exec(html)) !== null && ids.length < 5) {
      if (!ids.includes(m[1])) ids.push(m[1]);
    }

    const imgs = [];
    while ((m = imgPattern.exec(html)) !== null && imgs.length < 5) {
      imgs.push('https:' + m[1].replace(/\\u002F/g, '/'));
    }

    const prices = [];
    while ((m = pricePattern.exec(html)) !== null && prices.length < 5) {
      prices.push('$' + m[1]);
    }

    for (let i = 0; i < Math.min(ids.length, 3); i++) {
      results.push({
        title: productName + (i > 0 ? ` (Option ${i + 1})` : ''),
        url: `https://www.aliexpress.com/item/${ids[i]}.html`,
        affiliate_url: `https://www.aliexpress.com/item/${ids[i]}.html`,
        image: imgs[i] || null,
        price: prices[i] || null,
        source: 'aliexpress_regex',
        product_id: ids[i],
      });
    }
  }

  return results;
}

function fallbackAliResults(product) {
  const q = encodeURIComponent(product);
  return [{
    title: product,
    url: `https://www.aliexpress.com/wholesale?SearchText=${q}&SortType=total_transy_desc`,
    affiliate_url: `https://www.aliexpress.com/wholesale?SearchText=${q}&SortType=total_transy_desc`,
    image: null,
    price: null,
    source: 'search_fallback',
    note: 'Auto-search returned no results — click to search manually on AliExpress'
  }];
}

// ── CJ Dropshipping public search ────────────────────────────
async function searchCJ(product) {
  const q = encodeURIComponent(product);
  try {
    const res = await fetch(
      `https://cjdropshipping.com/product-list.html?searchTextList=${q}`,
      {
        headers: { 'User-Agent': 'Mozilla/5.0' },
        signal: AbortSignal.timeout(6000),
      }
    );
    if (!res.ok) return cjFallback(product);
    const html = await res.text();
    const ids = [];
    const m = html.match(/\/product\/[a-zA-Z0-9\-]+\.html/g) || [];
    for (const href of m.slice(0, 3)) {
      const pid = href.replace('/product/', '').replace('.html', '');
      if (!ids.includes(pid)) ids.push(pid);
    }
    if (ids.length === 0) return cjFallback(product);
    return ids.map((pid, i) => ({
      title: product + (i > 0 ? ` (Option ${i + 1})` : ''),
      url: `https://cjdropshipping.com/product/${pid}.html`,
      affiliate_url: `https://cjdropshipping.com/product/${pid}.html`,
      image: null,
      price: null,
      source: 'cj_search',
      product_id: pid,
    }));
  } catch {
    return cjFallback(product);
  }
}

function cjFallback(product) {
  const q = encodeURIComponent(product);
  return [{
    title: product,
    url: `https://cjdropshipping.com/search?q=${q}`,
    affiliate_url: `https://cjdropshipping.com/search?q=${q}`,
    image: null,
    price: null,
    source: 'cj_fallback',
  }];
}

function json(status, data) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}
