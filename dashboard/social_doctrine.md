# ShipStack Social Engine — Operating Doctrine

**Owner:** Alex Alexander
**Set:** 2026-06-07
**Optimize for:** account trust, community participation, content quality
**Do NOT optimize for:** avoiding detection

---

## Core principles

1. **Earn trust before asking for anything.** First 2-4 weeks: teach / demonstrate / document / entertain / answer questions. Avoid constant links, constant CTAs, repetitive sales messaging, daily launch announcements. Ratio: 80% value, 15% brand story, 5% promotion.
2. **Become part of the community.** Reply to comments, answer questions, congratulate people, share useful resources, participate in discussions. **Rule:** for every post published, perform 3-5 meaningful engagements. Not "Great post!" — real responses.
3. **Build content pillars.** Each product gets 4-6 pillars (e.g. industry education / tutorials / founder journey / customer stories / industry news / behind-the-scenes). Prevents the account sounding like an advertisement.
4. **Increase volume gradually.** Week 1: 1 post/day. Week 2: 2 posts/day. Week 3: 2-3 posts/day. Week 4+: normal cadence. Never jump from 0 to 10/day.
5. **Use platform-native content.** Same idea, different format. TikTok → short video. Instagram → reels + carousel. LinkedIn → professional insight. X → discussion thread. Do NOT blast one post everywhere.

---

## Daily community interaction (per account)

- **Posting:** publish scheduled content.
- **Engagement:** reply to all comments within 24h; like relevant comments; answer questions.
- **Discovery:** engage with 10-20 relevant industry posts.
- **Monitoring:** track follower growth, reach, saves, shares, comments.

---

## Trust signals — staged buildout

- **Week 1:** complete profile, website link, logo, banner.
- **Week 2:** pinned post, about post, FAQ content.
- **Week 3:** product demos, case studies, real testimonials only.
- **Week 4:** community discussions, UGC, collaborations.

---

## Content mix

| Type                 |  %  |
|----------------------|-----|
| Education            | 40% |
| Problem / solution   | 20% |
| Behind-the-scenes    | 15% |
| Community engagement | 15% |
| Product promotion    | 10% |

Keeps the account useful instead of turning into a digital billboard.

---

## Forbidden — never do

- Auto-DM strangers.
- Mass follow / unfollow.
- Repost identical content repeatedly.
- Manufacture engagement.
- Use fake testimonials.
- Invent customers.
- Pretend to be a person if it's a brand account.
- Spam links into conversations.

---

## Long-term success metrics (60-90 day window)

Not posting frequency — community formation. Track:

- Comments per post
- Shares per post
- Saves per post
- Profile visits
- Returning commenters

Platforms reward this because they want users talking to each other, not coupons shouted into the void.

---

## Enforcement (to be baked into social_push.py)

1. Daily cap per account follows the Week 1-4 ramp. Account-age computed from `account_created_at` in social_queue state.
2. Reject `queue_post` requests with `status: "throttled"` when daily cap hit.
3. Track `last_5_post_types` per account; reject when content-mix ratio breaks (e.g. 3rd promo in last 5 posts → reject as `mix_violation`).
4. Require 3+ engagement actions logged since last post before allowing the next post on the same account.
5. Surface live throttle state on dashboard stage 6: "Today: 1/2 posts allowed; mix balance OK; engagement debt: 0".
