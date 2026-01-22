#!/usr/bin/env python3
"""
Script to remove Notion tasks that don't have corresponding traces.

Usage:
    python3 remove_tasks_without_traces.py         # Dry run (default)
    python3 remove_tasks_without_traces.py --delete  # Actually delete files
"""

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Remove Notion tasks that don't have corresponding traces."
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete the files. Without this flag, only shows what would be deleted.",
    )
    args = parser.parse_args()

    # Get the repo root (parent of scripts directory)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Define paths
    tasks_dir = repo_root / "dojo-bench-customer-colossus" / "tasks" / "notion-database-v2"
    traces_dir = repo_root / "dojo-bench-customer-colossus" / "traces" / "notion-database"

    # Validate directories exist
    if not tasks_dir.exists():
        print(f"Error: Tasks directory not found: {tasks_dir}")
        return 1

    if not traces_dir.exists():
        print(f"Error: Traces directory not found: {traces_dir}")
        return 1

    # Get all task and trace filenames
    task_files = {f.name for f in tasks_dir.glob("*.json")}
    trace_files = {f.name for f in traces_dir.glob("*.json")}

    print(f"Found {len(task_files)} tasks in {tasks_dir}")
    print(f"Found {len(trace_files)} traces in {traces_dir}")
    print()

    # Find tasks without traces
    tasks_without_traces = task_files - trace_files

    if not tasks_without_traces:
        print("All tasks have corresponding traces. Nothing to delete.")
        return 0

    print(f"Found {len(tasks_without_traces)} tasks without traces:")
    print()

    for task_file in sorted(tasks_without_traces):
        task_path = tasks_dir / task_file
        if args.delete:
            os.remove(task_path)
            print(f"  Deleted: {task_file}")
        else:
            print(f"  Would delete: {task_file}")

    print()
    if args.delete:
        print(f"Deleted {len(tasks_without_traces)} task files.")
    else:
        print(f"Dry run complete. Run with --delete to actually remove {len(tasks_without_traces)} files.")

    return 0


if __name__ == "__main__":
    exit(main())
