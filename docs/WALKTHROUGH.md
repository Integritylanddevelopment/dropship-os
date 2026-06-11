# ShipStack Pipeline Dashboard — Plain-English Walkthrough

**Last updated:** 2026-06-08
**For:** Alex (single-operator workflow)
**Lives at:** http://127.0.0.1:8891/
**Started by:** double-click `LAUNCH SHIPSTACK` on your desktop

This walkthrough explains every button and field you will see, in plain English, from the top of the page to the bottom. No jargon.

---

## The Pipeline Story (read this first)

The whole dashboard is built around one flow, in three tabs:

1. **Discovery** — robots crawl Reddit / Pinterest / YouTube / Google Trends every night. Each hot keyword becomes a "report" with a score and a recommended action.
2. **Decide** — you look at every report and tell ShipStack what to do: **Pursue** it, run a small **Test**, just **Watch**, or **Skip** it forever.
3. **Distribution** — for everything you marked Pursue or Test, ShipStack helps you scrape product images, make short videos, push them into a social-publishing queue, and (when accounts are connected) post them live.

A keyword goes through this start-to-finish: **discovery → decide → scrape → media gen → produced output → push to social → social ready → live**.

---

## HEADER (always visible at the top)

- **"ShipStack Pipeline"** — page title in orange.
- **"Run YYYY-MM-DD ... | N signals -> M reports | Xs"** — when the last discovery run happened, how many raw signals it grabbed, how many product reports it built, and how long it took.
- **"refresh"** — click to re-pull all data from the server. Use after long-running jobs (compile / publish) finish.

---

## TAB BAR (just under the header)

Three tabs. The numbers in parentheses tell you how many items live in each tab.

- **Discovery (N)** — N = number of reports in the last run.
- **Decide (N)** — N = number of reports still awaiting your call.
- **Distribution (N)** — N = number of reports you marked Pursue / Test.

Click a tab to switch. Tab state is session-only; refreshing the page reopens on Discovery.

---

## TAB 1 — DISCOVERY

A read-only snapshot of what the discovery robots found overnight.

### Signal Source bars
Horizontal bars, one per platform. The longer the bar, the more product signals came from that source. Tells you at a glance whether Reddit had the loudest week or whether Pinterest is heating up.

### Recommendation Pill Counts
Small color-coded labels:
- **PURSUE** (green) — model thinks this is worth real work.
- **TEST** (yellow) — promising but uncertain. Run a $20 ad first.
- **WATCH** (blue) — trending but not ready. Re-check in a week.
- **SKIP** (gray) — supplier or saturation problems. Move on.

Counts under each pill = how many reports fall in that bucket. Higher PURSUE counts = better discovery week.

### Stat strip (top right of section)
"X signals / Y reports / Z elapsed" — same numbers as the header, restated for context.

---

## TAB 2 — DECIDE

This is the only tab where you make calls. Every report in the last run shows up as a card, sorted highest score first.

### Card layout (one per product)

- **Product keyword** (big, top of card) — what the report is about.
- **Overall score** (bold, next to keyword) — 0.00 to 1.00. ShipStack's confidence this is a real opportunity. Above 0.50 = worth taking seriously.
- **Recommendation pill** — same color/label as the Discovery counts. The robot's suggested choice.
- **Sub-scores** (the small rows under the headline) — show *why* the score is what it is. Each is 0.00 to 1.00:
  - **demand** (demand_velocity) — how fast people are searching / posting about this. Higher = more momentum.
  - **intent** (buyer_intent) — how much of the chatter shows someone wanting to BUY (not just talk). Phrases like "where can I get" boost this.
  - **supply** (supplier_availability) — can ShipStack find suppliers? If 0, no real pursuit is possible.
  - **content** (content_potential) — how easy is it to make scroll-stopping videos. Visual products win here.
  - **satur** (low_saturation) — how empty the field is. Higher = fewer competitors already running ads.
  - **ship** (shipping_simplicity) — is the product small, light, non-fragile, no battery issues. Higher = simpler logistics.
  - **margin** — modeled gross margin if you sold at the suggested retail price. Higher = healthier unit economics.
- **Top sources** (bottom of card) — links to the actual Reddit threads / YouTube videos / Pinterest pins that triggered the report. Click to verify the trend is real.

### Decision buttons (one row per card)

- **PURSUE** — commit to this product. It flows into Distribution.
- **TEST** — run a small validation campaign first. Also flows into Distribution.
- **WATCH** — keep an eye on it, no work yet. Doesn't enter Distribution.
- **SKIP** — dismiss permanently. Doesn't enter Distribution.

You can change your mind any time by clicking a different button. Your last click wins.

### Detail modal (opens when you click "Detail" or any sub-score)

Pops a panel with everything the report knows:
- Full top-supplier list with unit cost, MOQ, shipping time, supplier URL.
- Full top-social-source list with the raw post URLs, scores, and any buyer-intent quotes the parser pulled.
- Raw sub-score breakdown with the exact numbers the model used.
- Sentiment / cluster tags if the model found recurring themes.

