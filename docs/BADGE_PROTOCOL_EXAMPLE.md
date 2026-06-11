# Badge Protocol — Usage Examples

This document shows how agents **must** use the ShipStack badge system for every tool call.

---

## Pattern Overview

Every tool call follows this 3-step pattern:

```
1. CALL shipstack_badge.get_badge()     — Get one-shot token + rules
2. EXECUTE the tool                      — Read, write, compute, call API
3. CALL shipstack_badge.log_action()    — Write result to JSONL (sync)
```

The Badge is the cost of admission. Without it, the agent doesn't know the current rules.

---

## Example 1: Decision Engine Scoring

```python
from shipstack_badge import get_badge, log_action
from decision_engine import DecisionEngine, Product

# STEP 1: Get badge (every tool call)
badge = get_badge()
token = badge['token']
issued_at = badge['issued_at']

print(f"Badge token: {token}")
print(f"Valid for 60 seconds until: {badge['expires_at']}")

# STEP 2: Execute the tool
engine = DecisionEngine()
product = Product(
    id="product-123",
    title="Premium Pet Collar",
    price=5.50,
    supplier="zendrop",
    reviews=250,
    rating=4.8,
    niche="pet accessories"
)

decision = engine.decide(product)

# STEP 3: Log the action (synchronous — blocks until written)
log_result = log_action(
    token=token,
    issued_at_iso=issued_at,
    tool_name="decision_engine_score",
    target="product-123",
    action="score",
    result=f"Scored {decision.score:.2f} ({decision.competition_level} competition)",
    success=True
)

print(f"Logged to line: {log_result['line_number']}")
```

---

## Example 2: HTTP Request with Badge Header

```bash
# STEP 1: Get badge
BADGE=$(curl http://localhost:8889/badge)
TOKEN=$(echo $BADGE | jq -r '.token')
ISSUED=$(echo $BADGE | jq -r '.issued_at')

echo "Got token: $TOKEN"
echo "Valid until: $(echo $BADGE | jq -r '.expires_at')"

# STEP 2: Call protected endpoint with badge in Authorization header
RESPONSE=$(curl -X POST http://localhost:8889/api/decide \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Badge-Issued-At: $ISSUED" \
  -H "Content-Type: application/json" \
  -d '{
    "products": [
      {"id": "p1", "title": "Widget", "price": 5.99, "niche": "home kitchen"}
    ]
  }')

echo "Response: $RESPONSE"

# STEP 3: Service logs the action automatically (we don't see it, but it happens)
# → Entry written to shipstack_actions.jsonl
# → Next action blocked until write completes
```

---

## Example 3: Product Research Tool

```python
from shipstack_badge import get_badge, log_action
from product_research import ProductResearcher

# STEP 1: Get badge
badge = get_badge()

# STEP 2: Execute research
researcher = ProductResearcher()
products = researcher.research(
    search_term="pet collars",
    suppliers=["zendrop", "autods", "aliexpress"],
    limit=10
)

# STEP 3: Log
log_action(
    token=badge['token'],
    issued_at_iso=badge['issued_at'],
    tool_name="product_research_search",
    target="pet collars",
    action="research",
    result=f"Found {len(products)} products",
    success=True
)

for product in products:
    print(f"{product['title']} (${product['price']:.2f}) — {product['reviews']} reviews")
```

---

## Example 4: Analytics Query

```python
from shipstack_badge import get_badge, log_action
from analytics_engine import AnalyticsEngine

# STEP 1: Get badge
badge = get_badge()

# STEP 2: Compute metrics
analytics = AnalyticsEngine()
metrics = analytics.get_summary_metrics(hours=24)

# STEP 3: Log
log_action(
    token=badge['token'],
    issued_at_iso=badge['issued_at'],
    tool_name="analytics_summary",
    target="shipstack_actions.jsonl",
    action="query",
    result=f"Computed {metrics['total_actions']} actions at {metrics['success_rate']:.1%} success",
    success=True
)

print(f"Total actions: {metrics['total_actions']}")
print(f"Success rate: {metrics['success_rate']:.1%}")
```

---

## Key Behaviors

### Token Expiry (60 seconds)
```python
from shipstack_badge import get_badge, validate_token
import time

badge = get_badge()
print(f"Token: {badge['token']}")

# Token is valid NOW
assert validate_token(badge['token'], badge['issued_at']) == True

# Wait 65 seconds...
time.sleep(65)

# Token is EXPIRED
assert validate_token(badge['token'], badge['issued_at']) == False

# Must get a NEW badge for the next tool call
new_badge = get_badge()
```

