// ============================================================
// ROI Product Finder — Live Market Scan API
// Vercel Serverless Function: /api/scan
//
// To activate live scanning, add these env vars in Vercel:
//   SERPAPI_KEY   → https://serpapi.com (100 free searches/mo)
//   RAPIDAPI_KEY  → https://rapidapi.com (AliExpress product data)
//
// Without keys, returns curated product database.
// With keys, performs real-time market scans.
// ============================================================

const CURATED_PRODUCTS = [
  { id:1, name:"Silicone Pet Deshedding Glove", category:"pet", supplierPrice:1.20, retailBest:12.99, amazonPrice:12.99, ebayPrice:9.99, tiktokPrice:11.99, shipping:3.50, monthlyVolume:49000, trendScore:8.5, roiScore:9.2, competition:"low", viral:"high", isNew:true, isTopPick:true, topChannels:["TikTok","Pinterest","Reddit"], description:"Silicone glove that removes pet hair while petting.", winRate:"78% profitable in week 1", tags:["impulse","pet","viral","proven"], supplierSource:"AliExpress", emoji:"🐾" },
  { id:2, name:"Peeling Exfoliating Face Serum", category:"beauty", supplierPrice:4.50, retailBest:24.99, amazonPrice:22.99, ebayPrice:18.99, tiktokPrice:24.99, shipping:2.50, monthlyVolume:38000, trendScore:9.0, roiScore:9.0, competition:"medium", viral:"high", isNew:true, isTopPick:true, topChannels:["TikTok","Pinterest","Instagram Reels"], description:"Peeling serum with visible results on video.", winRate:"Organic reach engine via demo content", tags:["beauty","before-after","viral","high-margin"], supplierSource:"AliExpress", emoji:"💄" },
  { id:3, name:"Anti-Snoring Mouthpiece Device", category:"wellness", supplierPrice:7.00, retailBest:34.99, amazonPrice:34.99, ebayPrice:24.99, tiktokPrice:32.99, shipping:2.00, monthlyVolume:29000, trendScore:7.5, roiScore:8.8, competition:"low", viral:"medium", isNew:false, isTopPick:true, topChannels:["Reddit","Email","Native/Taboola"], description:"Solves sleep problem for 45M+ Americans.", winRate:"Strong advertorial performer", tags:["health","evergreen","problem-solver"], supplierSource:"AliExpress", emoji:"😴" },
  { id:5, name:"Magnetic Hair Clips Set (6pc)", category:"fashion", supplierPrice:2.50, retailBest:15.99, amazonPrice:13.99, ebayPrice:10.99, tiktokPrice:15.99, shipping:2.00, monthlyVolume:89000, trendScore:9.5, roiScore:9.1, competition:"low", viral:"high", isNew:true, isTopPick:true, topChannels:["TikTok","Instagram Reels","Pinterest"], description:"$217M GMV on TikTok Shop. 42,000 units/day.", winRate:"Currently exploding — move fast", tags:["viral","trending","tiktok-winner","fashion"], supplierSource:"AliExpress", emoji:"✨" },
  { id:7, name:"Rhythmic Breathing Sleep Koala", category:"wellness", supplierPrice:12.00, retailBest:44.99, amazonPrice:44.99, ebayPrice:34.99, tiktokPrice:44.99, shipping:4.50, monthlyVolume:41000, trendScore:9.8, roiScore:9.4, competition:"low", viral:"high", isNew:true, isTopPick:true, topChannels:["TikTok","YouTube Shorts","Reddit"], description:"Viral US 2026. Anxiety + sleep — huge emotional pull.", winRate:"Fastest growing wellness item Q1 2026", tags:["viral-2026","trending","emotional","wellness"], supplierSource:"AliExpress", emoji:"🐨" }
];

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json');

  const { category = 'all', minMargin = 50, maxCost = 50, minRoi = 7 } = req.query;
  const SERPAPI_KEY = process.env.SERPAPI_KEY;
  const RAPIDAPI_KEY = process.env.RAPIDAPI_KEY;

  // ── LIVE MODE: Real API Scanning ──────────────────────────
  if (SERPAPI_KEY && RAPIDAPI_KEY) {
    try {
      const keywords = getCategoryKeywords(category);
      const results = [];

      for (const keyword of keywords.slice(0, 3)) {
        // 1. Get Amazon price via SerpAPI Google Shopping
        const googleRes = await fetch(
          `https://serpapi.com/search.json?engine=google_shopping&q=${encodeURIComponent(keyword)}&api_key=${SERPAPI_KEY}`
        );
        const googleData = await googleRes.json();
        const amazonResult = googleData.shopping_results?.[0];

        if (!amazonResult) continue;

        // 2. Get AliExpress price via RapidAPI
        const aliRes = await fetch(
          `https://aliexpress-datahub.p.rapidapi.com/item_search?q=${encodeURIComponent(keyword)}&sort=SALE_PRICE_ASC`,
          { headers: { 'x-rapidapi-host': 'aliexpress-datahub.p.rapidapi.com', 'x-rapidapi-key': RAPIDAPI_KEY } }
        );
        const aliData = await aliRes.json();
        const aliResult = aliData.result?.resultList?.[0];

        if (!aliResult) continue;

        const retailPrice = parseFloat(amazonResult.price?.replace(/[$,]/g, '')) || 0;
        const supplierPrice = parseFloat(aliResult.item?.sku?.def?.promotionPrice || aliResult.item?.sku?.def?.price) || 0;
        const shipping = 3.50;

        if (retailPrice <= 0 || supplierPrice <= 0) continue;

        const margin = ((retailPrice - supplierPrice - shipping) / retailPrice) * 100;
        if (margin < minMargin || supplierPrice > maxCost) continue;

        results.push({
          name: amazonResult.title?.slice(0, 50),
          supplierPrice,
          retailBest: retailPrice,
          amazonPrice: retailPrice,
          shipping,
          margin: margin.toFixed(1),
          profit: (retailPrice - supplierPrice - shipping).toFixed(2),
          roiScore: calculateRoiScore(margin, keyword),
          source: 'live-scan',
          amazonUrl: amazonResult.link,
          aliUrl: aliResult.item?.itemDetailUrl
        });
      }

      if (results.length > 0) {
        return res.status(200).json({ mode: 'live', count: results.length, products: results });
      }
    } catch (err) {
      console.error('Live scan error:', err.message);
      // Fall through to curated data
    }
  }

  // ── CURATED MODE: Research-backed database ─────────────────
  let products = CURATED_PRODUCTS.filter(p => {
    const margin = ((p.retailBest - p.supplierPrice - p.shipping) / p.retailBest) * 100;
    const catOk = category === 'all' || p.category === category;
    const marginOk = margin >= parseInt(minMargin);
    const costOk = p.supplierPrice <= parseInt(maxCost);
    const roiOk = p.roiScore >= parseFloat(minRoi);
    return catOk && marginOk && costOk && roiOk;
  });

  return res.status(200).json({
    mode: 'curated',
    message: SERPAPI_KEY ? 'Live scan failed — returning curated data' : 'Add SERPAPI_KEY + RAPIDAPI_KEY env vars to enable live scanning',
    count: products.length,
    products
  });
};

function getCategoryKeywords(category) {
  const map = {
    pet: ['pet grooming glove', 'dog car seat cover', 'cat toy interactive'],
    beauty: ['face roller skincare', 'exfoliating serum', 'bath scrubber'],
    home: ['solar garden lights', 'essential oil diffuser', 'LED plant grow light'],
    fitness: ['resistance band set', 'posture corrector', 'massage gun'],
    wellness: ['anti snoring device', 'sleep aid weighted', 'back massager'],
    fashion: ['magnetic hair clip', 'mini crossbody bag', 'phone case'],
    tech: ['wireless charger pad', 'smart wifi plug', 'portable power bank'],
    kitchen: ['electric lunch box', 'insulated tumbler', 'bottle warmer']
  };
  return map[category] || Object.values(map).flat().slice(0, 8);
}

function calculateRoiScore(margin, keyword) {
  let score = 6.0;
  if (margin > 70) score += 2.0;
  else if (margin > 50) score += 1.0;
  if (keyword.includes('pet') || keyword.includes('beauty')) score += 0.5;
  return Math.min(score, 9.9).toFixed(1);
}
