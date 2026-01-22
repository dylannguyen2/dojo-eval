# Scripts Directory

This directory contains utility scripts for managing the Dojo SPAs project data.

## Available Scripts

### 1. Generate Collection IDs (`generate-collection-ids.ts`)

Generates deterministic `_id` fields for items in high-level collections (arrays) within JSON backend data files.

**Features:**

- Content-based hash IDs that remain stable across multiple runs
- Processes any top-level array collection in JSON files
- Can target specific collections or process all collections
- Dry-run mode to preview changes
- Creates automatic backups in `.backup/` directory
- Verbose mode for detailed output

**Usage:**

```bash
# From the scripts directory
cd scripts

# Generate IDs for all collections in a single file
pnpm run generate-ids weibo/app/initial_data.json

# Process all JSON files in a directory
pnpm run generate-ids --dir ../dojo-bench-customer-colossus/initial-backend-data/weibo

# Dry run to preview changes (recommended first)
pnpm run generate-ids weibo/app/initial_data.json --dry-run

# Dry run for a directory
pnpm run generate-ids --dir ../dojo-bench-customer-colossus/initial-backend-data/weibo --dry-run

# Only generate IDs for specific collections
pnpm run generate-ids weibo/app/initial_data.json --collections users,posts

# Process directory with specific collections only
pnpm run generate-ids --dir ../dojo-bench-customer-colossus/initial-backend-data/jd --collections users,posts

# Verbose output to see all generated IDs
pnpm run generate-ids weibo/app/initial_data.json -v

# Process single bench file
pnpm run generate-ids ../dojo-bench-customer-colossus/initial-backend-data/weibo/default_backend.json
```

**Options:**

- `--dir <path>` - Process all JSON files in the specified directory
- `--dry-run` - Preview changes without modifying the file(s)
- `--collections` - Comma-separated list of collections to process (e.g., users,posts)
- `--verbose` or `-v` - Show detailed output including generated IDs
- `--help` or `-h` - Show help message

**Examples:**

```bash
# Example 1: Generate IDs for all collections in weibo initial_data.json
pnpm run generate-ids weibo/app/initial_data.json

# Example 2: Preview what would be generated for xiaohongshu
pnpm run generate-ids xiaohongshu/app/initial_data.json --dry-run

# Example 3: Only process "users" and "posts" collections
pnpm run generate-ids jd/app/initial_data.json --collections users,posts

# Example 4: Generate IDs with verbose output
pnpm run generate-ids weibo/app/initial_data.json -v

# Example 5: Process all bench files in weibo directory
pnpm run generate-ids --dir ../dojo-bench-customer-colossus/initial-backend-data/weibo

# Example 6: Dry run for all files in a directory
pnpm run generate-ids --dir ../dojo-bench-customer-colossus/initial-backend-data/jd --dry-run
```

**ID Format:**

- IDs are generated as: `{collectionName}_{hash12chars}`
- Example: `users_a1b2c3d4e5f6`, `posts_9z8y7x6w5v4u`
- IDs are deterministic based on item content (excluding existing `_id`)

### 2. Merge Data (`merge-data.ts`)

Merges collections from an origin backend JSON file into target file(s) using content-hash comparison to detect duplicates.

**Features:**

- Content-based duplicate detection (ignores `_id` differences)
- Single file mode or batch directory mode
- Conflict detection when same `_id` has different content
- Creates backups in `.backup/` directory
- Dry-run mode to preview changes
- Verbose mode for detailed output

**Usage:**

```bash
# From the scripts directory
cd scripts

# Merge one file into another (single file mode)
pnpm run merge-data target.json origin.json

# Merge origin into all files in a directory (batch mode)
pnpm run merge-data --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json

# Dry run to preview changes (recommended first)
pnpm run merge-data target.json origin.json --dry-run

# Dry run for batch mode
pnpm run merge-data --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json --dry-run

# Verbose output to see item-by-item processing
pnpm run merge-data target.json origin.json -v
```

**Options:**

- `--target-dir <path>` - Process all JSON files in the specified directory (batch mode)
- `--dry-run` - Preview changes without modifying files
- `--verbose` or `-v` - Show detailed output including item-by-item changes
- `--help` or `-h` - Show help message

**How It Works:**

1. **Content Hashing**: Each item's content (excluding `_id`) is hashed
2. **Duplicate Detection**: Items with identical content are skipped
3. **Conflict Detection**: If same `_id` exists with different content, target version is kept and a warning is shown
4. **Backup Creation**: All modified files are backed up to `.backup/` directory

**Examples:**