Click the X or press Escape to close.

---

## TAB 3 — DISTRIBUTION

Top-to-bottom, this tab is six stages. Each stage is a labeled panel.

### Stage 4 — SCRAPE

For every product you marked Pursue or Test, ShipStack will scrape collateral (images + caption snippets) from Pinterest, Reddit, YouTube.

Each scrape card shows:
- Product keyword + best supplier + price ($).
- Counts: N suppliers, M social hits, score.
- Status line if scrape ran: "scraped: N items, KB-size" plus a thumbnail preview.

Buttons:
- **Scrape collateral** — kicks off a background job. Button changes to "scraping..." with the job ID. Re-poll completes automatically.
- **Re-scrape** — appears once a scrape exists. Runs it again (overwrites cache).

### Stage 5 — MEDIA GEN (Prometheus)

Each scraped product becomes a folder tile in a grid. Click a tile to expand it.

Folder tile shows:
- Thumbnail of one scraped image.
- Product name.
- Item count + total size.

Expanded folder panel shows:
- Grid of every collateral item (images / videos / text cards).
- Each item has an X to delete it (asks for confirmation).
- **Add by URL** — paste a URL of another product image / TikTok / pin, ShipStack scrapes and adds it.
- **Upload file** — pick an image or video from your computer to add it directly.
- **Compile to Prometheus:** four platform buttons (**TT / IN / YO / PI**) — each compiles a vertical video for that platform (TikTok 1080x1920, Instagram Reels 1080x1920, YouTube Shorts 1080x1920, Pinterest 1000x1500). Click one; button shows job ID, then "done KB-size" when finished. Hover the finished button to see the video file path.

### Stage 5b — PRODUCED OUTPUT (new — for selecting which variants advance)

Sister panel to Media Gen but showing the OPPOSITE direction: finished videos sitting on disk, waiting for your sign-off.

Folder tile shows:
- Thumbnail of the first produced variant.
- Product name.
- "N produced" — how many platform mp4s exist for that product.

Expanded folder panel shows:
- A playable video card per variant. Click play to preview.
- **plat-badge** — TIKTOK / INSTAGRAM_REELS / YOUTUBE_SHORTS / PINTEREST.
- Dimensions, duration, file size.
- **"select for social" checkbox** under each video — tick the ones you actually want to publish.
- Below the video grid: the copy snippet (Hook, Caption, Hashtags) so you can sanity-check the text before pushing.
- **Push to social → (N)** button — sends every selected variant into the Social Ready queue. N updates live as you tick boxes. Disabled until you tick at least one.

After clicking Push to social, the items appear in Stage 6b below and the panel auto-expands.

### Stage 6 — SOCIAL PUSH (existing queue system)

The classic per-platform queueing view.

- **Platform row** (one per platform) — colored dot (green = connected, gray = not connected), platform name, **Connect** link (opens OAuth in new tab) if disconnected, queued-count badge.
- **Throttle line** — under each connected platform:
  - **Wk** — week number in your current rotation.
  - **N/M today** — posts published today out of the daily cap.
  - **debt** — engagement debt: comments/replies you owe before you're allowed to post again. ShipStack enforces a 1-comment-per-post minimum to keep platforms happy.
  - **mix:promo N/M** — how many of your last 5 posts were promotional. ShipStack blocks publishing if more than 1-in-5 is promo (avoids algorithmic shadow-banning).
  - **+1 eng** button — log one community engagement you did manually (comment, reply, like). Burns down the debt counter so you can post again.
- **Queue summary** — "N queued, M ready".
- **Push card** (one per chosen product with a media kit) — quick-queue buttons (TT / IG / YT / P). Click to add that platform variant to the queue. Button shows checkmark once queued.

### Stage 6b — SOCIAL READY (new — final sign-off before going live)

Items that survived your "Push to social" click in Stage 5b. Same folder layout as 5b.

Folder tile shows:
- Thumbnail.
- Product name.
- "N ready".

Expanded folder panel shows:
- One playable video card per item.
- Status pill: **queued** (default) / **selected_for_live** (you ticked the box) / **posted** (already published) / **held_no_credential** (platform not connected) / **queue_blocked** (throttle/mix rejected it) / **error**.
- **queue for live** checkbox — tick to mark for the next publish run. Greyed out with tooltip "Connect <platform> first" if the platform's OAuth isn't connected.
- **Publish live (N)** button — sends every ticked item through the social_push driver. Returns a summary: "Posted X, held Y, skipped Z, errors W". Items that go through become status=posted; items held for missing credentials revert to unselected so you can fix and retry.

### 7-day Calendar Strip

Below the social rows. Shows a planned mini-calendar for each platform (TikTok, Instagram, YouTube, Pinterest) for the next 7 days.

