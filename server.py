#!/usr/bin/env python3
"""
Figma Verification Server

Simple HTTP server that runs reward function verification for Figma tasks.
Called by slash commands after task execution to check if task succeeded.

Usage:
  cd dojo-figma-eval && uv run python server.py

Endpoints:
  POST /verify - Run verification for a task
  GET /health - Health check
  GET /tasks - List available tasks
  GET /functions - List available reward functions
"""

import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Paths - all relative to this file's directory
BASE_DIR = Path(__file__).parent.absolute()
REWARDS_DIR = BASE_DIR / "rewards"
TASKS_DIR = BASE_DIR / "tasks"
TRACES_DIR = BASE_DIR / "traces"

# Default storage server URL
DEFAULT_STORAGE_URL = os.environ.get("STORAGE_URL", "http://localhost:8081")

app = FastAPI(title="Figma Verification Server", version="1.0.0")

# CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class VerifyRequest(BaseModel):
    task_id: str
    frontend_state: Optional[Dict[str, Any]] = None
    final_answer: Optional[str] = ""


class VerifyResponse(BaseModel):
    score: float
    passed: bool
    message: str
    errors: list[str] = []
    successes: list[str] = []


class StorageBackend:
    """Backend for querying the storage server."""

    def __init__(self, storage_url: str = DEFAULT_STORAGE_URL):
        self.storage_url = storage_url

    def query(self, query: Dict[str, Any]) -> Any:
        """Execute a query against the storage server."""
        try:
            response = requests.post(
                f"{self.storage_url}/query",
                json=query,
                timeout=30
            )
            if response.status_code != 200:
                return []
            result = response.json()
            return result.get("data", [])
        except Exception as e:
            print(f"Query failed: {e}")
            return []