```bash
# Example 1: Merge initial_data.json into a single backend file
pnpm run merge-data ../dojo-bench-customer-colossus/initial-backend-data/weibo/accept_search_suggestion_backend.json ../weibo/app/initial_data.json

# Example 2: Merge initial_data.json into ALL backend files in directory
pnpm run merge-data --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json

# Example 3: Preview what would be merged (dry-run)
pnpm run merge-data --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json --dry-run

# Example 4: See detailed processing with verbose mode
pnpm run merge-data target.json origin.json --dry-run -v
```

**Backup Directory Structure:**

Backups are stored in a `.backup/` directory relative to the target file(s):

```
dojo-bench-customer-colossus/initial-backend-data/weibo/
├── .backup/
│   ├── accept_search_suggestion_backend.json
│   ├── change_search_categories_backend.json
│   └── ...
├── accept_search_suggestion_backend.json
├── change_search_categories_backend.json
└── ...
```

This makes it easy to:

- Delete all backups: `rm -rf .backup/`
- Restore backups: `cp .backup/* .`

### 3. Generate Diff (`generate-diff.ts`)

Generates property-level diffs between backend files and a source file (initial_data.json). Uses hybrid matching (ID + content-hash) to handle auto-generated IDs.

**Features:**

- Property-level delta detection (tracks only changed properties)
- Hybrid matching: matches by `_id` first, then by content-hash for auto-generated IDs
- Detects added items and modified items separately
- Stores diffs in `.diff/` directory
- Single file mode or batch directory mode
- Dry-run mode to preview changes
- Verbose mode for detailed output

**Usage:**

```bash
# From the scripts directory
cd scripts

# Generate diff for a single backend file
pnpm run generate-diff backend_file.json initial_data.json

# Generate diffs for all backend files in a directory
pnpm run generate-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json

# Dry run to preview changes (recommended first)
pnpm run generate-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json --dry-run

# Verbose output to see item-by-item analysis
pnpm run generate-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json -v
```

**Options:**

- `--target-dir <path>` - Process all JSON files in the specified directory (batch mode)
- `--dry-run` - Preview changes without creating diff files
- `--verbose` or `-v` - Show detailed output including item-by-item changes
- `--help` or `-h` - Show help message

**How It Works:**

1. **Hybrid Matching**: For each backend item, tries to match by `_id` first, then by content-hash
2. **Modified Items**: Compares properties deeply, stores only changed properties with source's `_id`
3. **Added Items**: Items that don't exist in source (completely new)
4. **Diff Storage**: Saves diffs in `.diff/<filename>.diff.json`

**Diff Format:**

```json
{
  "users": {
    "modified": [
      {
        "_id": "user1",
        "changes": {
          "followersCount": 150,
          "bio": "Updated bio"
        }
      }
    ],
    "added": [
      {
        "_id": "custom_user_99",
        "name": "Task User",
        "avatar": "...",
        ...
      }
    ]
  }
}
```

**Examples:**

```bash
# Example 1: Generate diff for all weibo backend files
pnpm run generate-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json

# Example 2: Preview what diffs would be generated (dry-run)
pnpm run generate-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json --dry-run

# Example 3: Generate diff for single file with verbose output
pnpm run generate-diff ../dojo-bench-customer-colossus/initial-backend-data/weibo/accept_search_suggestion_backend.json ../weibo/app/initial_data.json -v
```

**Output Structure:**

```
dojo-bench-customer-colossus/initial-backend-data/weibo/
├── .diff/
│   ├── accept_search_suggestion_backend.diff.json
│   ├── create_post_with_mention_and_hashtag_backend.diff.json
│   └── ...
├── accept_search_suggestion_backend.json
├── create_post_with_mention_and_hashtag_backend.json
└── ...
```

### 4. Apply Diff (`apply-diff.ts`)

Applies property-level diffs to merged source data, creating enriched backend files that preserve both scraped enrichments and task-specific customizations.

**Features:**

- Smart property merging: overlays task-specific changes onto enriched data
- Handles missing diff files gracefully (uses merged data as-is)
- Preserves both scraped data enrichments AND task customizations
- Creates backups in `.backup/` directory
- Single file mode or batch directory mode
- Dry-run mode to preview changes
- Verbose mode for detailed output

**Usage:**

```bash
# From the scripts directory
cd scripts

# Apply diff for a single backend file
pnpm run apply-diff backend_file.json merged_data.json

# Apply diffs for all backend files in a directory
pnpm run apply-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/merged_data.json

# Dry run to preview changes (recommended first)
pnpm run apply-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/merged_data.json --dry-run

# Verbose output to see item-by-item processing
pnpm run apply-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/merged_data.json -v
```

