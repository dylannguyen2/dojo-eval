---
description: Execute multiple Figma tasks with automatic verification
---

# Execute Multiple Figma Tasks with Auto-Verification

Execute multiple Figma/FigJam tasks using MCP tools, then automatically run verification for each.

## Input
Markdown list of task IDs:
```
$ARGUMENTS
```

Example input:
```
- login-screen-react-extraction-v2
- button-component-variants-v2
- input-fields-spatial-analysis-v2
```

## ⚠️ CRITICAL RULES - READ FIRST ⚠️

**THESE RULES MUST BE FOLLOWED AT ALL TIMES:**

1. **🚫 NEVER LOOK AT THE REWARD FUNCTION FILE**
   - Do NOT read, inspect, or reference `rewards/figma_v2.py`
   - Do NOT read any file in the `rewards/` directory
   - Execute the task based ONLY on the `user_prompt` in the task file
   - Looking at reward functions invalidates the evaluation

2. **🚫 NEVER SEND BACKEND QUERY CURL REQUESTS**
   - All task operations must go through MCP tools ONLY
   - Do NOT query localhost:8081 to inspect or verify data

3. **🚫 ONLY EXECUTE VIA MCP - NEVER BY GUI/PLAYWRIGHT**
   - Use MCP tools exclusively for all operations
   - Do NOT use Playwright browser automation for creating/modifying content
   - Do NOT manually click through the GUI
   - MCP tools are the authoritative interface for this evaluation

## Prerequisites

Before running, ensure these services are running:
1. **Docker containers** (MongoDB, storage server): `cd local-server && make up`
2. **Figma frontend**: `cd figma/app && pnpm dev` (runs on localhost:5173)
3. **Figma MCP server**: `cd figma/figma-mcp && pnpm dev` (runs on localhost:8002)
4. **Figma verify server**: `cd figma/evaluation && uv run python server.py` (runs on localhost:8003)

## Workflow

Process each task ID from the input list sequentially:

### Step 1: Parse task list

Extract task IDs from the markdown list in `$ARGUMENTS`.
- Remove markdown list markers (`-`, `*`, `1.`)
- Trim whitespace
- Create array of task IDs to process

### Step 2: For each task ID, execute the following steps:

#### Step 2.1: Read task prompt
Read: `~/Documents/dojo-figma-eval/tasks/{TASK_ID}.json`
Extract `user_prompt` from `instructions` field.

**⚠️ REMINDER - CRITICAL RULES:**
- **🚫 NEVER READ REWARD FUNCTIONS** - Do NOT read `rewards/figma_v2.py` or any file in `rewards/` directory
- **🚫 NEVER READ `initial_data.json`** - This is ground truth data for verification
- **🚫 NEVER SEND BACKEND CURL REQUESTS**
- **🚫 ALL OPERATIONS VIA MCP ONLY** - No Playwright, no GUI clicks, no browser automation

**Execute the task based SOLELY on the `user_prompt` instructions. Do not look at any verification or ground truth files.**

#### Step 2.2: Understand task context

Review the task file to understand:
- File ID and node IDs involved
- Required operations (create, modify, inspect)
- Expected outcomes
- **Expected answer format**: Many tasks include a "Provide your final answer as JSON:" section in the `user_prompt` - note this format for the `final_answer` field in the trace

**⚠️ DO NOT use Playwright/browser for task execution** - MCP tools only!

#### Step 2.3: Execute operations (MCP ONLY)

**⚠️ CRITICAL: Use ONLY MCP tools for ALL operations. NO Playwright. NO GUI clicks.**

**Strategy:** Execute all operations through Figma MCP tools. The MCP server provides programmatic access to all Figma/FigJam functionality.

##### Available Figma MCP Tools:

| Operation | MCP Tool |
|-----------|----------|
| Get layer metadata | `mcp_figma-mcp_get_metadata(nodeId, fileKey, clientLanguages, clientFrameworks)` |
| Get design tokens/variables | `mcp_figma-mcp_get_variable_defs(nodeId, fileKey, clientLanguages, clientFrameworks)` |
| Get FigJam content | `mcp_figma-mcp_get_figjam(nodeId, fileKey, clientLanguages, clientFrameworks)` |
| Get design context/code | `mcp_figma-mcp_get_design_context(stage, language)` |
| Get user info | `mcp_figma-mcp_whoami()` |
| Get screenshot | `mcp_official-figma-mcp_get_screenshot(nodeId, fileKey, clientLanguages, clientFrameworks)` |

**Note:** These tools provide both inspection AND modification capabilities through the MCP server.
All task operations should be performed using these MCP tools exclusively.

#### Step 2.4: Save trace file

Write trace to: `~/Documents/dojo-figma-eval/traces/{TASK_ID}.json`

**Trace Format:**
```json
{
  "task_id": "{TASK_ID}",
  "steps": [
    {
      "action": "Get file metadata to understand structure",
      "command": "mcp_figma-mcp_get_metadata(nodeId: \"0:1\", fileKey: \"file-5\", clientLanguages: \"unknown\", clientFrameworks: \"unknown\")",
      "method": "mcp"
    },
    {
      "action": "Retrieve design tokens and variables",
      "command": "mcp_figma-mcp_get_variable_defs(nodeId: \"1:2\", fileKey: \"file-5\", clientLanguages: \"unknown\", clientFrameworks: \"unknown\")",
      "method": "mcp"
    }
  ],
  "final_answer": "{\"key\": \"value\"}"
}
```

