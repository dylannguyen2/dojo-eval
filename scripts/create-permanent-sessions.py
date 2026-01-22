#!/usr/bin/env python3
import argparse
import subprocess
import os
import sys
import json
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # dotenv not installed, rely on environment variables

SNAPSHOTS = {
    "jd": "jd-default-seed-data",
    "xiaohongshu": "xhs-default-seed-data",
    "weibo": "weibo-default-seed-data",
    "notion": "notion-default-seed-data"
}

# Aliases for convenience
ALIASES = {
    "xhs": "xiaohongshu",
}

ENVIRONMENTS = {
    "staging": {
        "endpoint": "https://staging-orchestrator.trydojo.ai/api/v1/session",
        "api_key_env": "API_KEY_STAGING",
    },
    "prod": {
        "endpoint": "https://orchestrator.trydojo.ai/api/v1/session",
        "api_key_env": "API_KEY_PRODUCTION",
    },
}


def resolve_target(target: str) -> str:
    """Resolve a target name, handling aliases."""
    resolved = ALIASES.get(target, target)
    if resolved not in SNAPSHOTS:
        valid = list(SNAPSHOTS.keys()) + list(ALIASES.keys())
        print(f"Error: unknown target '{target}'. Valid targets: {', '.join(valid)}", file=sys.stderr)
        sys.exit(1)
    return resolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, choices=["staging", "prod"])
    parser.add_argument("targets", nargs="*", help="Optional targets to create (e.g., jd xhs weibo notion). If omitted, creates all.")
    args = parser.parse_args()

    env_config = ENVIRONMENTS[args.env]
    endpoint = env_config["endpoint"]
    api_key_env = env_config["api_key_env"]
    api_key = os.environ.get(api_key_env)

    if not api_key:
        print(f"Error: {api_key_env} environment variable is required for {args.env}")
        print(f"Set it in .env file or export it in your shell")
        sys.exit(1)

    # Determine which snapshots to create
    if args.targets:
        targets = [resolve_target(t) for t in args.targets]
        # Remove duplicates while preserving order
        targets = list(dict.fromkeys(targets))
    else:
        targets = list(SNAPSHOTS.keys())

    session_ids = {}

    for name in targets:
        snapshot = SNAPSHOTS[name]
        print(f"Creating session for {snapshot}...", file=sys.stderr)

        result = subprocess.run(
            [
                "curl", "-s", "-X", "POST", endpoint,
                "-H", "Content-Type: application/json",
                "-H", f"Authorization: Bearer {api_key}",
                "-d", f'{{"snapshot_name":"{snapshot}","persistent":true}}',
            ],
            capture_output=True,
            text=True,
        )
        
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        try:
            response = json.loads(result.stdout)
            session_id = response.get("session_id")
            if session_id:
                session_ids[name] = session_id
                print(f"  -> {session_id}", file=sys.stderr)
            else:
                print(f"  -> Error: no session_id in response: {result.stdout}", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"  -> Error parsing response: {result.stdout}", file=sys.stderr)
        
        print(file=sys.stderr)

    print(json.dumps(session_ids, indent=2))


if __name__ == "__main__":
    main()