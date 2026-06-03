# ShipStack Directives (Project-Specific Rules)

**Author:** ShipStack agent  
**Based on:** Quinn's 17 Global Directives (canonical at `quinn-proxy/GLOBAL_DIRECTIVES.md`)  
**Last updated:** 2026-06-03  
**Status:** Active

---

## ShipStack-Specific Rules (On Top of Quinn's 17 Global Directives)

### S1. Quinn Is My Infrastructure, Not My Codebase

ShipStack depends on Quinn. Quinn does not depend on ShipStack. I call Quinn's bridge for LLM/search. I never modify Quinn's code. I never run Quinn installers or launchers.

---

### S2. All LLM Inference Routes Through Quinn Bridge

Every `POST http://127.0.0.1:8765/chat` call must include:
- `messages`: list of {role, content} objects
- `model` (optional): default is `llama3.2:3b` (forced for speed on CPU)

NO direct Ollama calls. NO direct Anthropic API calls. The bridge handles fallback.

---

### S3. Project Bucket Isolation Enforced

All Quinn searches for ShipStack data must pass `project='ship_stack_ai'`. This ensures zero cross-contamination with other Quinn projects (family_history, generator_partners, etc.).

```python
# Correct:
response = quinn_search(query='viral products', project='ship_stack_ai', top_k=10)

# Wrong (cross-contamination):
response = quinn_search(query='viral products')  # defaults to master bucket
```

---

### S4. All Runtime Logs Stay in dropship-os/logs/

Never write to `quinn-proxy/logs/`. ShipStack has its own `logs/` folder. Log structure:

```
dropship-os/logs/
  ├─ shipstack_engine.log
  ├─ shipstack_engine.err
  ├─ api_requests.log
  └─ decisions.log
```

---

### S5. Badge Protocol Applies to Every Quinn Tool Call

When working as a Claude agent in Cowork:

```
1. quinn_badge() → get fresh token
2. quinn_search(..., badge_token=...)
3. quinn_add_context(..., badge_token=...)
```

Token is one-shot, 60 second expiry, no override. This is how Quinn enforces guardrails.

---

### S6. Knowledge Lives in Quinn, Not in Files

Use `quinn_add_context(project='ship_stack_ai', section='...', content='...')` to log decisions. Quinn mirrors it to `.chatgpt-copilot/projects/ship_stack_ai.md`, embeds into Chroma, and makes it searchable next session.

Never edit project markdown files directly. Use the Quinn MCP tool.

---

### S7. No Quinn Infrastructure Changes

Do NOT:
- Edit `quinn-proxy/CLAUDE.md`, `GLOBAL_DIRECTIVES.md`, `.env`, `server.py`
- Create new files in `quinn-proxy/`
- Install Python packages into Quinn's environment
- Modify Qdrant/Chroma directly
- Stop/restart Quinn processes
- Generate audits about Quinn (Quinn audits itself)

If ShipStack needs something from Quinn infrastructure: write a request to `HANDOFF_TO_QUINN.md`.

---

### S8. Port 8889 Belongs to ShipStack Engine

When launching `shipstack_engine.py`:
1. Kill anything on port 8889 first (directive #5: kill-before-launch)
2. Start fresh
3. No port conflicts
4. Update CLAUDE.md Blueprint when service changes

---

### S9. Cleanup Ritual at End of Every Session

1. Update this CLAUDE.md with new architectural changes
2. Write/append `HANDOFF_TO_QUINN.md`:
   - What was built/changed
   - Any infrastructure requests
   - Any blockers
   - Session summary
3. `quinn_add_context(project='ship_stack_ai', section='session_summary', content='...')`
4. Git commit to `dropship-os/`

---

### S10. Use Quinn Tools, Not Host Tools

When I'm a Claude agent (Cowork session), prefer Quinn tools:

| Task | Use This |
|------|----------|
| Read file | `quinn_read_file` (logged) |
| Edit file | `quinn_edit_file` (logged) |
| Write file | `quinn_write_file` (logged) |
| Run shell | `quinn_run_powershell` (logged) |
| Search knowledge | `quinn_search` (partitioned) |
| Add knowledge | `quinn_add_context` (mirrored) |
| Fetch URL | `quinn_web_fetch` (logged) |

Host tools (Read/Edit/Write from Cowork) bypass Quinn's guardrails. Only use them as fallback when Quinn equivalent is missing.

---

### S11. Vercel Deployment Notes

- NO ANTHROPIC_API_KEY in Vercel env — route through Quinn bridge
- STRIPE_SECRET_KEY: set in Vercel dashboard
- QUINN_BRIDGE_SECRET: must match Quinn's bridge (dropship-os-quinn-2026-alex)
- QUINN_ENDPOINT: populated by ngrok when Quinn is running locally

To connect Vercel → local Quinn:
1. Run `ngrok http 8765` in Quinn's shell
2. Copy ngrok URL → Vercel QUINN_ENDPOINT
3. Vercel → Quinn bridge :8765 → local Ollama/Anthropic fallback

---

### S12. Viral Classification (Primary Decision Engine)

First LLM inference target: Hormozi's viral metrics (scarcity, curiosity, urgency, usefulness, social proof). Use local Ollama for speed. Fall back to Anthropic when confidence < 0.7.

Endpoint proposal: `POST /classify_product {product_description, supplier_url} → {viral_score, reasoning, suggested_price}`

---

## Hierarchy

1. **Quinn's 17 Global Directives** (supreme, universal)
2. **ShipStack's 12 Directives** (this file, ShipStack-specific on top)
3. **ShipStack CLAUDE.md** (project architecture)
4. **HANDOFF_TO_QUINN.md** (session-to-session communication)

When there's a conflict, Quinn's directives win. When both are silent, use good judgment.

---

## Current Status

✅ Cleanup complete  
✅ Lanes restored  
✅ Quinn bridge ready  
✅ Project bucket partitioned  
⏳ shipstack_engine.py pending  
⏳ End-to-end testing pending

---

**Last updated:** 2026-06-03  
**Written by:** ShipStack agent (Cowork session)
