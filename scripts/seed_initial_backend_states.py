#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description="Seed tasks from JSON files")
parser.add_argument("tasks_dir", type=Path, help="Path to tasks folder")
parser.add_argument(
    "--env",
    required=True,
    choices=["staging", "production"],
    help="Environment (staging or production)",
)
parser.add_argument(
    "--dry-run", action="store_true", help="Print commands without executing"
)
parser.add_argument(
    "--overwrite", action="store_true", help="Delete existing snapshots and re-seed"
)
args = parser.parse_args()

tasks_dir = args.tasks_dir
env = args.env
dry_run = args.dry_run
overwrite = args.overwrite

# Switch kubectl context
kubectx = f"dojo-{env}"
if dry_run:
    print(f"Would run: kubectx {kubectx}")
else:
    print(f"Switching to {kubectx}...")
    result = subprocess.run(["kubectx", kubectx])
    if result.returncode != 0:
        print(f"Error switching context to {kubectx}")
        sys.exit(1)

# Get existing volume snapshots
existing_snapshots = set()
if not dry_run:
    result = subprocess.run(
        [
            "kubectl",
            "get",
            "volumesnapshots",
            "-o",
            "jsonpath={.items[*].metadata.name}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        existing_snapshots = set(result.stdout.split())

skipped = 0
processed = 0
deleted = 0

# Get the folder name from the tasks_dir
folder_name = tasks_dir.name.replace("_", "-")

for f in sorted(tasks_dir.glob("*.json")):
    name = f.stem
    name = name.replace("_", "-")

    # Combine folder name and file name
    full_name = f"{folder_name}-{name}"

    # Check if snapshot already exists
    if full_name in existing_snapshots:
        if overwrite:
            print(f"Deleting existing snapshot: {full_name}")
            if not dry_run:
                result = subprocess.run(
                    ["kubectl", "delete", "volumesnapshot", full_name]
                )
                if result.returncode != 0:
                    print(f"Error deleting snapshot {full_name}, skipping")
                    skipped += 1
                    continue
            else:
                print(f"Would run: kubectl delete volumesnapshot {full_name}")
            deleted += 1
        else:
            print(f"Skipping {full_name}: volume snapshot already exists")
            skipped += 1
            continue

    # Get the directory containing this script
    script_dir = Path(__file__).resolve().parent
    seed_script = script_dir / "seed.py"

    cmd = [
        "python3",
        str(seed_script),
        "remote",
        "--path",
        str(f.absolute()),
        "--name",
        full_name,
        "--env",
        env,
    ]

    if dry_run:
        print(f"Would run: {' '.join(cmd)}")
    else:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"Error seeding {f.name}, exit code: {result.returncode}")

    processed += 1

total = len(list(tasks_dir.glob("*.json")))
print(
    f"\n{'Would process' if dry_run else 'Processed'}: {processed} files, skipped: {skipped}, deleted: {deleted}, total: {total}"
)
