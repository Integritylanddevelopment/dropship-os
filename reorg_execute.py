#!/usr/bin/env python3
"""
Reorganize ShipStack root files into subfolders per Quinn's spec.
Safe execution: dry-run first, then execute.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
import json

# Define root
ROOT = Path(r"C:\Users\integ\Documents\Claude\Projects\Drop shipping")

# File-to-folder mapping per Quinn's spec
MOVES = {
    "engines": [
        "shipstack_engine.py", "shipstack.py", "prometheus_engine.py", "prometheus.py",
        "prometheus_monitor.py", "decision_engine.py", "run_dropship_os.py", "run_prometheus.py",
        "RUN_STACK.py", "launch_shipstack.py", "shipstack_dashboard.py", "server.js"
    ],
    "agents": [
        "social_ai_agent.py", "product_research.py", "analytics_engine.py"
    ],
    "badge": [
        "shipstack_badge.py", "shipstack_log_action.py", "validate_config.py"
    ],
    "frontend": [
        "index.html", "launcher_os.html", "privacy.html", "thank-you.html", "metrics.json"
    ],
    "scripts": [
        "DEPLOY.ps1", "LAUNCH_SHIPSTACK.ps1", "PUSH_SHIPSTACK_TO_GITHUB.ps1",
        "PUSH_ENGINE.ps1", "push_to_github.ps1", "quick_start.sh", "set_vercel_env.py",
        "set_vercel_envs.py", "get_youtube_token.py", "consolidate_shipstack_env.py"
    ],
    "docs": [
        "BUILD_PLAN.md", "SYSTEM_ARCHITECTURE.md", "QUICKSTART.md", "SETUP_CHECKLIST.md",
        "SETUP_FOR_FIRST_TIME.md", "PLAN_FRAMEWORK.md", "SHIPSTACK_BUILD_CHECKLIST.md",
        "BADGE_PROTOCOL_EXAMPLE.md"
    ],
    "handoffs": [
        "HANDOFF_FROM_QUINN_CORRECTIVE.md", "HANDOFF_TO_QUINN.md",
        "HANDOFF_TO_QUINN_2026-06-03_ACK_BUILD_ORDER.md",
        "HANDOFF_TO_QUINN_2026-06-03_TIER0_COMPLETE.md",
        "HANDOFF_TO_QUINN_2026-06-03_TIER1_COMPLETE.md",
        "HANDOFF_TO_QUINN_2026-06-03_TIERS_2-5_COMPLETE.md",
        "HANDOFF_TO_QUINN_2026-06-03_COMPLETE_BUILD.md",
        "MASTER_HANDOFF_FROM_QUINN.md", "PROMETHEUS_HANDOFF.md",
        "SHIPSTACK_AGENT_GUARDRAILS.md"
    ],
    "tests": [
        "test_integration.py", "verify_stack.py"
    ],
    "_archive": [
        "SHIPSTACK_CONSISTENCY_CHECK_2026-06-03.md",
        "DEPLOYMENT_STATUS_2026-06-03.md", "FINAL_DELIVERY_2026-06-03.md",
        "index.html.bak", ".env2", ".gitignore2", "reorg_and_rename.py"
    ]
}

DELETE_FILES = [
    "DISABLE_CLAUDE_CODE_NOW.bat", "run_disable_claude_code.bat",
    "EXECUTE_DISABLE.bat", "RUN_INGEST.bat"
]

DELETE_DIRS_IF_EMPTY = [
    "__pycache__", "pinterest_cards", "decision_engine", "dependencies",
    "C:\\Users\\integ\\Documents\\Claude\\Projects\\Drop shipping"  # mojibake
]

# ===== FUNCTIONS =====

def sha256_file(path):
    """Compute SHA256 of file."""
    import hashlib
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()

def dry_run():
    """Print what will happen."""
    print("=" * 80)
    print("DRY RUN - NO CHANGES MADE")
    print("=" * 80)

    moves_count = {}
    conflicts = []

    for dest_folder, files in MOVES.items():
        dest_path = ROOT / dest_folder
        moves_count[dest_folder] = 0

        for file in files:
            src = ROOT / file
            if not src.exists():
                print(f"  SKIP (not found): {file}")
                continue

            # Check for conflict
            dst_full = dest_path / file
            if dst_full.exists():
                src_hash = sha256_file(src)
                dst_hash = sha256_file(dst_full)
                if src_hash == dst_hash:
                    print(f"  DELETE (duplicate): {file}")
                else:
                    print(f"  RENAME (conflict): {file} -> {file}.from_root")
                    conflicts.append((file, src, dst_full))
            else:
                print(f"  MOVE -> {dest_folder}/: {file}")
                moves_count[dest_folder] += 1

    print("\n" + "=" * 80)
    print("DELETIONS:")
    for f in DELETE_FILES:
        src = ROOT / f
        if src.exists():
            print(f"  DELETE: {f}")

    for d in DELETE_DIRS_IF_EMPTY:
        path = Path(d) if d.startswith("C:\\") else (ROOT / d)
        if path.exists() and (not path.is_dir() or not list(path.iterdir())):
            print(f"  DELETE (empty): {d}")

    print("\n" + "=" * 80)
    print("SUMMARY:")
    print(json.dumps(moves_count, indent=2))
    print(f"Conflicts found: {len(conflicts)}")

    return moves_count, conflicts

def execute():
    """Actually do the moves."""
    print("\n" + "=" * 80)
    print("EXECUTING REORGANIZATION...")
    print("=" * 80)

    log = {
        "timestamp": datetime.now().isoformat(),
        "moves_by_folder": {},
        "conflicts": [],
        "deleted_files": [],
        "deleted_dirs": [],
        "errors": []
    }

    # Create subfolders first
    for folder in MOVES.keys():
        folder_path = ROOT / folder
        folder_path.mkdir(exist_ok=True)

    # Move files
    for dest_folder, files in MOVES.items():
        dest_path = ROOT / dest_folder
        log["moves_by_folder"][dest_folder] = 0

        for file in files:
            src = ROOT / file
            if not src.exists():
                continue

            dst = dest_path / file

            if dst.exists():
                src_hash = sha256_file(src)
                dst_hash = sha256_file(dst)
                if src_hash == dst_hash:
                    # Delete duplicate
                    os.remove(src)
                    log["deleted_files"].append(file)
                else:
                    # Rename incoming
                    new_name = f"{file}.from_root"
                    new_dst = dest_path / new_name
                    shutil.move(str(src), str(new_dst))
                    log["conflicts"].append({"file": file, "renamed_to": new_name})
            else:
                # Normal move
                shutil.move(str(src), str(dst))
                log["moves_by_folder"][dest_folder] += 1

    # Delete marked files
    for f in DELETE_FILES:
        src = ROOT / f
        if src.exists():
            os.remove(src)
            log["deleted_files"].append(f)

    # Delete empty dirs
    for d in DELETE_DIRS_IF_EMPTY:
        path = Path(d) if d.startswith("C:\\") else (ROOT / d)
        if path.exists():
            try:
                if path.is_dir() and not list(path.iterdir()):
                    os.rmdir(path)
                    log["deleted_dirs"].append(str(d))
            except Exception as e:
                log["errors"].append(f"Failed to delete {d}: {e}")

    print("\n" + "=" * 80)
    print("REORGANIZATION COMPLETE!")
    print(json.dumps(log, indent=2))
    return log

if __name__ == "__main__":
    import sys

    print("ShipStack Folder Reorganization Tool")
    print(f"Root: {ROOT}\n")

    # Dry run
    moves, conflicts = dry_run()

    # Ask user
    if len(sys.argv) > 1 and sys.argv[1] == "--execute":
        print("\n--execute flag detected. Proceeding...")
        log = execute()
    else:
        print("\nTo execute, run: python reorg_execute.py --execute")
        print("Aborting.")
