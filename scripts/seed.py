#!/usr/bin/env python3
"""Seed script for database initialization and snapshot creation."""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal, TypedDict

import httpx
from dotenv import load_dotenv

load_dotenv()

APP_INITIAL_DATA_MAPPING: dict[str, str] = {
    "xiaohongshu": "../xiaohongshu/app/initial_data.json",
    "weibo": "../weibo/app/initial_data.json",
    "jd": "../jd/app/initial_data.json",
    "notion": "../notion/app/initial_data.json",
    "figma": "../figma/app/initial_data.json",
    "canva": "../canva/app/initial_data.json",
}

APP_INDICES_MAPPING: dict[str, str] = {
    "xiaohongshu": "../xiaohongshu/app/indices.json",
    "weibo": "../weibo/app/indices.json",
    "jd": "../jd/app/indices.json",
    "notion": "../notion/app/indices.json",
}

INITIAL_DATA_SPECIAL_ID = "initial_data"
NAMESPACE = "dojo-go-server"

ENVIRONMENTS = {
    "local": {
        "base_url": "http://localhost:8080/api/v1/session",
        "api_key_env": "API_KEY_LOCAL",
        "kube_context": "dojo-local",
    },
    "staging": {
        "base_url": "https://staging-orchestrator.trydojo.ai/api/v1/session",
        "api_key_env": "API_KEY_STAGING",
        "kube_context": "dojo-staging",
    },
    "production": {
        "base_url": "https://orchestrator.trydojo.ai/api/v1/session",
        "api_key_env": "API_KEY_PRODUCTION",
        "kube_context": "dojo-production",
    },
}

Environment = Literal["local", "staging", "production"]


class SessionResponse(TypedDict):
    session_id: str


class StatusResponse(TypedDict):
    status: Literal["RUNNING", "QUEUED", "TERMINATED", "FAILED", "LOCKED"]


class SeedResponse(TypedDict):
    seed_id: str


class Mutation(TypedDict, total=False):
    type: str
    collection: str
    documents: list[dict[str, Any]]
    deletes: list[dict[str, Any]]
    index: dict[str, Any]


class DiffSeedFile(TypedDict):
    type: Literal["diff"]
    base_id: str
    transactions: list[Mutation]


class RetryOptions(TypedDict, total=False):
    max_retries: int
    base_delay_ms: int
    max_delay_ms: int


DEFAULT_RETRY_OPTIONS: RetryOptions = {
    "max_retries": 3,
    "base_delay_ms": 1000,
    "max_delay_ms": 10000,
}


def chunk_array[T](array: list[T], size: int) -> list[list[T]]:
    """Split an array into chunks of the specified size."""
    return [array[i : i + size] for i in range(0, len(array), size)]


def is_diff_seed_file(data: dict[str, Any]) -> bool:
    """Check if the seed file is a diff type."""
    return data.get("type") == "diff"


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


def resolve_base_file_path(json_path: str, base_id: str) -> str:
    """Resolve the base file path for diff seed files."""
    json_dir = Path(json_path).resolve().parent

    if base_id == INITIAL_DATA_SPECIAL_ID:
        folder_name = json_dir.name
        relative_path = APP_INITIAL_DATA_MAPPING.get(folder_name)
        if not relative_path:
            valid_folders = ", ".join(APP_INITIAL_DATA_MAPPING.keys())
            raise ValueError(
                f'Unknown folder "{folder_name}" for initial_data base_id. '
                f"Expected one of: {valid_folders}"
            )
        return str(Path.cwd() / relative_path)

    return str(json_dir / f"{base_id}.json")


