# How To Use ShipStack Mission Control

## Starting it

Double-click **"ShipStack Mission Control"** on your Desktop.
Wait about 30 seconds. Your browser opens the control screen automatically.

If the browser doesn't open, go to: **http://127.0.0.1:8889/**

## Using it

1. (Optional) Type a niche in the box — like "pet accessories" or "yard and garden". Leave it blank to scan general trending products.
2. Make sure **Pinterest** is checked.
3. Push the big **RUN PIPELINE** button.
4. Watch the six steps light up: Check services → Discover → Pick winners → Generate cards → Publish images → Post to social.
5. When it finishes (about 2 minutes), you'll see your product picks with their scorecards, and a table showing what posted where.

Every run: finds trending products, scores them (demand, buyer intent, margin, content potential), makes branded product card images, publishes the images, and tries to post them to your social accounts.

## One thing only YOU can fix (5 minutes)

**Pinterest is blocking real posts right now.** Your Pinterest developer app is in
"Trial" mode. Trial apps cannot create real pins — Pinterest rejects them.

To fix it:
1. Go to https://developers.pinterest.com/apps
2. Log in with the Pinterest account you used before
3. Open your app (ID 1566237)
4. Click **"Request Standard Access"** and fill in the short form
5. Pinterest usually approves in a few days

The moment they approve, the same RUN button starts posting real pins. No code changes needed.

## Also worth doing (makes product picks much better)

**Reddit data is stale.** Reddit blocks anonymous access now, so we're using an
old mirror. To get LIVE trending data:
1. Go to https://www.reddit.com/prefs/apps
2. Click "create another app", pick "script" type, name it "ShipStack"
3. Tell Claude the client ID and secret it shows you — I'll wire them in

## What's already working

- One-button pipeline, start to finish
- Product discovery + scoring (Google Trends live, Reddit via mirror)
- Product card image generation
- Image publishing to your GitHub (public URLs)
- YouTube posting (ready — needs videos from the video engine)
- Honest results: if a post fails, the table tells you exactly why

## What's waiting on credentials

| Platform | Status |
|----------|--------|
| Pinterest | Blocked by Trial mode — request Standard access (above) |
| YouTube | Ready — posts when a product video exists |
| TikTok | Needs OAuth — run `python scripts/tiktok_oauth.py` |
| Instagram | No Meta credentials configured yet |