**Fields:**
- `task_id`: The task identifier
- `steps`: Array of MCP tool calls executed during the task
- `final_answer`: String containing the final answer as JSON (format specified in the task's `user_prompt`)

**Note:** All traces should only contain MCP tool calls. No Playwright or browser operations.

**CRITICAL REQUIREMENTS:**
- **NO ELLIPSIS** - Do NOT use `...` or `... (N more items)` abbreviations
- **VALID JSON** - Trace must be parseable with `json.loads()`
- **COMPLETE ARRAYS** - Write out ALL array elements, not summaries
- **EXACT COMMANDS** - Include full parameter values as executed

#### Step 2.5: CRITICAL - Run Automatic Verification

**IMMEDIATELY after saving the trace file**, run verification:

```bash
cd ~/Documents/dojo-figma-eval && ./verify-task.sh {TASK_ID}
```

This will:
1. Read the final_answer from the trace file
2. Query the storage backend for current state
3. Run the reward function against the backend data
4. Return the verification result: `{ score, passed, message, errors, successes }`

**Note:** The trace file MUST exist before running verification, as verify-task.sh reads the `final_answer` field from it.

#### Step 2.6: Record result

Store the verification result for this task to include in the final summary.

### Step 3: Report results

After processing all tasks, report a summary of results:

**Summary Format:**
```
📊 BATCH EXECUTION SUMMARY
==========================

Processed {N} tasks:

✅ PASSED ({X}/{N}):
- {task-id-1}: Score 1.0
- {task-id-2}: Score 1.0

❌ FAILED ({Y}/{N}):
- {task-id-3}: Score {score} - {error message}
- {task-id-4}: Score {score} - {error message}

Overall Success Rate: {X}/{N} ({percentage}%)

---

DETAILED RESULTS:
=================

Task: {task-id-1}
Status: ✅ PASSED
Score: 1.0
Message: {success message}
Final Answer: {final_answer}
Trace: ~/Documents/dojo-figma-eval/traces/{task-id-1}.json

---

Task: {task-id-2}
Status: ❌ FAILED
Score: {score}
Message: {message}
Errors:
- {error 1}
- {error 2}
Final Answer: {final_answer}
Trace: ~/Documents/dojo-figma-eval/traces/{task-id-2}.json

---

[... repeat for each task ...]
```

---

## ⚠️ NO GUI/PLAYWRIGHT OPERATIONS ALLOWED

**This section has been removed. ALL operations must be performed via MCP tools.**

Do NOT use:
- ❌ Playwright browser automation
- ❌ Manual GUI clicks
- ❌ Browser snapshots for task execution
- ❌ Direct browser interaction

Instead use:
- ✅ MCP tools exclusively
- ✅ `mcp_figma-mcp_*` function calls
- ✅ Programmatic API access through MCP server

---

## Figma Evaluation Structure

All Figma evaluation files are in `~/Documents/dojo-figma-eval/`:
```
dojo-figma-eval/
├── tasks/           # ✅ READ THESE: Task JSON definitions with user_prompt
├── rewards/         # 🚫 FORBIDDEN: Reward/verification functions - DO NOT READ
├── traces/          # ✅ WRITE HERE: Save execution traces after completion
├── server.py        # Verification server (called by verify-task.sh)
├── verify-task.sh   # ✅ RUN THIS: CLI verification script after task completion
└── pyproject.toml   # Python dependencies
```

**Key:**
- ✅ = Safe to read/use during task execution
- 🚫 = FORBIDDEN - Reading these invalidates the evaluation

---

## Figma Collections Reference

The Figma app uses these MongoDB collections:
- `currentUser` - Current authenticated user
- `users` - All users
- `teams` - Team definitions with members
- `projects` - Projects within teams
- `files` - Design files (type: "figma" or "figjam")
- `pages` - Pages within files
- `nodes` - All design nodes (frames, shapes, sticky notes, etc.)
- `components` - Reusable components
- `componentSets` - Component variant sets
- `styles` - Color, text, and effect styles
- `variables` - Design tokens
- `variableCollections` - Variable collection definitions

**⚠️ WARNING:** Do NOT query these collections directly via curl to localhost:8081 during task execution!

---

## 🔴 FINAL REMINDERS - MUST FOLLOW

Before executing ANY task, remember:

1. **🚫 NEVER read reward function files** - Do NOT look at `rewards/figma_v2.py` or `rewards/` directory
2. **🚫 NEVER send backend curl requests** - Except Step 0 database reset
3. **🚫 NEVER use Playwright/GUI** - MCP tools ONLY for all operations
4. **✅ ONLY execute via MCP tools** - This is the ONLY valid execution method
5. **✅ ONLY use the `user_prompt`** - Execute based solely on task instructions, not verification logic
6. **✅ ALWAYS run verification** - `./verify-task.sh {TASK_ID}` after each task completion
7. **✅ PROCESS SEQUENTIALLY** - Complete each task fully (execute + verify) before moving to the next

**Violation of these rules will invalidate the evaluation results.**

---

## 🚫 FORBIDDEN FILES - DO NOT READ

The following files must NEVER be read during task execution:
- `rewards/figma_v2.py` - Contains reward/verification functions
- `rewards/backend.py` - Contains backend utilities for verification
- `rewards/__init__.py` - Reward module initialization
- Any other file in the `rewards/` directory

**Reading these files will compromise the integrity of the evaluation.**