- Each row = one platform.
- Each cell = one day. Dots inside = scheduled pillar (color-coded): edu / problem-solution / behind-the-scenes / community / promotion.
- Empty cell = nothing scheduled that day.
- Hover a day for the list of pillars in plain text.
- **Regen** button — re-plans the 7 days for that platform based on your throttle settings and pillar mix rules.

Legend at the bottom maps each dot color to a pillar name.

---

## DETAIL MODAL (opens from Tab 2 detail clicks)

A pop-up overlay. Click anywhere outside the inner panel (or press Escape) to close.

Shows the full raw report for a product — every field the JSON has. Used when you need to dig into WHY a sub-score is what it is, or to copy a supplier URL.

---

## API ENDPOINTS (for debugging / scripting)

Everything the dashboard does is also exposed as plain JSON at `/api/...`. You can curl any of these.

| Endpoint | Method | What it does |
|---|---|---|
| `/api/latest-run` | GET | The full last discovery run (signals, reports, scores). |
| `/api/decisions` | GET / POST | Your Pursue/Test/Watch/Skip choices. POST `{kw, choice}` updates. |
| `/api/media-kits` | GET | Generated copy (hooks, captions, hashtags) per product. |
| `/api/generate-media` | POST | `{product_keyword}` -> generates a media kit. |
| `/api/social-status` | GET | Per-platform connect status + queued counts. |
| `/api/social-queue` | GET | Items in the social_push queue. |
| `/api/account-status` | GET | Throttle / debt / mix state per platform. |
| `/api/calendar` | GET | The 7-day plan per platform. |
| `/api/calendar/regenerate` | POST | `{platform, days}` -> re-plans. |
| `/api/log-engagement` | POST | `{platform, count}` -> burns down engagement debt. |
| `/api/queue-post` | POST | `{product_keyword, platform}` -> queues one post. |
| `/api/collateral/index` | GET | Map of product -> scraped collateral summary. |
| `/api/collateral/list?product_keyword=...` | GET | Items inside a product folder. |
| `/api/collateral/scrape` | POST | `{product_keyword}` -> kicks scrape job. |
| `/api/collateral/job/<id>` | GET | Status of a scrape job. |
| `/api/collateral/add` | POST | URL or multipart upload to add one item. |
| `/api/collateral/<slug>/<item_id>` | DELETE | Removes one collateral item. |
| `/api/collateral/compile` | POST | `{product_keyword, platform}` -> Prometheus video job. |
| `/api/produce-video` | POST | `{product_keyword, platform}` -> same as compile, alt path. |
| `/api/job/<id>` | GET | Status of a Prometheus job. |
| `/api/produced/list` | GET | Map of slug -> per-platform produced mp4 metadata. |
| `/api/produced/selections` | GET | Your current "select for social" ticks. |
| `/api/produced/select` | POST | `{product_keyword, platform, selected}` -> toggles one. |
| `/api/produced/push-to-social` | POST | `{product_keyword}` -> moves selected variants into Social Ready. |
| `/api/produced/file/<slug>/<filename>` | GET | Serves the actual mp4 / thumbnail (used by `<video>` tags). |
| `/api/social-ready/list` | GET | Items staged for live publishing. |
| `/api/social-ready/select` | POST | `{product_keyword, platform, item_id, selected}` -> queue-for-live toggle. |
| `/api/social-ready/publish` | POST | `{product_keyword}` -> push all selected items through social_push. |
| `/api/prometheus-health` | GET | Proxies Prometheus engine /health. |

---

## END-TO-END FLOW (numbered story)

1. ShipStack runs discovery overnight. You wake up to N new reports.
2. You open the dashboard. Discovery tab shows the headlines.
3. You switch to Decide. Reading top-down, you click **Pursue** on the obvious winners, **Test** on the iffy ones, **Skip** on the rest.
4. Open Distribution tab. Stage 4 shows your Pursue/Test products as scrape-ready cards. Click **Scrape collateral** on each one and let them run.
5. Stage 5 fills with folder tiles as scrapes finish. Open a folder, prune any bad images, then click **TT / IN / YO / PI** to compile platform-shaped videos via Prometheus.
6. Stage 5b populates with the finished mp4s. Preview each one in the browser; tick the "select for social" checkbox on the ones you like.
7. Click **Push to social →**. The selected variants move into Stage 6b.
8. Look at Stage 6: confirm the relevant platforms are connected (green dot). If not, click **Connect**. Watch the throttle line — if engagement debt is non-zero, click **+1 eng** for each comment you've actually done.
9. In Stage 6b, tick **queue for live** for every item ready to go. Disconnected platforms grey their boxes out — fix the connection or skip those.
10. Click **Publish live (N)**. ShipStack publishes everything queued through social_push. Read the summary; retry held items after fixing OAuth.
11. Refresh and check Stage 6b again — published items show **posted** status with a green tint.

That's a full day of solo dropshipping in one dashboard.
