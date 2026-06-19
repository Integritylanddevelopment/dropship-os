---
name: shipstack_brain_commands
title: ShipStack Brain Commands
scope: project
memory_type: procedural
pinned: true
tags: ["brain", "commands", "shipstack"]
last_updated: 2026-06-19
---

# ShipStack Brain Commands

## Key Difference: Project Scope

Always specify `project="ship_stack_ai"` when querying:

```python
# Correct — ShipStack brain
quinn_search("product status", project="ship_stack_ai", top_k=3)
quinn_chat("What's next for ShipStack?")

# Wrong — would search Quinn brain instead
quinn_search("product status")  # ❌ defaults to Quinn
```

## Command Reference

### quinn_search — Find specific info
```python
quinn_search(
    query="what you're looking for",
    project="ship_stack_ai",  # REQUIRED for ShipStack
    top_k=3
)
```

### quinn_chat — Ask questions
```python
quinn_chat(
    message="your question",
)
```

### quinn_add_context — Feed knowledge (optional)
```python
quinn_add_context(
    content="knowledge to save",
    project="ship_stack_ai"
)
```

## Project Navigation

- **Product questions** → search "ShipStack product architecture"
- **Status updates** → search "ShipStack pipeline status"
- **Team coordination** → search "ShipStack team roles"
- **Integration with Quinn** → search "ShipStack ALIEN Quinn bridge"

---

**Remember:** Always include `project="ship_stack_ai"` to stay in ShipStack brain scope.
