import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""One-shot: publish privacy policy + terms of service to GitHub Pages."""
sys.path.insert(0, r"C:\Users\integ\Documents\Claude\Projects\ShipStack")
from integrations import landing_pages as lp

BIZ = "Integrity Products USA"
EMAIL = "support@integrityproductsusa.com"
PHONE = "945-312-6709"
SITE = "https://integrityproductsusa.com"

STYLE = """<style>
* { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',system-ui,sans-serif; }
body { background:#f7f8fa; color:#181c23; }
.page { max-width:720px; margin:0 auto; background:#fff; min-height:100vh; padding:38px 30px 60px; }
h1 { font-size:30px; margin-bottom:6px; }
.updated { color:#8a94a2; font-size:13px; margin-bottom:26px; }
h2 { font-size:19px; margin:26px 0 10px; }
p, li { font-size:15px; color:#3a4150; line-height:1.7; margin-bottom:12px; }
ul { padding-left:22px; margin-bottom:12px; }
.contact { background:#f2faf9; border-radius:12px; padding:16px 18px; margin-top:30px; font-size:14.5px; }
a { color:#06897c; }
</style>"""

PRIVACY = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Privacy Policy — {BIZ}</title>{STYLE}</head><body><div class="page">
<h1>Privacy Policy</h1><p class="updated">Last updated: July 22, 2026</p>
<p>{BIZ} ("we", "us") operates online product stores. This policy explains what
information we collect when you visit our pages or buy from us, and how we use it.</p>
<h2>What we collect</h2>
<ul>
<li><b>Order information:</b> your name, email, phone number, and shipping address — collected securely by Stripe when you check out. We use it to fulfill and ship your order.</li>
<li><b>Payment information:</b> handled entirely by Stripe. Your card number never touches our servers.</li>
<li><b>Basic site data:</b> our pages are static and do not use tracking cookies or analytics scripts.</li>
</ul>
<h2>How we use it</h2>
<ul>
<li>To process, ship, and track your order (we share your shipping details with our fulfillment partners solely to deliver your package).</li>
<li>To respond when you contact support.</li>
<li>To meet legal, tax, and fraud-prevention obligations.</li>
</ul>
<h2>What we never do</h2>
<p>We do not sell, rent, or trade your personal information. We share it only with the
service providers needed to complete your order (payment processing and shipping).</p>
<h2>Data retention & your rights</h2>
<p>Order records are kept as required for tax and accounting purposes. You may request a copy
of your data or ask us to delete information we're not legally required to keep by emailing us.</p>
<h2>Children</h2>
<p>Our stores are not directed at children under 13 and we do not knowingly collect their information.</p>
<div class="contact"><b>Contact us</b><br>
{BIZ}<br>Email: <a href="mailto:{EMAIL}">{EMAIL}</a><br>Phone: {PHONE}</div>
</div></body></html>"""

TERMS = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Terms of Service — {BIZ}</title>{STYLE}</head><body><div class="page">
<h1>Terms of Service</h1><p class="updated">Last updated: July 22, 2026</p>
<p>These terms apply when you buy from a {BIZ} store page. By placing an order you agree to them.</p>
<h2>Orders & payment</h2>
<p>All payments are processed securely by Stripe. Prices are in U.S. dollars. We may cancel and
fully refund any order we cannot fulfill.</p>
<h2>Shipping</h2>
<p>Orders are processed in 1-2 business days. Typical delivery is 7-15 days with a tracking
number provided. Delivery estimates are not guarantees; carrier delays can occur.</p>
<h2>Returns & refunds</h2>
<p>Unused items in original condition may be returned within 30 days of delivery. Email
<a href="mailto:{EMAIL}">{EMAIL}</a> to start a return. Refunds are issued to the original
payment method once the return is confirmed. Items damaged in transit are replaced or refunded
in full — send us a photo within 7 days of delivery.</p>
<h2>Product information</h2>
<p>We work to keep photos, descriptions, and pricing accurate. Colors may vary slightly by screen.
If we make an error in pricing or description, your remedy is a full refund of the affected order.</p>
<h2>Limitation of liability</h2>
<p>To the fullest extent permitted by law, our total liability for any claim related to an order
is limited to the amount you paid for that order. Nothing in these terms limits rights you have
under applicable consumer-protection law.</p>
<h2>Governing law</h2>
<p>These terms are governed by the laws of the State of Texas, USA.</p>
<h2>Changes</h2>
<p>We may update these terms; the version posted at the time of your order applies to that order.</p>
<div class="contact"><b>Questions?</b><br>
{BIZ}<br>Email: <a href="mailto:{EMAIL}">{EMAIL}</a><br>Phone: {PHONE}</div>
</div></body></html>"""

ok1 = lp.upload_text("legal/privacy.html", PRIVACY, "legal: privacy policy")
ok2 = lp.upload_text("legal/terms.html", TERMS, "legal: terms of service")
base = lp.ensure_pages_enabled()
print(f"privacy: {ok1} -> {base}/legal/privacy.html")
print(f"terms:   {ok2} -> {base}/legal/terms.html")
