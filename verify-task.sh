#!/bin/bash

# Verify a Figma task by ID
# Usage: ./verify-task.sh <task_id>
#
# Examples:
#   ./verify-task.sh create-sticky-note-v2
#   ./verify-task.sh create-shape-with-text-v2
#
# Prerequisites:
#   1. Storage server running: cd local-server && make up
#   2. Figma app running: cd figma/app && pnpm dev
#   3. This verify server running: uv run python server.py

if [ -z "$1" ]; then
  echo "Figma Task Verification"
  echo ""
  echo "Usage: ./verify-task.sh <task_id>"
  echo ""
  echo "Arguments:"
  echo "  task_id: The ID of the Figma task to verify (required)"
  echo ""
  echo "Examples:"
  echo "  ./verify-task.sh create-sticky-note-v2"
  echo "  ./verify-task.sh create-shape-with-text-v2"
  echo ""
  echo "Available tasks:"
  if [ -d "tasks" ]; then
    ls -1 tasks/*.json 2>/dev/null | xargs -I {} basename {} .json | sed 's/^/  - /'
  else
    echo "  (no tasks found)"
  fi
  exit 1
fi

TASK_ID="$1"
SERVER_URL="${FIGMA_VERIFY_URL:-http://localhost:8002}"

# Check if task exists
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TASK_FILE="$SCRIPT_DIR/tasks/$TASK_ID.json"

if [ ! -f "$TASK_FILE" ]; then
  echo "Error: Task '$TASK_ID' not found at $TASK_FILE"
  echo ""
  echo "Available tasks:"
  ls -1 "$SCRIPT_DIR/tasks"/*.json 2>/dev/null | xargs -I {} basename {} .json | sed 's/^/  - /'
  exit 1
fi

echo "Verifying task: $TASK_ID"
echo "Server: $SERVER_URL"
echo ""

curl -s -X POST "$SERVER_URL/verify" \
  -H "Content-Type: application/json" \
  -d "{\"task_id\": \"$TASK_ID\", \"frontend_state\": {}, \"final_answer\": \"\"}" | jq .
