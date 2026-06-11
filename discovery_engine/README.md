# ShipStack Discovery Engine

## Status (latest verify run)

Source                    Tier        Items  Time     Notes
Reddit (Pullpush)         downstream  5      11.95s   WORKS. Time grew due to per-host throttle floor.
Google Trends RSS         downstream  10     0.78s    WORKS. Switched to /trending/rss?geo=US.
YouTube search            downstream  0      2.16s    fetch OK 922KB, Wiz-framework JSON, parser stale.
Amazon Movers             downstream  0      1.41s    fetch OK 341KB, zg-grid markup changed.
Etsy /trending            downstream  0      5.08s    403 anti-bot. Selenium required.
Etsy keyword              downstream  0      4.75s    same 403 wall.
Pinterest keyword         downstream  0      1.48s    fetch OK 898KB, React render, regex misses.
CJdropshipping            upstream    0      6.94s    /elastic-search v2 returns 404 (moved).
Spocket                   upstream    0      1.08s    URL hits Webflow marketing page.

2 of 9 sources working end-to-end (Reddit + Google Trends).

## Throttle / batch jitter (2026-06-07)

signals/_common.py exposes throttle(host_hint). Every fetch() invokes it.
- Per-host floor: 1.5s minimum between consecutive hits to the same host.
- Global floor: 0.3s minimum between any two hits.
- Jitter: random.uniform(0.4, 1.6)s added per call.
- Retries: 1.5^attempt + random 0.2-0.8s backoff.

pipeline.collect_all_signals random.shuffle()s subreddit/keyword/amazon-category
lists each run so we do not always hit hosts in the same sequence.

Effect: Reddit smoke test went from ~0.7s to ~12s (per-host pace), should hit
far fewer anti-bot blocks during full runs.

## Architecture

discovery_engine/
  signals/                  downstream collectors
    _common.py              fetch + throttle + buyer-intent phrases
    reddit_signals.py       WORKS via Pullpush
    google_trends.py        WORKS via RSS
    youtube_signals.py      fetch OK, parser stale
    amazon_movers.py        fetch OK, parser stale
    etsy_trending.py        blocked 403
    pinterest_signals.py    fetch OK, parser stale
  suppliers/
    cj_dropshipping.py      endpoint moved
    spocket.py              wrong endpoint
  scoring/
    buyer_intent.py         20+ purchase-intent phrase weights
    trend_velocity.py       3/7/14-day rolling counts
    content_score.py        visual/problem/curiosity/giftable hooks
    margin_calc.py          landed cost + margin + break-even CPA
    clusterer.py            Jaccard token-set clustering
    risk_filters.py         HARD AVOID gates
    opportunity_report.py   weighted score + pursue/test/watch/skip/reject
  pipeline.py               orchestrator (12-step workflow)
  cli.py                    python -m discovery_engine.cli {run|suppliers|verify}

## Spec compliance

12 spec workflow steps + ranking weights 30/20/20/15/10/5 + AVOID filters
(legal/shipping/saturation/explainability/margin) implemented and unit-tested.
Rejects CBD, replicas, glass/oversized, lithium battery, industrial-spec
products correctly while passing clean candidates as watch.

## Next session priorities

1. YouTube parser: regex needs the actual JSON-escaped quotes from videoRenderer
   or compactVideoRenderer blocks.
2. Amazon Movers parser: zg-grid-general-faceout containers, _p13n-zg-list-grid
   classes. Update ASIN+title regex.
3. Pinterest parser: pins live in __PWS_INITIAL_PROPS__ blob.
   Parse resource_response.data list.
4. CJ endpoint refresh: try /api/restful/v1/product/list or scrape consumer
   site /list/*.html search results.
5. Etsy + Spocket: need real browser or paid scraper. Document blocked.