def run_kubectl(
    args: list[str], check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a kubectl command and return the result."""
    cmd = ["kubectl", "-n", NAMESPACE] + args
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def switch_kube_context(env: Environment) -> None:
    """Switch to the appropriate kubernetes context."""
    context = ENVIRONMENTS[env]["kube_context"]
    print(f"Switching to kubernetes context: {context}")
    subprocess.run(["kubectx", context], check=True)


def snapshot_exists(snapshot_name: str) -> bool:
    """Check if a volume snapshot exists."""
    result = run_kubectl(
        ["get", "volumesnapshot", snapshot_name, "-o", "name"],
        check=False,
    )
    return result.returncode == 0


def snapshot_is_ready(snapshot_name: str) -> bool:
    """Check if a volume snapshot exists and is ready to use."""
    result = run_kubectl(
        [
            "get",
            "volumesnapshot",
            snapshot_name,
            "-o",
            "jsonpath={.status.readyToUse}",
        ],
        check=False,
    )
    if result.returncode != 0:
        return False
    return result.stdout.strip().lower() == "true"


async def wait_for_snapshot_ready(
    snapshot_name: str,
    timeout_seconds: int = 300,
    poll_interval: int = 10,
) -> bool:
    """
    Wait for a snapshot to be ready to use.
    Returns True if ready, False if timeout reached.
    """
    print(f"Waiting for snapshot '{snapshot_name}' to be ready...")
    elapsed = 0

    while elapsed < timeout_seconds:
        if snapshot_is_ready(snapshot_name):
            print(f"Snapshot '{snapshot_name}' is ready to use")
            return True

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        print(
            f"Snapshot '{snapshot_name}' not ready yet ({elapsed}s/{timeout_seconds}s)..."
        )

    return False


def delete_snapshot(snapshot_name: str, dry_run: bool = False) -> None:
    """Delete a volume snapshot."""
    if dry_run:
        print(f"  [DRY-RUN] Would delete snapshot: {snapshot_name}")
        return

    print(f"  Deleting snapshot: {snapshot_name}")
    run_kubectl(["delete", "volumesnapshot", snapshot_name], check=True)


async def fetch_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    retry_options: RetryOptions | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """Make an HTTP request with exponential backoff retry logic."""
    opts = {**DEFAULT_RETRY_OPTIONS, **(retry_options or {})}
    max_retries = opts["max_retries"]
    base_delay_ms = opts["base_delay_ms"]
    max_delay_ms = opts["max_delay_ms"]

    last_error: Exception | None = None
    last_response: httpx.Response | None = None

    for attempt in range(max_retries + 1):
        try:
            response = await client.request(method, url, **kwargs)

            if response.is_success:
                return response

            should_retry = response.status_code >= 500 or response.status_code == 429

            if not should_retry or attempt == max_retries:
                return response

            last_response = response
            delay = min(base_delay_ms * (2**attempt), max_delay_ms)
            print(
                f"Request to {url} failed with status {response.status_code}, "
                f"retrying in {delay}ms (attempt {attempt + 1}/{max_retries})..."
            )
            await asyncio.sleep(delay / 1000)

        except Exception as e:
            last_error = e

            if attempt == max_retries:
                raise

            delay = min(base_delay_ms * (2**attempt), max_delay_ms)
            print(
                f"Request to {url} failed with error: {e}, "
                f"retrying in {delay}ms (attempt {attempt + 1}/{max_retries})..."
            )
            await asyncio.sleep(delay / 1000)

    if last_response is not None:
        return last_response
    if last_error is not None:
        raise last_error
    raise RuntimeError("Unexpected retry failure")


async def start_session(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    snapshot_name: str | None = None,
) -> str:
    """Start a new session and return the session ID."""
    body: dict[str, Any] = {}
    if snapshot_name:
        body["snapshot_name"] = snapshot_name

    response = await fetch_with_retry(
        client,
        "POST",
        base_url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json=body,
    )

    if not response.is_success:
        raise RuntimeError(f"Failed to start session: {response.status_code}")

    data: SessionResponse = response.json()
    return data["session_id"]


async def poll_until_not_locked(
    client: httpx.AsyncClient,
    base_url: str,
    session_id: str,
    timeout_seconds: int = 300,
    poll_interval: int = 10,
) -> None:
    """Poll until the session is no longer in LOCKED state."""
    print("Checking if session is locked...")
    elapsed = 0

    while elapsed < timeout_seconds:
        response = await fetch_with_retry(
            client,
            "GET",
            f"{base_url}/{session_id}/status",
            headers={"Content-Type": "application/json"},
        )

        if not response.is_success:
            raise RuntimeError(f"Failed to get status: {response.status_code}")

        data: StatusResponse = response.json()

        if data["status"] != "LOCKED":
            print(f"Session is no longer locked (status: {data['status']})")
            return

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        print(f"Session still LOCKED ({elapsed}s/{timeout_seconds}s)...")

    raise RuntimeError(f"Session still LOCKED after {timeout_seconds} seconds")


async def poll_until_running(
    client: httpx.AsyncClient,
    base_url: str,
    session_id: str,
) -> None:
    """Poll until the session status is RUNNING."""
    print("Polling for RUNNING status...")

    while True:
        response = await fetch_with_retry(
            client,
            "GET",
            f"{base_url}/{session_id}/status",
            headers={"Content-Type": "application/json"},
        )

        if not response.is_success:
            raise RuntimeError(f"Failed to get status: {response.status_code}")

        data: StatusResponse = response.json()
        print(f"Current status: {data['status']}")

        if data["status"] == "RUNNING":
            print("Session is now RUNNING")
            return

        if data["status"] != "QUEUED":
            raise RuntimeError(
                f"Unexpected status: {data['status']}. Expected QUEUED or RUNNING."
            )

        await asyncio.sleep(5)


async def send_mutation_batch(
    client: httpx.AsyncClient, url: str, mutations: list[Mutation]
) -> None:
    """Send a batch of mutations to the session."""
    body = {"mutations": mutations}
    response = await fetch_with_retry(
        client,
        "POST",
        f"{url}/transaction",
        headers={"Content-Type": "application/json"},
        json=body,
    )

    if not response.is_success:
        error_text = response.text
        raise RuntimeError(f"Transaction failed: {response.status_code} - {error_text}")


async def send_transaction(
    client: httpx.AsyncClient,
    url: str,
    transaction: dict[str, Any],
) -> None:
    """Send a transaction (which already contains a mutations array) to the session."""
    response = await fetch_with_retry(
        client,
        "POST",
        f"{url}/transaction",
        headers={"Content-Type": "application/json"},
        json=transaction,
    )

    if not response.is_success:
        error_text = response.text
        raise RuntimeError(f"Transaction failed: {response.status_code} - {error_text}")


async def apply_transactions(
    client: httpx.AsyncClient,
    url: str,
    transactions: list[dict[str, Any]],
) -> None:
    """Apply a list of transactions (each containing a mutations array)."""
    total = len(transactions)
    print(f"Applying {total} transactions...")

    for i, transaction in enumerate(transactions):
        await send_transaction(client, url, transaction)
        completed = i + 1
        if completed % 100 == 0 or completed == total:
            print(f"Transactions completed: {completed}/{total}")


async def poll_index_creation_status(
    client: httpx.AsyncClient,
    url: str,
    timeout_seconds: int = 600,
    poll_interval: int = 5,
) -> None:
    """Poll the index creation status endpoint until indexing is complete."""
    print("Polling for index creation completion...")
    elapsed = 0

    while elapsed < timeout_seconds:
        try:
            response = await fetch_with_retry(
                client,
                "GET",
                f"{url}/search-index-status",
                headers={"Content-Type": "application/json"},
            )

            if not response.is_success:
                print(
                    f"Warning: Failed to get index creation status: {response.status_code}"
                )
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                continue

            data = response.json()
            indexes = data.get("indexes", [])
            print(f"Indexes: {indexes}")

            in_progress = [idx for idx in indexes if idx.get("status") == "in_progress"]
            pending = [idx for idx in indexes if idx.get("status") == "pending"]
            completed = [idx for idx in indexes if idx.get("status") == "completed"]
            failed = [idx for idx in indexes if idx.get("status") == "failed"]

            if in_progress:
                print(f"Index creation in progress: {len(in_progress)}", in_progress)
            if pending:
                print(f"Index creation pending: {len(pending)}", pending)
            if completed:
                print(f"Index creation completed: {len(completed)}", completed)
            if failed:
                print(f"Index creation failed: {len(failed)}", failed)

            if not in_progress and not pending:
                if failed:
                    failed_collections = [idx.get("collection") for idx in failed]
                    raise RuntimeError(
                        f"Index creation failed: {', '.join(failed_collections)}"
                    )
                return

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        except Exception as e:
            print(f"Warning: Error polling index creation status: {e}")
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

    raise RuntimeError(
        f"Index creation did not complete within {timeout_seconds} seconds"
    )


async def create_meilisearch_indices(
    client: httpx.AsyncClient,
    url: str,
    app_context: str,
) -> None:
    """Create Meilisearch search indexes before seeding data."""
    # Get indices file path from app context
    indices_path = APP_INDICES_MAPPING.get(app_context)

    if not indices_path:
        print(f"\nNo indices mapping found for app: {app_context}")
        print("Skipping Meilisearch index creation")
        return

    resolved_path = (Path.cwd() / indices_path).resolve()

    if not resolved_path.exists():
        print(f"\nIndices file not found: {resolved_path}")
        print("Skipping Meilisearch index creation")
        return

    print(f"\nCreating Meilisearch indices from: {resolved_path}")

    with open(resolved_path, encoding="utf-8") as f:
        indices_data = json.load(f)

    indices = indices_data.get("indices", [])

    if not indices:
        print("No indices configured")
        return

    # Send request to create Meilisearch indexes (now asynchronous on server)
    response = await fetch_with_retry(
        client,
        "POST",
        f"{url}/create-search-index",
        headers={"Content-Type": "application/json"},
        json={"indexes": indices},
    )

    if not response.is_success:
        error_text = response.text
        raise RuntimeError(
            f"Failed to create Meilisearch indices: {response.status_code} - {error_text}"
        )

    print(f"✓ Index creation started for {len(indices)} Meilisearch indices")

    # Poll until index creation is complete
    await poll_index_creation_status(client, url)


async def seed_full_data(
    client: httpx.AsyncClient,
    url: str,
    data: dict[str, Any],
) -> None:
    """Seed the database with a full seed file (non-diff)."""
    delete_mutations: list[Mutation] = []
    insert_mutations: list[Mutation] = []

    for collection, documents in data.items():
        if collection == "type":
            continue

        delete_mutations.append(
            {"type": "delete", "collection": collection, "deletes": [{"query": {}}]}
        )

        if isinstance(documents, list) and len(documents) > 0:
            document_chunks = chunk_array(documents, 5)
            for document_chunk in document_chunks:
                insert_mutations.append(
                    {
                        "type": "insert",
                        "collection": collection,
                        "documents": document_chunk,
                    }
                )

    delete_batches = chunk_array(delete_mutations, 5)
    total_delete_batches = len(delete_batches)
    print(
        f"Sending {len(delete_mutations)} delete mutations in {total_delete_batches} batches..."
    )
    for i, batch in enumerate(delete_batches):
        await send_mutation_batch(client, url, batch)
        completed = i + 1
        if completed % 100 == 0 or completed == total_delete_batches:
            print(f"Delete batches completed: {completed}/{total_delete_batches}")

    insert_batches = chunk_array(insert_mutations, 5)
    parallel_chunks = chunk_array(insert_batches, 20)
    total_insert_batches = len(insert_batches)

    print(
        f"Sending {len(insert_mutations)} insert mutations in "
        f"{total_insert_batches} batches (20 parallel)..."
    )

    batches_completed = 0
    for chunk in parallel_chunks:
        await asyncio.gather(
            *[send_mutation_batch(client, url, batch) for batch in chunk]
        )
        prev_completed = batches_completed
        batches_completed += len(chunk)
        if batches_completed == total_insert_batches or (
            prev_completed // 100 < batches_completed // 100
        ):
            print(
                f"Insert batches completed: {batches_completed}/{total_insert_batches}"
            )


async def create_seed(
    client: httpx.AsyncClient,
    base_url: str,
    session_id: str,
    name: str,
    api_key: str,
) -> tuple[SeedResponse, bool]:
    """
    Create a seed/snapshot from the current session state.
    Returns (response, session_already_ended) tuple.
    """
    response = await fetch_with_retry(
        client,
        "POST",
        f"{base_url}/create_seed",
        retry_options={"max_retries": 3, "base_delay_ms": 2000, "max_delay_ms": 15000},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={"session_id": session_id, "name": name},
        timeout=180.0,
    )

    if response.is_success:
        return response.json(), False

    error_text = response.text

    # Check for the specific "running sessions" error - snapshot might still be created
    if response.status_code == 400 and "running sessions" in error_text:
        print(f"Seed creation returned error: {error_text}")
        print(f"Polling kubectl to check if snapshot '{name}' was created anyway...")

        if await poll_for_snapshot_creation(name, timeout_seconds=90, poll_interval=10):
            print(f"Snapshot '{name}' was successfully created despite API error")

            # Also check if Meilisearch snapshot was created
            print("Checking if Meilisearch snapshot was also created...")
            if await poll_for_meilisearch_snapshot_creation(
                name, timeout_seconds=90, poll_interval=10
            ):
                print(
                    f"Meilisearch snapshot 'meilisearch-{name}' was successfully created"
                )
            else:
                print(
                    f"Warning: Meilisearch snapshot 'meilisearch-{name}' was not found"
                )

            # Poll until session is no longer LOCKED before ending it
            await poll_until_not_locked(client, base_url, session_id)

            # End the session since we're not going through normal flow
            try:
                print(f"Ending session {session_id}...")
                await end_session(client, base_url, session_id, api_key)
            except Exception as e:
                print(f"Warning: Failed to end session: {e}")

            return {"seed_id": name}, True  # Session already ended
        else:
            raise RuntimeError(
                f"Snapshot '{name}' was not created after 90 seconds of polling"
            )

    raise RuntimeError(f"Failed to create seed: {response.status_code} - {error_text}")


def create_seed_fire_and_forget(
    client: httpx.AsyncClient,
    base_url: str,
    session_id: str,
    name: str,
    api_key: str,
) -> None:
    """
    Fire off a seed creation request without waiting for response.
    """
    asyncio.create_task(
        client.post(
            f"{base_url}/create_seed",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={"session_id": session_id, "name": name},
            timeout=180.0,
        )
    )
    print(f"Fire-and-forget: seed creation request sent for '{name}'")


async def poll_for_snapshot_creation(
    snapshot_name: str,
    timeout_seconds: int = 90,
    poll_interval: int = 10,
) -> bool:
    """
    Poll kubectl to check if a snapshot was created.
    Returns True if snapshot exists, False if timeout reached.
    """
    elapsed = 0
    while elapsed < timeout_seconds:
        print(
            f"Checking for snapshot '{snapshot_name}' ({elapsed}s/{timeout_seconds}s)..."
        )

        if snapshot_exists(snapshot_name):
            return True

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    return False


async def poll_for_meilisearch_snapshot_creation(
    snapshot_name: str,
    timeout_seconds: int = 90,
    poll_interval: int = 10,
) -> bool:
    """
    Poll kubectl to check if a Meilisearch snapshot was created.
    Meilisearch snapshots follow the naming convention 'meilisearch-{snapshot_name}'.
    Returns True if snapshot exists, False if timeout reached.
    """
    meilisearch_snapshot_name = f"meilisearch-{snapshot_name}"
    elapsed = 0
    while elapsed < timeout_seconds:
        print(
            f"Checking for Meilisearch snapshot '{meilisearch_snapshot_name}' ({elapsed}s/{timeout_seconds}s)..."
        )

        if snapshot_exists(meilisearch_snapshot_name):
            return True

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    return False


async def end_session(
    client: httpx.AsyncClient, base_url: str, session_id: str, api_key: str
) -> None:
    """End/stop the session."""
    response = await fetch_with_retry(
        client,
        "POST",
        f"{base_url}/{session_id}/stop",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={},
    )

    if not response.is_success:
        raise RuntimeError(f"Failed to end session: {response.status_code}")


async def ensure_snapshot_exists(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    json_path: str,
    overwrite: bool = False,
    dry_run: bool = False,
    fire_and_forget: bool = False,
    visited: set[str] | None = None,
    app_context: str | None = None,
    processed_snapshots: set[str] | None = None,
    override_name: str | None = None,
) -> str:
    """
    Ensure a snapshot exists for the given JSON file.
    Recursively creates base snapshots if needed.
    Returns the snapshot name.

    Args:
        visited: Tracks file paths in current recursion chain (circular dependency detection)
        processed_snapshots: Tracks snapshots already processed across all files (avoid duplicate work)
        override_name: Optional snapshot name to use instead of calculating from file path
    """
    if visited is None:
        visited = set()
    if processed_snapshots is None:
        processed_snapshots = set()

    full_path = str(Path(json_path).resolve())

    if full_path in visited:
        raise RuntimeError(f"Circular dependency detected: {full_path}")
    visited.add(full_path)

    # Determine app context: use provided one, or derive from this file's parent folder
    current_app_context = app_context or Path(json_path).resolve().parent.name

    # Use override name if provided, otherwise calculate from file path
    snapshot_name = (
        override_name
        if override_name
        else calculate_snapshot_name(json_path, current_app_context)
    )

    print(f"\n{'=' * 60}")
    print(f"Processing: {json_path}")
    print(f"App context: {current_app_context}")
    print(f"Snapshot name: {snapshot_name}")

    # Check if snapshot already exists
    exists = snapshot_exists(snapshot_name)
    print(f"Snapshot exists: {exists}")

    # Skip if we've already processed this snapshot in this run (handles --overwrite case too)
    if snapshot_name in processed_snapshots:
        print(f"Snapshot '{snapshot_name}' already processed in this run, skipping.")
        visited.discard(full_path)
        return snapshot_name

    if exists and not overwrite:
        print(f"Snapshot '{snapshot_name}' already exists, skipping.")
        processed_snapshots.add(snapshot_name)
        visited.discard(full_path)
        return snapshot_name

    if exists and overwrite:
        print(f"Overwrite enabled, will delete and recreate '{snapshot_name}'")
        delete_snapshot(snapshot_name, dry_run=dry_run)

        # Also delete Meilisearch snapshot if it exists
        meilisearch_snapshot_name = f"meilisearch-{snapshot_name}"
        if snapshot_exists(meilisearch_snapshot_name):
            print(
                f"Meilisearch snapshot exists, deleting '{meilisearch_snapshot_name}'"
            )
            delete_snapshot(meilisearch_snapshot_name, dry_run=dry_run)
        else:
            print(
                f"Meilisearch snapshot '{meilisearch_snapshot_name}' does not exist, skipping deletion"
            )

    # Load the seed file
    with open(full_path, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    base_snapshot_name: str | None = None

    if is_diff_seed_file(data):
        # Recursively ensure base snapshot exists
        base_id = data["base_id"]
        base_file_path = resolve_base_file_path(json_path, base_id)
        print(f"This is a diff file with base_id: {base_id}")
        print(f"Base file path: {base_file_path}")

        base_snapshot_name = await ensure_snapshot_exists(
            client=client,
            base_url=base_url,
            api_key=api_key,
            json_path=base_file_path,
            overwrite=overwrite,
            dry_run=dry_run,
            fire_and_forget=fire_and_forget,
            visited=visited,
            app_context=current_app_context,
            processed_snapshots=processed_snapshots,
        )
        print(f"\nBack to processing: {json_path}")
        print(f"Base snapshot ready: {base_snapshot_name}")

    # Now create this snapshot
    if dry_run:
        print(f"[DRY-RUN] Would create snapshot: {snapshot_name}")
        if base_snapshot_name:
            print(f"[DRY-RUN]   - Start session from base: {base_snapshot_name}")
            print(
                f"[DRY-RUN]   - Apply {len(data.get('transactions', []))} transactions"
            )
        else:
            print("[DRY-RUN]   - Start fresh session")
            print("[DRY-RUN]   - Seed full data")
        print(f"[DRY-RUN]   - Create seed with name: {snapshot_name}")
        processed_snapshots.add(snapshot_name)
        visited.discard(full_path)
        return snapshot_name

    # Actually create the snapshot
    print(f"\nCreating snapshot: {snapshot_name}")

    # If we have a base snapshot, make sure it's ready before starting session
    if base_snapshot_name:
        if not snapshot_is_ready(base_snapshot_name):
            print(f"Base snapshot '{base_snapshot_name}' is not ready yet, waiting...")
            if not await wait_for_snapshot_ready(
                base_snapshot_name, timeout_seconds=300, poll_interval=10
            ):
                raise RuntimeError(
                    f"Base snapshot '{base_snapshot_name}' not ready after 300 seconds"
                )

    session_id: str | None = None
    session_ended: bool = False
    try:
        # Start session (with base snapshot if this is a diff)
        print(f"Starting session (base: {base_snapshot_name or 'none'})...")
        session_id = await start_session(client, base_url, api_key, base_snapshot_name)
        print(f"Session started: {session_id}")

        await poll_until_running(client, base_url, session_id)

        url = f"{base_url}/{session_id}"
        if is_diff_seed_file(data):
            # Apply only this file's transactions
            await apply_transactions(client, url, data["transactions"])
            print(
                "\nSkipping Meilisearch index creation for diff-based seed (indexes inherited from base snapshot)"
            )
        else:
            # Wipe and insert all data first
            print("Seeding full database...")
            await seed_full_data(client, url, data)

            # Create Meilisearch indexes after seeding - change stream will auto-sync to Meilisearch
            print("\nCreating Meilisearch search indexes after seeding...")
            await create_meilisearch_indices(client, url, current_app_context)

        print("Creating seed...")
        if fire_and_forget:
            create_seed_fire_and_forget(
                client, base_url, session_id, snapshot_name, api_key
            )
            session_ended = False
        else:
            seed_response, session_ended = await create_seed(
                client, base_url, session_id, snapshot_name, api_key
            )
            print(f"Seed created: {seed_response}")
            print(f"seed_id: {seed_response['seed_id']}")

            # Poll until session is no longer LOCKED (snapshot creation in progress)
            if not session_ended:
                await poll_until_not_locked(client, base_url, session_id)

        # Mark as processed
        processed_snapshots.add(snapshot_name)
        visited.discard(full_path)  # Allow re-entry from different chain

        return snapshot_name

    finally:
        if session_id and not session_ended and not fire_and_forget:
            try:
                print(f"Ending session {session_id}...")
                await end_session(client, base_url, session_id, api_key)
            except Exception as e:
                print(f"Warning: Failed to end session: {e}")


def collect_json_files(path: str) -> list[str]:
    """
    Collect JSON files to process.
    If path is a file, return it as a single-item list.
    If path is a directory, return all .json files in it (non-recursive).
    """
    p = Path(path)

    if p.is_file():
        if p.suffix.lower() != ".json":
            raise ValueError(f"File must be a JSON file: {path}")
        return [str(p)]

    if p.is_dir():
        json_files = sorted(p.glob("*.json"))
        if not json_files:
            raise ValueError(f"No JSON files found in directory: {path}")
        return [str(f) for f in json_files]

    raise ValueError(f"Path does not exist: {path}")


async def seed_remote(args: argparse.Namespace) -> None:
    path: str = args.path
    env: Environment = args.env
    overwrite: bool = args.overwrite
    dry_run: bool = args.dry_run
    fire_and_forget: bool = args.fire_and_forget
    snapshot_name_override: str | None = args.name

    env_config = ENVIRONMENTS[env]
    base_url = env_config["base_url"]
    api_key_env = env_config["api_key_env"]
    api_key = os.environ.get(api_key_env)

    if not api_key:
        raise RuntimeError(
            f"{api_key_env} environment variable is required for {env} environment"
        )

    # Collect all JSON files to process
    json_files = collect_json_files(path)

    # Validate --name is only used with a single file
    if snapshot_name_override and len(json_files) > 1:
        raise ValueError(
            f"--name parameter can only be used with a single JSON file, but {len(json_files)} files were found"
        )

    print(f"{'=' * 60}")
    print("Seed Script")
    print(f"{'=' * 60}")
    print(f"Path: {path}")
    print(f"JSON files to process: {len(json_files)}")
    for f in json_files:
        print(f"  - {f}")
    print(f"Environment: {env}")
    print(f"Overwrite: {overwrite}")
    print(f"Dry run: {dry_run}")
    print(f"Fire and forget: {fire_and_forget}")
    print(f"Base URL: {base_url}")

    # Switch kubernetes context
    if not dry_run:
        switch_kube_context(env)
    else:
        print(f"[DRY-RUN] Would switch to context: {env_config['kube_context']}")

    # Detect correctly if we use inital_data.json. Otherwise this used `app`
    if path.endswith("initial_data.json"):
        app_context = path.split("/")[-3]
    else:
        app_context = None

    # Track all created snapshots (shared across all files to avoid duplicate work)
    processed_snapshots: set[str] = set()
    created_snapshots: list[str] = []

    async with httpx.AsyncClient() as client:
        for json_file in json_files:
            print(f"\n{'#' * 60}")
            print(f"# Processing file: {json_file}")
            print(f"{'#' * 60}")

            snapshot_name = await ensure_snapshot_exists(
                client=client,
                base_url=base_url,
                api_key=api_key,
                json_path=json_file,
                overwrite=overwrite,
                dry_run=dry_run,
                fire_and_forget=fire_and_forget,
                visited=set(),  # Fresh visited set per top-level file
                processed_snapshots=processed_snapshots,
                app_context=app_context,
                override_name=snapshot_name_override,
            )
            created_snapshots.append(snapshot_name)

    print(f"\n{'=' * 60}")
    print("Complete!")
    print(f"{'=' * 60}")
    print(f"Snapshots created/verified: {len(created_snapshots)}")
    for snap in created_snapshots:
        print(f"  - {snap}")


async def do_seed_local(
    client: httpx.AsyncClient, url: str, path: str, app_context: str
) -> None:
    full_path = str(Path(path).resolve())

    current_app_context = app_context or Path(path).resolve().parent.name

    with open(full_path, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    if is_diff_seed_file(data):
        base_id = data["base_id"]
        print(f"Encountered diff seed file with base_id: {base_id}")
        base_file_path = resolve_base_file_path(path, base_id)
        await do_seed_local(client, url, base_file_path, current_app_context)

        print(f"Applying {len(data['transactions'])} diff transactions from {path}...")
        await apply_transactions(client, url, data["transactions"])
    else:
        print(f"Seeding full data for {path}")
        await seed_full_data(client, url, data)

        print(f"Creating Meilisearch indices for {path}...")
        await create_meilisearch_indices(client, url, current_app_context)


async def seed_local(args: argparse.Namespace) -> None:
    path: str = args.path
    if Path(path).is_dir():
        raise Exception("Only single JSON file is supported for local seeding")

    if path.endswith("initial_data.json"):
        app_context = path.split("/")[-3]
    else:
        app_context = None

    async with httpx.AsyncClient() as client:
        await do_seed_local(client, args.url, path, app_context)


async def main() -> None:
    """Main entry point."""
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Seed database and create volume snapshots",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    parser_remote = subparsers.add_parser(
        "remote",
        help="Seed via orchestrator service session",
    )
    parser_remote.set_defaults(func=seed_remote)

    parser_remote.add_argument(
        "--path",
        metavar="json-file-or-folder",
        help="Path to a seed JSON file or folder containing JSON files",
    )
    parser_remote.add_argument(
        "--env",
        required=True,
        choices=["local", "staging", "production"],
        help="Environment (staging or production)",
    )
    parser_remote.add_argument(
        "--name",
        type=str,
        help="Override snapshot name (only valid when path is a single JSON file)",
    )
    parser_remote.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and recreate all snapshots in the dependency chain",
    )
    parser_remote.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually creating/deleting snapshots",
    )
    parser_remote.add_argument(
        "--fire-and-forget",
        action="store_true",
        help="After calling create_seed, move on immediately without checking response or waiting",
    )

    parser_local = subparsers.add_parser(
        "local", help="Seed local storage service directly"
    )
    parser_local.set_defaults(func=seed_local)

    parser_local.add_argument(
        "--path",
        metavar="json-file-or-folder",
        help="Path to a seed JSON file or folder containing JSON files",
    )

    parser_local.add_argument(
        "--url", type=str, help="URL of storage service to seed", required=True
    )

    args = parser.parse_args()

    if hasattr(args, "func"):
        await args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error running seed script: {e}", file=sys.stderr)
        sys.exit(1)
