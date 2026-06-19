---
name: shipstack_nomenclature
title: ShipStack Nomenclature
scope: project
memory_type: semantic
pinned: true
tags: ["nomenclature", "shipstack", "architecture"]
last_updated: 2026-06-19
---

# ShipStack Nomenclature

## Layer 1 — Machines & Models (inherited from Quinn)

| Machine | Models | Address | Role |
|---------|--------|---------|------|
| **PRIME** | llama3.2:3b, qwen2.5:7b, nomic-embed-text | 127.0.0.1:11434 | Quinn hub |
| **ALIEN** | qwen2.5-coder:7b (GPU), nomic-embed-text | 192.168.1.103:11434 | GPU code generation |
| **EAGLE** | Claude (Anthropic) | api.anthropic.com | Architecture, reasoning |

## Layer 2 — ShipStack Services

| Service | Port | Host | Purpose |
|---------|------|------|---------|
| ShipStack Engine | 8889 | PRIME | Product classification, SKU analysis |
| ShipStack Dashboard | 8890 | PRIME | Product UI |
| Social AI Agent | 8867 | PRIME | Content generation + posting |
| Prometheus Engine | 8766 | PRIME | Video production AI |
| Pipeline Dashboard | 8891 | PRIME | Pipeline visualization |

## Layer 3 — Project Scope

- **Project ID:** ship_stack_ai
- **Owner:** ShipStack team
- **Launcher:** LAUNCH_SHIPSTACK.pyw (separate from Quinn)
- **Brain scope:** Queries use project="ship_stack_ai"

## Layer 4 — Memory Types

| Type | Purpose |
|------|---------|
| **working** | Current sprint goals, status, next actions |
| **episodic** | Session events, what happened |
| **semantic** | Architecture, integrations, decisions |
| **procedural** | Workflows, automations, SOPs |
| **long_term** | Product strategy, roadmap |

---

**Rule:** ShipStack must not modify Quinn core files. Use separate launcher. Brain scope keeps projects isolated.