### Action Logging (Synchronous)
```python
from shipstack_badge import get_badge, log_action

badge = get_badge()

# log_action BLOCKS until written to JSONL
result = log_action(
    token=badge['token'],
    issued_at_iso=badge['issued_at'],
    tool_name="my_tool",
    target="/api/endpoint",
    action="execute",
    result="Success",
    success=True
)

# At this point, the entry is GUARANTEED to be in shipstack_actions.jsonl
# Next tool call can now begin
```

---

## JSONL Log Format

Every action logged as one JSON per line:

```json
{
  "timestamp": "2026-06-03T18:30:00Z",
  "badge_token": "badge-1_abc123def456...",
  "badge_issued_at": "2026-06-03T18:29:00Z",
  "tool_name": "decision_engine_score",
  "target": "product-123",
  "action": "score",
  "result": "Scored 0.76 (high competition)",
  "success": true
}
```

---

## Integration Points

### In ShipStack Engine (/api/decide endpoint)
```python
@app.route("/api/decide", methods=["POST"])
@require_badge  # Decorator checks Authorization header
def decide():
    data = request.get_json()
    
    # Get badge from headers (already validated by decorator)
    token = request.headers.get("Authorization", "Bearer ")[7:]
    issued_at = request.headers.get("X-Badge-Issued-At", "")
    
    # Execute decision engine
    engine = DecisionEngine()
    decisions = [engine.decide(p) for p in products]
    
    # Log the action
    log_action(
        token=token,
        issued_at_iso=issued_at,
        tool_name="shipstack_engine_decide",
        target="/api/decide",
        action="score",
        result=f"Scored {len(decisions)} products",
        success=True
    )
    
    return jsonify({"decisions": decisions})
```

### In Dashboard (monitoring logs)
```python
def get_recent_actions(limit=30):
    actions = []
    with open("logs/shipstack_actions.jsonl") as f:
        for line in f:
            actions.append(json.loads(line))
    return actions[-limit:]
```

---

## Rules Enforced by Badge

Every badge includes the current rule snapshot:

```python
badge = get_badge()
print(badge['rules_summary'])

# Output:
# {
#   "lane": "dropship-os/ only",
#   "quinn_bridge": "http://localhost:8765",
#   "ports": {"engine": 8889, "prometheus": 8766, ...},
#   "no_anthropic_keys": true,
#   "action_logging": true,
#   ...
# }
```

This ensures every tool call knows the current rules without re-reading files.

---

## What NOT to Do

❌ **Call tools without a badge token**
```python
# WRONG — no badge
from product_research import ProductResearcher
researcher = ProductResearcher()
products = researcher.research("pet collars")  # No logging, no auth
```

❌ **Reuse expired tokens**
```python
# WRONG — token from 2 minutes ago
badge = old_badge  # Expired!
log_action(token=badge['token'], ...)  # Will fail
```

❌ **Log after tool call without blocking**
```python
# WRONG — async logging (race condition)
result = log_action_async(...)  # Returns immediately
next_tool_call()  # May execute before log is written!
```

❌ **Call without checking rules**
```python
# WRONG — tool ignores current directives
if should_call_anthropic_directly():  # Maybe old code!
    response = requests.post("https://api.anthropic.com/...")  # LEAK!
```

---

## Correct Pattern (Always)

✅ **Get badge → Execute → Log (sync)**
```python
badge = get_badge()          # ALWAYS (per tool call)
result = do_tool_work()      # Execute
log_action(...)              # ALWAYS (sync)
```

✅ **In HTTP endpoints: require_badge decorator**
```python
@app.route("/api/endpoint", methods=["POST"])
@require_badge  # Checks Authorization header, validates token
def my_endpoint():
    # Authorization already verified
    token = request.headers.get("Authorization")[7:]
    # Use token in log_action call
```

✅ **Badge tokens are short-lived**
```python
# Get fresh token for every tool call
badge = get_badge()  # New token, 60-second TTL
# Use immediately
# Don't cache or reuse
```

---

## Summary

The badge system ensures:
- ✅ Every agent knows current rules (before tool use)
- ✅ Every action is logged (synchronously)
- ✅ Tokens are short-lived (can't be replayed)
- ✅ Authorization is enforced (decorator pattern)
- ✅ Quinn always sees every action (JSONL is source of truth)

**Every tool call: Get badge → Execute → Log (sync)**

