#!/usr/bin/env python3
"""Check snapshot status for task initial backend data in dojo-bench-customer-colossus."""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

NAMESPACE = "dojo-go-server"
COLOSSUS_BASE_PATH = Path(__file__).parent.parent / "dojo-bench-customer-colossus"
INITIAL_BACKEND_DATA_PATH = COLOSSUS_BASE_PATH / "initial-backend-data"

ENVIRONMENTS = {
    "staging": {
        "kube_context": "dojo-staging",
    },
    "production": {
        "kube_context": "dojo-production",
    },
}

Environment = Literal["staging", "production"]


def calculate_snapshot_name(json_path: str, app_context: str | None = None) -> str:
    """
    Calculate snapshot name from file path: {parent_folder}-{filename} with _ -> -.

    For initial_data files, use the app_context (original requesting app's folder)
    instead of the actual parent folder.
    """
    path = Path(json_path).resolve()
    filename = path.stem  # filename without extension

    # Use app_context if provided (for initial_data), otherwise use actual parent
    folder = app_context if app_context else path.parent.name

    raw_name = f"{folder}-{filename}"
    return re.sub(r"_", "-", raw_name)


def run_kubectl(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a kubectl command and return the result."""
    cmd = ["kubectl", "-n", NAMESPACE] + args
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def switch_kube_context(env: Environment) -> None:
    """Switch to the appropriate kubernetes context."""
    context = ENVIRONMENTS[env]["kube_context"]
    print(f"Switching to kubernetes context: {context}")
    try:
        subprocess.run(["kubectx", context], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print(f"Warning: Failed to switch context using kubectx, trying kubectl...")
        subprocess.run(["kubectl", "config", "use-context", context], check=True)


def get_snapshot_info(snapshot_name: str) -> dict | None:
    """Get snapshot information including creation timestamp and ready status."""
    result = run_kubectl(
        [
            "get", "volumesnapshot", snapshot_name,
            "-o", "json",
        ],
        check=False,
    )

    if result.returncode != 0:
        return None

    try:
        data = json.loads(result.stdout)
        creation_timestamp = data.get("metadata", {}).get("creationTimestamp")
        ready_to_use = data.get("status", {}).get("readyToUse", False)

        return {
            "name": snapshot_name,
            "exists": True,
            "ready": ready_to_use,
            "created_at": creation_timestamp,
        }
    except json.JSONDecodeError:
        return None


def get_meilisearch_snapshot_name(snapshot_name: str) -> str:
    """Get the Meilisearch snapshot name for a given snapshot."""
    return f"meilisearch-{snapshot_name}"


def calculate_age(creation_timestamp: str) -> str:
    """Calculate human-readable age from ISO timestamp."""
    created = datetime.fromisoformat(creation_timestamp.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    delta = now - created

    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def get_file_last_commit_date(file_path: Path) -> datetime | None:
    """Get the last commit date for a file using git log."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", str(file_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            return datetime.fromisoformat(result.stdout.strip().replace("Z", "+00:00"))
        return None
    except subprocess.CalledProcessError:
        return None


def collect_json_files(base_path: Path) -> dict[str, list[Path]]:
    """Collect all JSON files from initial-backend-data directory, grouped by app."""
    if not base_path.exists():
        raise ValueError(f"Path does not exist: {base_path}")

    files_by_app: dict[str, list[Path]] = {}

    for app_dir in base_path.iterdir():
        if not app_dir.is_dir():
            continue

        json_files = sorted(app_dir.glob("*.json"))
        if json_files:
            files_by_app[app_dir.name] = json_files

    return files_by_app


def check_snapshots(env: Environment, app_filter: str | None = None) -> None:
    """Check snapshot status for all initial backend data files."""
    print(f"{'='*80}")
    print(f"Snapshot Status Report for dojo-bench-customer-colossus")
    print(f"{'='*80}")
    print(f"Environment: {env}")
    print(f"Base path: {INITIAL_BACKEND_DATA_PATH}")
    print()

    # Switch kubernetes context
    switch_kube_context(env)
    print()

    # Collect all JSON files
    files_by_app = collect_json_files(INITIAL_BACKEND_DATA_PATH)

    if app_filter:
        files_by_app = {k: v for k, v in files_by_app.items() if k == app_filter}
        if not files_by_app:
            print(f"Error: No app found matching '{app_filter}'")
            print(f"Available apps: {', '.join(collect_json_files(INITIAL_BACKEND_DATA_PATH).keys())}")
            sys.exit(1)

    total_files = sum(len(files) for files in files_by_app.values())
    print(f"Found {total_files} initial backend data files across {len(files_by_app)} apps")
    print()

    # Track statistics
    stats = {
        "total": 0,
        "exists": 0,
        "missing": 0,
        "ready": 0,
        "not_ready": 0,
        "outdated": 0,
        "meilisearch_missing": 0,
        "meilisearch_not_ready": 0,
        "meilisearch_outdated": 0,
    }

    missing_snapshots: list[tuple[str, str]] = []  # (app, snapshot_name)
    not_ready_snapshots: list[tuple[str, str]] = []  # (app, snapshot_name)
    outdated_snapshots: list[tuple[str, str, str, str]] = []  # (app, snapshot_name, last_commit, snapshot_age)
    existing_snapshots: list[tuple[str, str, str]] = []  # (app, snapshot_name, age)

    missing_meilisearch_snapshots: list[tuple[str, str]] = []  # (app, snapshot_name)
    not_ready_meilisearch_snapshots: list[tuple[str, str]] = []  # (app, snapshot_name)
    outdated_meilisearch_snapshots: list[tuple[str, str, str, str]] = []  # (app, snapshot_name, last_commit, snapshot_age)

    # Check each file
    for app_name, json_files in sorted(files_by_app.items()):
        print(f"{'─'*80}")
        print(f"App: {app_name}")
        print(f"{'─'*80}")

        for json_file in json_files:
            stats["total"] += 1
            snapshot_name = calculate_snapshot_name(str(json_file))
            meilisearch_snapshot_name = get_meilisearch_snapshot_name(snapshot_name)

            # Get last commit date for the file
            last_commit_date = get_file_last_commit_date(json_file)

            info = get_snapshot_info(snapshot_name)
            meili_info = get_snapshot_info(meilisearch_snapshot_name)

            if info is None:
                stats["missing"] += 1
                missing_snapshots.append((app_name, snapshot_name))
                commit_info = f"(last commit: {last_commit_date.strftime('%Y-%m-%d %H:%M')})" if last_commit_date else ""
                print(f"  ✗ {snapshot_name:60s} MISSING {commit_info}")

                # Also check if Meilisearch snapshot is missing
                if meili_info is None:
                    stats["meilisearch_missing"] += 1
                    missing_meilisearch_snapshots.append((app_name, snapshot_name))
                    print(f"    └─ meilisearch: MISSING")
                else:
                    print(f"    └─ meilisearch: EXISTS (orphaned)")
            else:
                stats["exists"] += 1
                age = calculate_age(info["created_at"])
                snapshot_created = datetime.fromisoformat(info["created_at"].replace("Z", "+00:00"))

                # Check if snapshot is outdated (file was modified after snapshot creation)
                is_outdated = False
                if last_commit_date and snapshot_created < last_commit_date:
                    is_outdated = True
                    stats["outdated"] += 1
                    commit_str = last_commit_date.strftime('%Y-%m-%d %H:%M')
                    outdated_snapshots.append((app_name, snapshot_name, commit_str, age))

                # Check Meilisearch snapshot
                meili_status = ""
                meili_is_outdated = False
                if meili_info is None:
                    stats["meilisearch_missing"] += 1
                    missing_meilisearch_snapshots.append((app_name, snapshot_name))
                    meili_status = "✗ MISSING"
                else:
                    meili_age = calculate_age(meili_info["created_at"])
                    meili_snapshot_created = datetime.fromisoformat(meili_info["created_at"].replace("Z", "+00:00"))

                    # Check if Meilisearch snapshot is outdated
                    if last_commit_date and meili_snapshot_created < last_commit_date:
                        meili_is_outdated = True
                        stats["meilisearch_outdated"] += 1
                        commit_str = last_commit_date.strftime('%Y-%m-%d %H:%M')
                        outdated_meilisearch_snapshots.append((app_name, snapshot_name, commit_str, meili_age))

                    if meili_info["ready"]:
                        meili_icon = "⚠" if meili_is_outdated else "✓"
                        meili_outdated_flag = " [OUTDATED]" if meili_is_outdated else ""
                        meili_status = f"{meili_icon} EXISTS (age: {meili_age}){meili_outdated_flag}"
                    else:
                        stats["meilisearch_not_ready"] += 1
                        not_ready_meilisearch_snapshots.append((app_name, snapshot_name))
                        meili_icon = "⚠"
                        meili_outdated_flag = " [OUTDATED]" if meili_is_outdated else ""
                        meili_status = f"{meili_icon} NOT READY (age: {meili_age}){meili_outdated_flag}"

                if info["ready"]:
                    stats["ready"] += 1
                    existing_snapshots.append((app_name, snapshot_name, age))
                    status_icon = "⚠" if is_outdated else "✓"
                    outdated_flag = " [OUTDATED]" if is_outdated else ""
                    print(f"  {status_icon} {snapshot_name:60s} EXISTS (age: {age}, ready: ✓){outdated_flag}")
                    print(f"    └─ meilisearch: {meili_status}")
                else:
                    stats["not_ready"] += 1
                    not_ready_snapshots.append((app_name, snapshot_name))
                    status_icon = "⚠"
                    outdated_flag = " [OUTDATED]" if is_outdated else ""
                    print(f"  {status_icon} {snapshot_name:60s} EXISTS (age: {age}, ready: ✗){outdated_flag}")
                    print(f"    └─ meilisearch: {meili_status}")

        print()

    # Print summary
    print(f"{'='*80}")
    print(f"Summary")
    print(f"{'='*80}")
    print(f"Total files checked:              {stats['total']}")
    print()
    print(f"Main Snapshots:")
    print(f"  Exist:                          {stats['exists']} ({stats['exists']/stats['total']*100:.1f}%)")
    print(f"    └─ Ready:                     {stats['ready']}")
    print(f"    └─ Not ready:                 {stats['not_ready']}")
    print(f"    └─ Outdated:                  {stats['outdated']}")
    print(f"  Missing:                        {stats['missing']} ({stats['missing']/stats['total']*100:.1f}%)")
    print()
    print(f"Meilisearch Snapshots:")
    print(f"  Missing:                        {stats['meilisearch_missing']}")
    print(f"  Not ready:                      {stats['meilisearch_not_ready']}")
    print(f"  Outdated:                       {stats['meilisearch_outdated']}")
    print()

    # Print missing snapshots
    if missing_snapshots:
        print(f"{'='*80}")
        print(f"Missing Snapshots ({len(missing_snapshots)})")
        print(f"{'='*80}")

        by_app: dict[str, list[str]] = {}
        for app_name, snapshot_name in missing_snapshots:
            if app_name not in by_app:
                by_app[app_name] = []
            by_app[app_name].append(snapshot_name)

        for app_name, snapshots in sorted(by_app.items()):
            print(f"\n{app_name} ({len(snapshots)} missing):")
            for snapshot_name in snapshots:
                print(f"  - {snapshot_name}")

    # Print not ready snapshots
    if not_ready_snapshots:
        print(f"\n{'='*80}")
        print(f"Not Ready Snapshots ({len(not_ready_snapshots)})")
        print(f"{'='*80}")

        by_app: dict[str, list[str]] = {}
        for app_name, snapshot_name in not_ready_snapshots:
            if app_name not in by_app:
                by_app[app_name] = []
            by_app[app_name].append(snapshot_name)

        for app_name, snapshots in sorted(by_app.items()):
            print(f"\n{app_name} ({len(snapshots)} not ready):")
            for snapshot_name in snapshots:
                print(f"  - {snapshot_name}")

    # Print outdated snapshots
    if outdated_snapshots:
        print(f"\n{'='*80}")
        print(f"Outdated Snapshots ({len(outdated_snapshots)})")
        print(f"{'='*80}")
        print("These snapshots are older than their corresponding backend data files.")
        print("The files have been modified since the snapshots were created.")

        by_app: dict[str, list[tuple[str, str, str]]] = {}
        for app_name, snapshot_name, last_commit, snapshot_age in outdated_snapshots:
            if app_name not in by_app:
                by_app[app_name] = []
            by_app[app_name].append((snapshot_name, last_commit, snapshot_age))

        for app_name, snapshots in sorted(by_app.items()):
            print(f"\n{app_name} ({len(snapshots)} outdated):")
            for snapshot_name, last_commit, snapshot_age in snapshots:
                print(f"  - {snapshot_name}")
                print(f"      File last modified: {last_commit}")
                print(f"      Snapshot age:       {snapshot_age}")

    # Print missing Meilisearch snapshots
    if missing_meilisearch_snapshots:
        print(f"\n{'='*80}")
        print(f"Missing Meilisearch Snapshots ({len(missing_meilisearch_snapshots)})")
        print(f"{'='*80}")
        print("These main snapshots exist but are missing their associated Meilisearch snapshots.")

        by_app: dict[str, list[str]] = {}
        for app_name, snapshot_name in missing_meilisearch_snapshots:
            if app_name not in by_app:
                by_app[app_name] = []
            by_app[app_name].append(snapshot_name)

        for app_name, snapshots in sorted(by_app.items()):
            print(f"\n{app_name} ({len(snapshots)} missing):")
            for snapshot_name in snapshots:
                print(f"  - {snapshot_name} (missing: meilisearch-{snapshot_name})")

    # Print not ready Meilisearch snapshots
    if not_ready_meilisearch_snapshots:
        print(f"\n{'='*80}")
        print(f"Not Ready Meilisearch Snapshots ({len(not_ready_meilisearch_snapshots)})")
        print(f"{'='*80}")

        by_app: dict[str, list[str]] = {}
        for app_name, snapshot_name in not_ready_meilisearch_snapshots:
            if app_name not in by_app:
                by_app[app_name] = []
            by_app[app_name].append(snapshot_name)

        for app_name, snapshots in sorted(by_app.items()):
            print(f"\n{app_name} ({len(snapshots)} not ready):")
            for snapshot_name in snapshots:
                print(f"  - meilisearch-{snapshot_name}")

    # Print outdated Meilisearch snapshots
    if outdated_meilisearch_snapshots:
        print(f"\n{'='*80}")
        print(f"Outdated Meilisearch Snapshots ({len(outdated_meilisearch_snapshots)})")
        print(f"{'='*80}")
        print("These Meilisearch snapshots are older than their corresponding backend data files.")

        by_app: dict[str, list[tuple[str, str, str]]] = {}
        for app_name, snapshot_name, last_commit, snapshot_age in outdated_meilisearch_snapshots:
            if app_name not in by_app:
                by_app[app_name] = []
            by_app[app_name].append((snapshot_name, last_commit, snapshot_age))

        for app_name, snapshots in sorted(by_app.items()):
            print(f"\n{app_name} ({len(snapshots)} outdated):")
            for snapshot_name, last_commit, snapshot_age in snapshots:
                print(f"  - meilisearch-{snapshot_name}")
                print(f"      File last modified: {last_commit}")
                print(f"      Snapshot age:       {snapshot_age}")

    # Print age distribution
    if existing_snapshots:
        print(f"\n{'='*80}")
        print(f"Age Distribution")
        print(f"{'='*80}")

        # Calculate age buckets
        age_buckets: dict[str, int] = {
            "< 1 hour": 0,
            "1-24 hours": 0,
            "1-7 days": 0,
            "7-30 days": 0,
            "> 30 days": 0,
        }

        for _, _, age_str in existing_snapshots:
            # Parse age string to determine bucket
            if "d" in age_str:
                days = int(age_str.split("d")[0])
                if days > 30:
                    age_buckets["> 30 days"] += 1
                elif days >= 7:
                    age_buckets["7-30 days"] += 1
                else:
                    age_buckets["1-7 days"] += 1
            elif "h" in age_str:
                hours = int(age_str.split("h")[0])
                if hours >= 1:
                    age_buckets["1-24 hours"] += 1
                else:
                    age_buckets["< 1 hour"] += 1
            else:
                age_buckets["< 1 hour"] += 1

        for bucket, count in age_buckets.items():
            if count > 0:
                bar = "█" * min(int(count / len(existing_snapshots) * 50), 50)
                print(f"  {bucket:15s} {count:4d} {bar}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Check snapshot status for dojo-bench-customer-colossus initial backend data",
        usage="%(prog)s --env <staging|production> [--app <app-name>]",
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=["staging", "production"],
        help="Environment (staging or production)",
    )
    parser.add_argument(
        "--app",
        help="Filter by specific app (jd, weibo, xiaohongshu)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    env: Environment = args.env
    app_filter: str | None = args.app

    try:
        check_snapshots(env, app_filter)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
