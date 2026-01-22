#!/bin/bash

# Verify a Figma task by ID
# Usage: ./verify-task.sh <task_id> [final_answer_json]
#
# Examples:
#   ./verify-task.sh login-screen-react-extraction-v2
#   ./verify-task.sh login-screen-react-extraction-v2 '{"framework":"react","has_svg":true}'
#
# Prerequisites:
#   1. Storage server running: cd local-server && make up
#   2. Figma app running: cd figma/app && pnpm dev
#   3. This verify server running: uv run python server.py

if [ -z "$1" ]; then
  echo "Figma Task Verification"
  echo ""
  echo "Usage: ./verify-task.sh <task_id> [final_answer_json]"
  echo ""
  echo "Arguments:"
  echo "  task_id: The ID of the Figma task to verify (required)"
  echo "  final_answer_json: JSON string for final_answer (optional)"
  echo ""
  echo "Examples:"
  echo "  ./verify-task.sh login-screen-react-extraction-v2"
  echo "  ./verify-task.sh login-screen-react-extraction-v2 '{\"framework\":\"react\",\"has_svg\":true}'"
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
FINAL_ANSWER="${2:-}"
SERVER_URL="${FIGMA_VERIFY_URL:-http://localhost:8003}"

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

# If no final_answer provided, check for trace file with final_answer field
if [ -z "$FINAL_ANSWER" ]; then
  TRACE_FILE="$SCRIPT_DIR/traces/$TASK_ID.json"
  if [ -f "$TRACE_FILE" ]; then
    # Try to extract final_answer from trace file if it exists
    TRACE_FINAL_ANSWER=$(jq -r '.final_answer // empty' "$TRACE_FILE" 2>/dev/null)
    if [ -n "$TRACE_FINAL_ANSWER" ] && [ "$TRACE_FINAL_ANSWER" != "null" ]; then
      FINAL_ANSWER="$TRACE_FINAL_ANSWER"
      echo "Using final_answer from trace file: $TRACE_FILE"
    fi
  fi
fi

# Escape the final answer for JSON
if [ -n "$FINAL_ANSWER" ]; then
  # Use jq to properly escape the JSON string
  ESCAPED_ANSWER=$(echo -n "$FINAL_ANSWER" | jq -Rs .)
else
  ESCAPED_ANSWER='""'
fi

echo "Verifying task: $TASK_ID"
echo "Server: $SERVER_URL"
if [ -n "$FINAL_ANSWER" ]; then
  echo "Final answer: ${FINAL_ANSWER:0:100}..."
fi
echo ""

# Build the JSON payload
PAYLOAD=$(jq -n \
  --arg task_id "$TASK_ID" \
  --argjson final_answer "$ESCAPED_ANSWER" \
  '{task_id: $task_id, frontend_state: {}, final_answer: $final_answer}')

curl -s -X POST "$SERVER_URL/verify" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" | jq .