**Options:**

- `--target-dir <path>` - Process all JSON files in the specified directory (batch mode)
- `--dry-run` - Preview changes without modifying files
- `--verbose` or `-v` - Show detailed output including item-by-item changes
- `--help` or `-h` - Show help message

**How It Works:**

1. **Load Diff**: Reads `.diff/<filename>.diff.json` (if exists)
2. **For Modified Items**: Overlays property changes onto merged data items
   ```typescript
   enrichedItem = { ...mergedDataItem, ...diff.changes };
   ```
3. **For Added Items**: Adds new items that don't exist in merged data
4. **No Diff**: If no diff file exists, uses merged data as-is (still enriches with scraped data)
5. **Backup**: Creates backup before overwriting backend file

**Examples:**

```bash
# Example 1: Apply diffs for all weibo backend files
pnpm run apply-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/merged_data.json

# Example 2: Preview what would be applied (dry-run)
pnpm run apply-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/merged_data.json --dry-run

# Example 3: Apply diff for single file with verbose output
pnpm run apply-diff ../dojo-bench-customer-colossus/initial-backend-data/weibo/accept_search_suggestion_backend.json ../weibo/app/merged_data.json -v
```

**Result:**

Each backend file will have:

- ✅ All scraped data enrichments (new fields, updated content)
- ✅ Task-specific customizations preserved (from diffs)
- ✅ Backup saved in `.backup/` directory

### 5. Sync Backend IDs (`sync_backend_ids.py`)

Syncs `_id` fields from a source backend JSON file to target files by matching items based on their content hash (excluding top-level `_id`).

**Features:**

- Content-based hash matching (SHA256) that excludes only top-level `_id` fields
- Matches items across source and target files based on content similarity
- Updates target IDs to match source IDs when content matches
- Creates automatic backups with `.bak` extension before modifying files
- Dry-run mode to preview changes without modifying files
- Colored console output for clear visibility
- Atomic file writes for safety

**Usage:**

```bash
# Preview changes without modifying files (recommended first)
python3 scripts/sync_backend_ids.py \
  --source weibo/app/initial_data.json \
  --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo \
  --dry-run

# Actually sync IDs (creates backups)
python3 scripts/sync_backend_ids.py \
  --source weibo/app/initial_data.json \
  --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo
```

**Options:**

- `--source` - Path to source JSON file with correct IDs (required)
- `--target-dir` - Path to directory containing target JSON files (required)
- `--dry-run` - Preview changes without modifying files (optional)

**How It Works:**

1. **Content Hashing**: Each item's content (excluding top-level `_id`) is hashed using SHA256
2. **Hash Matching**: Items in target files are matched to source items by content hash
3. **ID Synchronization**: When hashes match, target `_id` is updated to match source `_id`
4. **Backup Creation**: Before modifying, creates `.bak` backup of each target file
5. **Atomic Writes**: Uses temporary files and atomic rename for safe file updates

**Key Differences from generate-collection-ids.ts:**

- `sync_backend_ids.py`: Syncs existing IDs from source to targets based on content matching
- `generate-collection-ids.ts`: Generates brand new IDs for all items

**Examples:**

```bash
# Example 1: Preview what IDs would be synced for weibo
python3 scripts/sync_backend_ids.py \
  --source weibo/app/initial_data.json \
  --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo \
  --dry-run

# Example 2: Actually sync IDs for weibo backend files
python3 scripts/sync_backend_ids.py \
  --source weibo/app/initial_data.json \
  --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo

# Example 3: Sync IDs for JD backend files
python3 scripts/sync_backend_ids.py \
  --source jd/app/initial_data.json \
  --target-dir dojo-bench-customer-colossus/initial-backend-data/jd
```

**Output Example:**

Dry-run mode:

```
[DRY RUN] Processing: accept_search_suggestion_backend.json
  posts: 600 matched, 15 IDs would be updated
  users: 24629 matched, 3 IDs would be updated
  [DRY RUN] Would create backup and update file

[DRY RUN] Summary:
  Files processed: 40
  Total items matched: 1,564,596
  Total IDs that would be synchronized: 127
  No files were modified (dry-run mode)
```

Normal mode:

```
Processing: accept_search_suggestion_backend.json
  posts: 600 matched, 15 IDs updated
  users: 24629 matched, 3 IDs updated
  ✓ Backup created: accept_search_suggestion_backend.json.bak
  ✓ File updated

Summary:
  Files processed: 40
  Total items matched: 1,564,596
  Total IDs synchronized: 127
```

