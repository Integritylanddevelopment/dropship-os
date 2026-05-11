// ═══════════════════════════════════════════════════════════════
// Dropship OS — Stripe Webhook (Vercel Edge Function)
//
// Receives Stripe events the instant a payment succeeds.
// If Quinn bridge is running, forwards for immediate fulfillment.
// Local order monitor catches anything missed within 30 min.
//
// Setup (one time):
//   1. Stripe dashboard → Developers → Webhooks → Add endpoint
//      URL: https://dropship-os-gamma.vercel.app/api/webhook
//      Events: checkout.session.completed, payment_intent.succeeded
//   2. Copy the "Signing secret" (whsec_...) into Vercel env vars:
//      STRIPE_WEBHOOK_SECRET = whsec_...
// ═══════════════════════════════════════════════════════════════

export const config = { runtime: 'edge' };

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, stripe-signature',
};

export default async function handler(req) {
  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 200, headers: CORS });
  }

  if (req.method !== 'POST') {
    return json({ error: 'POST only' }, 405);
  }

  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  const stripeKey     = process.env.STRIPE_SECRET_KEY;

  if (!stripeKey) {
    return json({ error: 'STRIPE_SECRET_KEY not configured' }, 500);
  }

  // ── Verify Stripe signature ───────────────────────────────────────────────
  const sig  = req.headers.get('stripe-signature');
  const body = await req.text();

  if (webhookSecret && sig) {
    const valid = await verifyStripeSignature(body, sig, webhookSecret);
    if (!valid) {
      return json({ error: 'Invalid Stripe signature' }, 400);
    }
  }

  let event;
  try {
    event = JSON.parse(body);
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const eventType = event.type;
  console.log(`[Webhook] Event: ${eventType} — ${event.id}`);

  // ── Handle payment events ─────────────────────────────────────────────────
  if (eventType === 'checkout.session.completed' || eventType === 'payment_intent.succeeded') {
    const obj = event.data?.object ?? {};

    // Only process paid sessions
    if (eventType === 'checkout.session.completed' && obj.payment_status !== 'paid') {
      return json({ received: true, action: 'skipped_unpaid' });
    }

    // ── Forward to Quinn bridge for immediate fulfillment (if running) ──────
    const quinnEndpoint = process.env.QUINN_ENDPOINT;
    const quinnSecret   = process.env.QUINN_BRIDGE_SECRET;

    if (quinnEndpoint) {
      try {
        const headers = { 'Content-Type': 'application/json' };
        if (quinnSecret) headers['Authorization'] = `Bearer ${quinnSecret}`;

        const res = await fetch(`${quinnEndpoint}/fulfill`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ event_type: eventType, session: obj }),
          signal: AbortSignal.timeout(10000),
        });

        if (res.ok) {
          const result = await res.json();
          console.log(`[Webhook] Quinn fulfilled: ${JSON.stringify(result)}`);
          return json({ received: true, action: 'fulfilled_via_quinn', result });
        } else {
          console.warn(`[Webhook] Quinn returned ${res.status} — local monitor will catch this`);
        }
      } catch (e) {
        console.warn(`[Webhook] Quinn unreachable: ${e.message} — local monitor will catch this`);
      }
    }

    // Quinn not running — local 30-min poller will handle it
    return json({ received: true, action: 'queued_for_local_monitor' });
  }

  // Unhandled event type — acknowledge so Stripe stops retrying
  return json({ received: true, action: 'ignored', event_type: eventType });
}

// ── Stripe webhook signature verification (no external library needed) ───────
async function verifyStripeSignature(payload, sigHeader, secret) {
  try {
    const parts    = sigHeader.split(',').reduce((acc, part) => {
      const [k, v] = part.split('=');
      acc[k] = v;
      return acc;
    }, {});

    const timestamp = parts['t'];
    const signature = parts['v1'];
    if (!timestamp || !signature) return false;

    // Reject events older than 5 minutes
    const age = Math.floor(Date.now() / 1000) - parseInt(timestamp, 10);
    if (age > 300) return false;

    const signedPayload = `${timestamp}.${payload}`;
    const enc           = new TextEncoder();
    const keyData       = enc.encode(secret);
    const msgData       = enc.encode(signedPayload);

    const cryptoKey = await crypto.subtle.importKey(
      'raw', keyData, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
    );
    const sigBuffer  = await crypto.subtle.sign('HMAC', cryptoKey, msgData);
    const computed   = Array.from(new Uint8Array(sigBuffer))
      .map(b => b.toString(16).padStart(2, '0')).join('');

    return computed === signature;
  } catch {
    return false;
  }
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json' },
  });
}
