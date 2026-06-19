#!/usr/bin/env python3
"""
ShipStack Bootstrap Agent — Context Loader

Loads agent into Cowork with full ShipStack project context.
Queries the brain (ChromaDB/Qdrant) for live snapshots.
Agent absorbs full context in ~2-3 seconds.

Usage:
  python bootstrap.py --project ship_stack_ai
"""

import sys

def print_header(text):
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")

def main():
    print_header("SHIPSTACK BRAIN SNAPSHOT — NAVIGATION GUIDE")

    print("""
You are a Claude agent in the ShipStack project.

THE BRAIN IS YOUR SOURCE OF TRUTH (Qdrant + ChromaDB).

Everything you need to know lives in the brain. You access it using:
  → quinn_search(query, project="ship_stack_ai")     : Find specific information
  → quinn_chat(message)     : Ask questions (auto-searched)

FOLLOW THIS SEQUENCE:

""")

    queries = [
        ("1. CURRENT GOAL", "ShipStack goal current mission product"),
        ("2. PROJECT STATUS", "ShipStack status progress pipeline"),
        ("3. NEXT ACTIONS", "ShipStack next action priority"),
        ("4. PRODUCT ARCHITECTURE", "ShipStack product architecture design"),
        ("5. TEAM & ROLES", "ShipStack team roles responsibilities"),
        ("6. KNOWN ISSUES", "ShipStack issues blockers bugs"),
        ("7. INTEGRATIONS", "ShipStack integrations ALIEN Quinn"),
    ]

    for title, example_query in queries:
        print(f"{title}")
        print(f"  Run: quinn_search('{example_query}', project='ship_stack_ai', top_k=3)")
        print()

    print_footer()
    return 0

def print_footer():
    print("\n" + "="*70)
    print("  AFTER RUNNING THESE 7 QUERIES:")
    print("="*70)
    print("""
You will have full context of the ShipStack project.

RESTATE in 5 lines:
  1. What is the current GOAL?
  2. What is the current STATE?
  3. What is the next ACTION?
  4. What RULES govern ShipStack?
  5. What BLOCKERS exist?

WAIT for confirmation before starting work.

REMEMBER:
  • Brain learns from everything you do
  • Search for what you need (don't rely on memory)
  • Use quinn_chat to think through problems
  • Every question you ask → indexed for next agent
""")
    print("="*70 + "\n")

if __name__ == "__main__":
    sys.exit(main())
