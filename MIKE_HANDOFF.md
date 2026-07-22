# Handoff to OpenAI Mike — Social Distribution

**From:** Claude (EAGLE) / Alex
**Date:** 2026-07-22
**Your job:** Take APPROVED ad collateral and get it in front of people. Posting, scheduling, platform accounts, channel growth. You do NOT create ads, touch pricing, or modify the pipeline — that side is handled.

**The workflow in one line:** Claude's pipeline finds products and builds 10 graded ads each → Alex reviews in Mission Control and hits ✓ Approve → approved ads appear in YOUR feed → you post them → every ad links to that product's one sales page → sales auto-fulfill. Your entire world is the approved feed.

**Human review page** (what Alex sees, so you know where your feed comes from): http://127.0.0.1:8889/approved

---

## The one API you need

```
GET http://127.0.0.1:8889/api/library/approved
```

Returns only collateral Alex has personally approved:

```json
{
  "products": [
    {
      "product_id": "bird_house",
      "title": "Mini Walk-in Greenhouse With PVC Cover",
      "retail_price": 142.99,
      "landing_url": "https://integritylanddevelopment.github.io/dropship-os/landing/bird_house.html",
      "payment_link": "https://buy.stripe.com/...",
      "approved_ads": [
        {
          "image_url": "https://raw.githubusercontent.com/.../cards/bird_house_v1.png",
          "headline": "Never deal with plants dying every winter again",
          "subline": "...",
          "grade": 88,
          "letter": "A",
          "approved_at": "2026-07-22T..."
        }
      ]
    }
  ]
}
```

## Hard rules

1. **Only post what this endpoint returns.** If it's not in the approved feed, it is still in review. Never pull from `/api/library` (that's the working pile).
2. **Every ad links to its product's `landing_url`.** All ads for one product → that product's ONE sales page. Never link anywhere else, never link the checkout directly.
3. **Post the ad copy as given.** `headline` = post title/hook, `subline` = description base. You may add platform-native hashtags/formatting, but don't rewrite the offer, price, or claims.
4. **Public identity:** business name **Integrity Products USA**, support email **support@integrityproductsusa.com**, phone **945-312-6709**. Never publish any other phone number.
5. **Grades:** A ads first. Post best-graded creative before lower grades.
6. Poll the endpoint before each posting session — ads get approved/pulled continuously, and pulled ads must stop being scheduled.

## Platform status (your to-do list)

| Platform | Status | Your action |
|----|----|----|
| Pinterest | App in TRIAL — Pinterest blocks production pins | Standard-access request submitted at developers.pinterest.com (app 1566237) — chase approval, then post via `POST http://127.0.0.1:8867/post/pinterest` `{title, description, image_url, link}` |
| TikTok | OAuth incomplete | Run `python scripts/tiktok_oauth.py` in this repo with Alex present, then videos post via :8867 |
| Instagram/Meta | No credentials | Create Meta app, fill META_* keys in `.env` |
| YouTube | Credentials ready | Needs product videos (Prometheus engine :8766 makes them) — coordinate before scheduling |

## Cadence playbook (already stored in this repo)

`agents/advisors/garyvee.json` + `kamil.json` — volume rules: 3+ posts/day per product while testing, kill weak products after 3 days/9 posts, double down when one hits. Read them; they're the strategy source of truth.

## Boundaries

- Work OUTSIDE `engines/`, `asset_machine/`, `discovery_engine/`, `integrations/` — those are the find-side and are actively maintained.
- Your natural home: `social_ai_agent/` posting/scheduling modules, or your own folder calling the HTTP APIs.
- Site domain **integrityproductsusa.com** is propagating to Vercel now (bought 2026-07-22); sales-page links in the feed update automatically when things move — always use the `landing_url` the API returns, never hardcode.

## Current state as you read this

- The approved feed is live and tested (1 approved ad in it right now: the greenhouse A-88).
- Pinterest posting endpoint works but Pinterest itself blocks pins until the Standard-access request is approved — your #1 chase item.
- Auto-fulfillment is armed: when your posts convert, orders ship themselves. Your posting volume is the faucet on the whole machine.