def load_reward_functions(rewards_dir: Path = REWARDS_DIR) -> Dict[str, Any]:
    """Load all reward functions from the rewards directory."""
    functions: Dict[str, Any] = {}

    if not rewards_dir.exists():
        print(f"Rewards directory not found: {rewards_dir}")
        return functions

    # Create a fake 'rewards' package in sys.modules
    package_name = "rewards"

    if package_name not in sys.modules:
        pkg = types.ModuleType(package_name)
        pkg.__path__ = [str(rewards_dir)]
        pkg.__package__ = package_name
        sys.modules[package_name] = pkg

    # First, load backend.py as it's needed by other modules
    backend_file = rewards_dir / "backend.py"
    if backend_file.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                f"{package_name}.backend", backend_file,
                submodule_search_locations=[str(rewards_dir)]
            )
            if spec and spec.loader:
                backend_module = importlib.util.module_from_spec(spec)
                backend_module.__package__ = package_name
                sys.modules[f"{package_name}.backend"] = backend_module
                spec.loader.exec_module(backend_module)
        except Exception as e:
            print(f"Failed to load backend.py: {e}")
            return functions

    # Load each reward Python file
    for py_file in sorted(rewards_dir.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name == "backend.py":
            continue

        try:
            module_name = py_file.stem
            full_module_name = f"{package_name}.{module_name}"

            # Skip if already loaded
            if full_module_name in sys.modules:
                module = sys.modules[full_module_name]
            else:
                spec = importlib.util.spec_from_file_location(
                    full_module_name, py_file,
                    submodule_search_locations=[str(rewards_dir)]
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    module.__package__ = package_name
                    sys.modules[full_module_name] = module
                    spec.loader.exec_module(module)
                else:
                    continue

            # Find all functions starting with _validate
            for name in dir(module):
                if name.startswith("_validate"):
                    func = getattr(module, name)
                    if callable(func):
                        functions[name] = func

        except Exception as e:
            print(f"Failed to load {py_file.name}: {e}")

    print(f"Loaded {len(functions)} reward functions")
    return functions


def reload_reward_functions() -> Dict[str, Any]:
    """Reload all reward functions (clears cache and reloads from disk)."""
    # Clear cached modules
    modules_to_remove = [key for key in sys.modules.keys() if key.startswith("rewards")]
    for mod in modules_to_remove:
        del sys.modules[mod]

    return load_reward_functions()


# Load functions on startup
reward_functions = load_reward_functions()


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "spa": "figma",
        "storage_url": DEFAULT_STORAGE_URL,
        "reward_functions_loaded": len(reward_functions),
        "tasks_dir": str(TASKS_DIR),
        "rewards_dir": str(REWARDS_DIR),
    }


@app.post("/verify", response_model=VerifyResponse)
def verify(request: VerifyRequest):
    """Run verification for a Figma task."""
    global reward_functions

    # Reload reward functions to get latest changes
    reward_functions = reload_reward_functions()

    # Load task to get reward function name
    task_path = TASKS_DIR / f"{request.task_id}.json"
    if not task_path.exists():
        raise HTTPException(status_code=404, detail=f"Task not found: {task_path}")

    with open(task_path) as f:
        task = json.load(f)

    reward_function_name = task.get("reward_function", "")
    if not reward_function_name:
        raise HTTPException(status_code=400, detail="Task has no reward_function defined")

    # Get reward function
    reward_fn = reward_functions.get(reward_function_name)
    if not reward_fn:
        raise HTTPException(
            status_code=404,
            detail=f"Reward function '{reward_function_name}' not found. Available: {list(reward_functions.keys())}"
        )

    # Create backend
    backend = StorageBackend(DEFAULT_STORAGE_URL)

    # Get frontend state (use empty dict if not provided)
    frontend_state = request.frontend_state or {}

    try:
        # Call the reward function
        import inspect
        sig = inspect.signature(reward_fn)
        params = list(sig.parameters.keys())

        if len(params) >= 3:
            result = reward_fn(backend, frontend_state, request.final_answer or "")
        else:
            result = reward_fn(backend, frontend_state)

        score = result.get("score", 0.0)
        metadata = result.get("metadata", {})

        error_msgs = metadata.get("error_accumulator", [])
        success_msgs = metadata.get("success_accumulator", [])

        if error_msgs:
            message = "; ".join(error_msgs)
        elif success_msgs:
            message = "; ".join(success_msgs)
        else:
            message = "Task complete" if score == 1.0 else "Task incomplete"

        return VerifyResponse(
            score=score,
            passed=score == 1.0,
            message=message,
            errors=error_msgs,
            successes=success_msgs,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return VerifyResponse(
            score=0.0,
            passed=False,
            message=f"Verification error: {str(e)}",
            errors=[str(e)],
            successes=[],
        )


@app.get("/tasks")
def list_tasks():
    """List available Figma tasks."""
    tasks = []
    if TASKS_DIR.exists():
        for task_file in sorted(TASKS_DIR.glob("*.json")):
            try:
                with open(task_file) as f:
                    task = json.load(f)
                tasks.append({
                    "id": task_file.stem,
                    "name": task.get("name", task_file.stem),
                    "description": task.get("description", ""),
                    "reward_function": task.get("reward_function", ""),
                })
            except Exception:
                pass
    return {"tasks": tasks, "count": len(tasks)}


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    """Get task details."""
    task_path = TASKS_DIR / f"{task_id}.json"
    if not task_path.exists():
        raise HTTPException(status_code=404, detail=f"Task not found: {task_path}")

    with open(task_path) as f:
        task = json.load(f)

    return task


@app.get("/functions")
def list_functions():
    """List available reward functions."""
    return {"functions": list(reward_functions.keys()), "count": len(reward_functions)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8002))
    print(f"Starting Figma verification server on port {port}")
    print(f"Storage URL: {DEFAULT_STORAGE_URL}")
    print(f"Tasks directory: {TASKS_DIR}")
    print(f"Rewards directory: {REWARDS_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=port)