### 6. Local MongoDB Seeding (`seed_local.ts`)

Seeds data to a local MongoDB instance and creates text indexes for search functionality.

**Usage:**

```bash
# Basic usage with text indexes
npx tsx scripts/seed_local.ts <data-file> --indices <indices-file>

# Example: Seed JD app
npx tsx scripts/seed_local.ts jd/app/initial_data.json --indices jd/app/src/indices.json

# Without text indexes
npx tsx scripts/seed_local.ts jd/app/initial_data.json
```

#### Text Index Configuration (`indices.json`)

Each app has an `indices.json` file that defines MongoDB text indexes for search functionality.

**File Locations:**

- `jd/app/src/indices.json`
- `weibo/app/src/indices.json`
- `xiaohongshu/app/src/indices.json`
- `notion/app/src/indices.json`

**Format:**

```json
{
  "indices": [
    {
      "collection": "collectionName",
      "fields": {
        "field1": "text",
        "field2": "text"
      },
      "options": {
        "weights": {
          "field1": 10,
          "field2": 5
        }
      }
    }
  ]
}
```

**Field Reference:**

- `collection` - MongoDB collection name (e.g., `products`, `posts`, `users`). The collection is used as the name of index in meillesearch
- `fields` - Field names mapped to `"text"` (supports nested fields like `"specs.value"`)
- `options.weights` - Search relevance weights (higher numbers = higher priority in search results)

**Example:**

```json
{
  "indices": [
    {
      "collection": "products",
      "fields": {
        "title": "text",
        "category": "text",
        "brand": "text"
      },
      "options": {
        "weights": {
          "title": 10,
          "category": 5,
          "brand": 3
        }
      }
    },
    {
      "collection": "users",
      "fields": {
        "username": "text",
        "displayName": "text",
        "bio": "text"
      },
      "options": {
        "weights": {
          "username": 10,
          "displayName": 10,
          "bio": 5
        }
      }
    }
  ]
}
```

**How Weights Work:**

Weights determine search relevance. In the example above:

- A match in `title` (weight: 10) is considered more important than a match in `brand` (weight: 3)
- Higher weights make documents with matches in those fields rank higher in search results
- Fields with equal weights (e.g., `username` and `displayName` both at 10) have equal importance

## Common Workflows

### Enriching Backend Data with Scraped Data (Recommended Workflow)

This workflow enriches all backend files with scraped data while preserving task-specific customizations.

**Overview:**

1. Generate IDs for both initial_data.json and scrapped_data.json
2. Generate diffs to capture task-specific customizations
3. Merge initial_data.json with scrapped_data.json
4. Apply diffs to create enriched backend files

**Step-by-Step:**

```bash
cd scripts

# Step 1: Ensure both initial_data.json and scrapped_data.json have IDs
pnpm run generate-ids ../weibo/app/initial_data.json
pnpm run generate-ids ../weibo/app/scrapped_data.json

# Step 2: Generate diffs between initial_data.json and all backend files
# This captures task-specific customizations
pnpm run generate-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json

# Step 3: Merge initial_data.json with scrapped_data.json
# This creates enriched initial_data.json with all scraped content
pnpm run merge-data ../weibo/app/initial_data.json ../weibo/app/scrapped_data.json

# Step 4: Apply diffs to create enriched backend files
# This merges scraped enrichments with task customizations
pnpm run apply-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json
```

**Result:**

- All backend files now have scraped data enrichments (new fields, updated content)
- Task-specific customizations are preserved (from diffs)
- Original files backed up in `.backup/` directories
- Diffs stored in `.diff/` directory for reference

**Verification:**

```bash
# Check a backend file to verify enrichment
# It should have both scraped data AND task-specific changes
cat ../dojo-bench-customer-colossus/initial-backend-data/weibo/accept_search_suggestion_backend.json | jq '.users[0]'
```

**For All Projects:**

```bash
for project in weibo jd xiaohongshu; do
  echo "Processing $project..."

  # Step 1: Generate IDs
  pnpm run generate-ids ../$project/app/initial_data.json
  pnpm run generate-ids ../$project/app/scrapped_data.json

  # Step 2: Generate diffs
  pnpm run generate-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/$project ../$project/app/initial_data.json

  # Step 3: Merge data
  pnpm run merge-data ../$project/app/initial_data.json ../$project/app/scrapped_data.json

  # Step 4: Apply diffs
  pnpm run apply-diff --target-dir ../dojo-bench-customer-colossus/initial-backend-data/$project ../$project/app/initial_data.json

  echo "✅ $project enrichment complete"
done
```

### Merging Initial Data to All Bench Files

