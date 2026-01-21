# Dojo Figma Evaluation

Self-contained task verification system for Figma/FigJam tasks.

## Structure

```
dojo-figma-eval/
├── tasks/           # Task JSON definitions
├── rewards/         # Reward functions
│   ├── backend.py   # Backend interface for querying MongoDB
│   └── figma_v2.py  # Figma-specific validation functions
├── traces/          # Execution traces (auto-generated)
├── server.py        # FastAPI verification server
├── verify-task.sh   # CLI verification script
├── pyproject.toml   # Python dependencies
└── README.md        # This file
```

## Quick Start

### 1. Start Prerequisites

```bash
# Terminal 1: Storage server (in dojo-spas repo)
cd local-server && make up

# Terminal 2: Seed database (in dojo-spas repo)
pnpm tsx scripts/seed_local.ts figma/app/initial_data.json

# Terminal 3: Figma frontend (in dojo-spas repo)
cd figma/app && pnpm dev
```

### 2. Start Verification Server

```bash
cd dojo-figma-eval
uv run python server.py
```

Server runs at `http://localhost:8002`

### 3. Run Verification

```bash
# Via CLI script
./verify-task.sh create-sticky-note-v2

# Or via curl
curl -X POST http://localhost:8002/verify \
  -H "Content-Type: application/json" \
  -d '{"task_id": "create-sticky-note-v2"}'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/verify` | POST | Run task verification |
| `/tasks` | GET | List available tasks |
| `/tasks/{id}` | GET | Get task details |
| `/functions` | GET | List reward functions |

## Creating New Tasks

### 1. Create Task JSON

Create `tasks/my-new-task-v2.json`:

```json
{
  "spa": "figma",
  "version": "2.0",
  "id": "my-new-task-v2",
  "name": "My New Task",
  "description": "Description of what the task does",
  "tier": "beginner",
  "initial_backend_state_name": "default_backend",
  "instructions": "{\"user_prompt\": \"Instructions for the agent...\", \"success_criteria\": \"What success looks like...\"}",
  "reward_function": "_validate_figma_my_new_task",
  "max_steps": 15,
  "timeout_seconds": 120,
  "metadata": "{\"category\": \"FigJam\", \"difficulty\": \"easy\"}",
  "environment_type": "mcp",
  "trace_id": "my-new-task-v2",
  "initial_state": "{}",
  "environment": "{\"type\": \"url\", \"path\": \"http://localhost:5173/figjam/file-5\"}",
  "image": "",
  "env_version": "1.0"
}
```

### 2. Create Reward Function

Add to `rewards/figma_v2.py`:

```python
def _validate_figma_my_new_task(
    backend: Backend,
    final_state_frontend: Dict[str, Any],
    final_answer: str = ""
) -> TaskScore:
    """Validate my new task."""
    errors: List[str] = []
    checks_passed: List[str] = []

    # Your validation logic here
    # Use backend.query({"collection": "...", "filter": {...}})

    return TaskScore(
        score=1.0 if not errors else 0.0,
        metadata=ScoreMetadata(
            success_accumulator=checks_passed,
            error_accumulator=errors
        )
    )
```

### 3. Test

```bash
./verify-task.sh my-new-task-v2
```

## Available Collections

Query these collections in reward functions:

- `currentUser` - Current authenticated user
- `users` - All users
- `teams` - Team definitions
- `projects` - Projects within teams
- `files` - Design files
- `pages` - Pages within files
- `nodes` - Design nodes (shapes, sticky notes, etc.)
- `components` - Reusable components
- `componentSets` - Component variant sets
- `styles` - Color, text, effect styles
- `variables` - Design tokens
- `variableCollections` - Variable collections