1. **Preview what would be merged (recommended):**

   ```bash
   pnpm run merge-data --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json --dry-run
   ```

2. **Perform the merge:**

   ```bash
   pnpm run merge-data --target-dir ../dojo-bench-customer-colossus/initial-backend-data/weibo ../weibo/app/initial_data.json
   ```

3. **If needed, restore from backups:**

   ```bash
   cd ../dojo-bench-customer-colossus/initial-backend-data/weibo
   cp .backup/* .
   ```

### Processing New Scraped Data for a Project

1. **First, check what would be generated (dry-run):**

   ```bash
   pnpm run generate-ids weibo/app/scrapped_data.json --dry-run
   ```

2. **Generate IDs for scraped data:**

   ```bash
   pnpm run generate-ids weibo/app/scrapped_data.json
   ```

3. **Merge scraped data to initial_data.json:**

   ```bash
   pnpm run merge-scraped-data weibo
   ```

4. **Merge to bench files:**

   ```bash
   pnpm run merge-scraped-data weibo --merge-to-bench
   ```

### Processing All Bench Files for a Project

1. **Preview what would be generated for all bench files:**

   ```bash
   pnpm run generate-ids --dir ../dojo-bench-customer-colossus/initial-backend-data/weibo --dry-run
   ```

2. **Generate IDs for all bench files:**

   ```bash
   pnpm run generate-ids --dir ../dojo-bench-customer-colossus/initial-backend-data/weibo
   ```

3. **Process all projects at once:**

   ```bash
   for project in weibo jd xiaohongshu; do
     echo "Processing $project bench files..."
     pnpm run generate-ids --dir ../dojo-bench-customer-colossus/initial-backend-data/$project
   done
   ```

### Setting Up New Backend Data File

1. **Create your JSON file with collections (arrays):**

   ```json
   {
     "users": [
       { "name": "Alice", "email": "alice@example.com" },
       { "name": "Bob", "email": "bob@example.com" }
     ],
     "posts": [{ "title": "Hello", "content": "World" }]
   }
   ```

2. **Generate IDs:**

   ```bash
   pnpm run generate-ids path/to/your/file.json
   ```

3. **Result:**
   ```json
   {
     "users": [
       {
         "_id": "users_a1b2c3d4e5f6",
         "name": "Alice",
         "email": "alice@example.com"
       },
       {
         "_id": "users_9z8y7x6w5v4u",
         "name": "Bob",
         "email": "bob@example.com"
       }
     ],
     "posts": [
       { "_id": "posts_1a2b3c4d5e6f", "title": "Hello", "content": "World" }
     ]
   }
   ```

## File Structure

```
scripts/
├── README.md                      # This file
├── package.json                   # NPM scripts configuration
├── generate-collection-ids.ts     # ID generation script
├── merge-data.ts                  # Data merging script (content-hash based)
├── generate-diff.ts               # Diff generation script (property-level deltas)
├── apply-diff.ts                  # Diff application script (smart property merging)
├── sync_backend_ids.py            # ID synchronization script (source -> targets)
├── dedupe.py                      # Backend file deduplication script
├── update_tasks_to_dedupe.py      # Task reference updater for dedupe
├── cleanup_duplicates.py          # Duplicate cleanup script
├── merge-scraped-data.ts          # Legacy data merging script
├── seed.ts                        # Remote MongoDB seeding
└── seed_local.ts                  # Local MongoDB seeding
```

## Notes

- `generate-collection-ids.ts`, `merge-data.ts`, and `apply-diff.ts` create backups in a `.backup/` directory
- Generated IDs are deterministic - same content = same ID
- Merge operations use content hashing to detect duplicates (ignores `_id` differences)
- `generate-diff.ts` uses hybrid matching (ID + content-hash) to handle auto-generated IDs
- `apply-diff.ts` preserves both scraped enrichments AND task-specific customizations
- Diff files are stored in `.diff/` directories next to backend files
- The scripts can be run from any directory using relative or absolute paths
- Always use `--dry-run` first to preview changes safely
- Backup and diff directories can be easily managed:
  - Delete all backups: `rm -rf .backup/`
  - Restore backups: `cp .backup/* .`
  - Delete all diffs: `rm -rf .diff/`

## Weibo task scanner

Runs a simple scan over weibo data to see if we fullfil task requirements from [requiements](https://www.notion.so/Required-data-for-tasks-2ce6ce78208480d586e6ffa19fc751ba?source=copy_link)

If the task requirements change the script has to be modified.

`uv run weibo_task_scannner.py ../weibo/app/initial_data.json`
