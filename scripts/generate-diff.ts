#!/usr/bin/env tsx

import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";
import { fileURLToPath } from "url";

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface DiffStats {
  collection: string;
  itemsAdded: number;
  itemsModified: number;
  itemsUnchanged: number;
  totalBackendItems: number;
}

interface GenerateOptions {
  targetFile?: string;
  targetDir?: string;
  sourceFile: string;
  dryRun: boolean;
  verbose: boolean;
}

interface CollectionDiff {
  added?: any[];
  modified?: Array<{
    _id: string;
    changes: Record<string, any>;
  }>;
}

interface DiffResult {
  [collection: string]: CollectionDiff;
}

function parseArgs(): GenerateOptions {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes("--help") || args.includes("-h")) {
    console.log(`
Usage: pnpm tsx scripts/generate-diff.ts <target-file|--target-dir dir-path> <source-file> [options]

Description:
  Generates property-level diffs between backend files and a source file.
  Handles auto-generated IDs via hybrid matching (ID + content-hash).
  Stores diffs in .diff/ directory next to backend files.

Arguments:
  target-file       Path to a single backend JSON file
  --target-dir      Process all JSON files in the specified directory
  source-file       Path to source JSON file (e.g., initial_data.json)

Options:
  --dry-run         Preview changes without creating diff files
  --verbose, -v     Show detailed output including item-by-item changes
  --help, -h        Show this help message

Examples:
  # Generate diff for single file
  pnpm tsx scripts/generate-diff.ts \\
    dojo-bench-customer-colossus/initial-backend-data/weibo/accept_search_suggestion_backend.json \\
    weibo/app/initial_data.json

  # Generate diffs for all files in directory
  pnpm tsx scripts/generate-diff.ts \\
    --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo \\
    weibo/app/initial_data.json

  # Dry run with verbose output
  pnpm tsx scripts/generate-diff.ts \\
    --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo \\
    weibo/app/initial_data.json --dry-run -v
    `);
    process.exit(args.includes("--help") || args.includes("-h") ? 0 : 1);
  }

  const dryRun = args.includes("--dry-run");
  const verbose = args.includes("--verbose") || args.includes("-v");

  // Check for --target-dir flag
  let targetDir: string | undefined;
  const targetDirIndex = args.findIndex((arg) => arg === "--target-dir");
  if (targetDirIndex !== -1 && args[targetDirIndex + 1]) {
    targetDir = args[targetDirIndex + 1];
  }

  // Get file paths (non-flag arguments, excluding the value after --target-dir)
  const fileArgs = args.filter((arg, index) => {
    // Skip flags
    if (arg.startsWith("--") || arg.startsWith("-")) return false;
    // Skip the argument after --target-dir
    if (targetDirIndex !== -1 && index === targetDirIndex + 1) return false;
    return true;
  });

  let targetFile: string | undefined;
  let sourceFile: string;

  if (targetDir) {
    // Directory mode: only need source file
    if (fileArgs.length < 1) {
      console.error("❌ Error: Must provide source file path");
      console.error("   Run with --help for usage information");
      process.exit(1);
    }
    sourceFile = fileArgs[0];
  } else {
    // Single file mode: need both target and source
    if (fileArgs.length < 2) {
      console.error("❌ Error: Must provide both target and source file paths");
      console.error("   Run with --help for usage information");
      process.exit(1);
    }
    targetFile = fileArgs[0];
    sourceFile = fileArgs[1];
  }

  return { targetFile, targetDir, sourceFile, dryRun, verbose };
}

function resolvePath(inputPath: string): string {
  // If absolute path, return as is
  if (path.isAbsolute(inputPath)) {
    return inputPath;
  }

  // Try relative to current working directory
  const cwdPath = path.resolve(process.cwd(), inputPath);
  if (fs.existsSync(cwdPath)) {
    return cwdPath;
  }

  // Try relative to script directory's parent (project root)
  const rootPath = path.resolve(__dirname, "..", inputPath);
  if (fs.existsSync(rootPath)) {
    return rootPath;
  }

  // Return original path and let validation handle the error
  return cwdPath;
}

function validateFilePath(filePath: string): void {
  if (!fs.existsSync(filePath)) {
    console.error(`❌ Error: File not found: ${filePath}`);
    process.exit(1);
  }

  if (!filePath.endsWith(".json")) {
    console.error(`❌ Error: File must be a JSON file: ${filePath}`);
    process.exit(1);
  }
}

function loadJsonFile(filePath: string): any {
  try {
    const content = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(content);
  } catch (error) {
    console.error(`❌ Error parsing JSON from ${filePath}:`);
    console.error(
      `   ${error instanceof Error ? error.message : String(error)}`
    );
    process.exit(1);
  }
}

/**
 * Generate a deterministic hash for an item based on its content (excluding _id).
 */
function hashItemContent(item: any): string {
  const { _id, ...itemWithoutId } = item;
  const stableItem = JSON.stringify(
    itemWithoutId,
    Object.keys(itemWithoutId).sort()
  );
  return crypto.createHash("sha256").update(stableItem).digest("hex");
}

/**
 * Deep equality check for property comparison
 */
function deepEqual(a: any, b: any): boolean {
  if (a === b) return true;
  if (a == null || b == null) return false;
  if (typeof a !== typeof b) return false;

  if (typeof a === "object") {
    if (Array.isArray(a) !== Array.isArray(b)) return false;

    if (Array.isArray(a)) {
      if (a.length !== b.length) return false;
      for (let i = 0; i < a.length; i++) {
        if (!deepEqual(a[i], b[i])) return false;
      }
      return true;
    }

    const keysA = Object.keys(a).sort();
    const keysB = Object.keys(b).sort();
    if (keysA.length !== keysB.length) return false;
    if (!deepEqual(keysA, keysB)) return false;

    for (const key of keysA) {
      if (!deepEqual(a[key], b[key])) return false;
    }
    return true;
  }

  return false;
}

/**
 * Find matching source item using hybrid strategy (ID first, then content-hash)
 */
function findMatchingSourceItem(
  backendItem: any,
  sourceById: Map<string, any>,
  sourceByContentHash: Map<string, any>
): { item: any | null; matchedById: boolean } {
  // Strategy 1: Match by _id (for stable IDs like users, posts)
  if (backendItem._id && sourceById.has(backendItem._id)) {
    return { item: sourceById.get(backendItem._id), matchedById: true };
  }

  // Strategy 2: Match by content hash (for auto-generated IDs)
  const contentHash = hashItemContent(backendItem);
  if (sourceByContentHash.has(contentHash)) {
    return { item: sourceByContentHash.get(contentHash), matchedById: false };
  }

  return { item: null, matchedById: false }; // No match = added item
}

/**
 * Get property-level diff between source and backend items
 */
function getPropertyDiff(
  sourceItem: any,
  backendItem: any
): Record<string, any> | null {
  const changes: Record<string, any> = {};

  // Compare all properties in backend item
  for (const key of Object.keys(backendItem)) {
    if (key === "_id") continue; // Skip _id

    // Deep comparison
    if (!deepEqual(sourceItem[key], backendItem[key])) {
      changes[key] = backendItem[key];
    }
  }

  return Object.keys(changes).length > 0 ? changes : null;
}

/**
 * Generate diff for a single collection
 */
function generateCollectionDiff(
  sourceCollection: any[],
  backendCollection: any[],
  collectionName: string,
  verbose: boolean
): {
  diff: CollectionDiff;
  stats: DiffStats;
} {
  const stats: DiffStats = {
    collection: collectionName,
    itemsAdded: 0,
    itemsModified: 0,
    itemsUnchanged: 0,
    totalBackendItems: backendCollection.length,
  };

  const diff: CollectionDiff = {};

  // Build maps for source collection
  const sourceById = new Map<string, any>();
  const sourceByContentHash = new Map<string, any>();

  for (const item of sourceCollection) {
    if (!item || typeof item !== "object") continue;

    if (item._id) {
      sourceById.set(item._id, item);
    }

    const contentHash = hashItemContent(item);
    sourceByContentHash.set(contentHash, item);
  }

  // Process backend items
  for (const backendItem of backendCollection) {
    if (!backendItem || typeof backendItem !== "object") continue;

    const { item: sourceItem, matchedById } = findMatchingSourceItem(
      backendItem,
      sourceById,
      sourceByContentHash
    );

    if (sourceItem) {
      // Item exists in source - check for modifications
      const propertyDiff = getPropertyDiff(sourceItem, backendItem);

      if (propertyDiff) {
        // Item has been modified
        stats.itemsModified++;

        if (!diff.modified) {
          diff.modified = [];
        }

        // Use source's _id (critical for content-hash matches)
        diff.modified.push({
          _id: sourceItem._id,
          changes: propertyDiff,
        });

        if (verbose) {
          const matchType = matchedById ? "by ID" : "by content-hash";
          console.log(
            `   [${collectionName}] Modified (${matchType}): ${sourceItem._id}`
          );
          console.log(
            `      Changed properties: ${Object.keys(propertyDiff).join(", ")}`
          );
        }
      } else {
        // Item unchanged
        stats.itemsUnchanged++;
        if (verbose) {
          console.log(
            `   [${collectionName}] Unchanged: ${
              sourceItem._id || backendItem._id
            }`
          );
        }
      }
    } else {
      // Item doesn't exist in source - it's new
      stats.itemsAdded++;

      if (!diff.added) {
        diff.added = [];
      }

      diff.added.push(backendItem);

      if (verbose) {
        console.log(
          `   [${collectionName}] Added: ${backendItem._id || "no-id"}`
        );
      }
    }
  }

  return { diff, stats };
}

/**
 * Generate full diff between source and backend data
 */
function generateDiff(
  sourceData: any,
  backendData: any,
  verbose: boolean
): {
  diffResult: DiffResult;
  allStats: DiffStats[];
} {
  const diffResult: DiffResult = {};
  const allStats: DiffStats[] = [];

  // Get all top-level array collections from backend
  const backendCollections = Object.keys(backendData).filter((key) =>
    Array.isArray(backendData[key])
  );

  for (const collectionName of backendCollections) {
    const sourceCollection = Array.isArray(sourceData[collectionName])
      ? sourceData[collectionName]
      : [];
    const backendCollection = backendData[collectionName];

    if (verbose) {
      console.log(`\n🔄 Processing collection: ${collectionName}`);
    }

    const { diff, stats } = generateCollectionDiff(
      sourceCollection,
      backendCollection,
      collectionName,
      verbose
    );

    // Only include collections with changes
    if (
      (diff.added && diff.added.length > 0) ||
      (diff.modified && diff.modified.length > 0)
    ) {
      diffResult[collectionName] = diff;
    }

    allStats.push(stats);
  }

  return { diffResult, allStats };
}

function writeJsonFile(filePath: string, data: any): void {
  try {
    const jsonString = JSON.stringify(data, null, 2);
    fs.writeFileSync(filePath, jsonString, "utf-8");
  } catch (error) {
    console.error(`❌ Error writing JSON to ${filePath}:`);
    console.error(
      `   ${error instanceof Error ? error.message : String(error)}`
    );
    process.exit(1);
  }
}

function printStats(stats: DiffStats[], targetFileName?: string): void {
  const header = targetFileName
    ? `DIFF SUMMARY - ${targetFileName}`
    : "DIFF SUMMARY";
  console.log("\n" + "=".repeat(80));
  console.log(header);
  console.log("=".repeat(80));

  let totalAdded = 0;
  let totalModified = 0;
  let totalUnchanged = 0;

  for (const stat of stats) {
    if (stat.itemsAdded === 0 && stat.itemsModified === 0) {
      continue; // Skip collections with no changes
    }

    console.log(`\n📦 ${stat.collection}:`);
    console.log(`   Total items:        ${stat.totalBackendItems}`);
    console.log(`   Unchanged:          ${stat.itemsUnchanged}`);
    if (stat.itemsModified > 0) {
      console.log(`   ✏️  Modified:        ${stat.itemsModified}`);
    }
    if (stat.itemsAdded > 0) {
      console.log(`   ✨ Added:           ${stat.itemsAdded}`);
    }

    totalAdded += stat.itemsAdded;
    totalModified += stat.itemsModified;
    totalUnchanged += stat.itemsUnchanged;
  }

  console.log("\n" + "-".repeat(80));
  if (totalAdded > 0 || totalModified > 0) {
    console.log(
      `📈 TOTAL: ${totalModified} modified, ${totalAdded} added out of ${
        totalAdded + totalModified + totalUnchanged
      } item(s)`
    );
  } else {
    console.log(`📈 TOTAL: No changes detected`);
  }
  console.log("=".repeat(80) + "\n");
}

function generateDiffForFile(
  targetPath: string,
  sourcePath: string,
  sourceData: any,
  options: GenerateOptions,
  showHeader: boolean = true
): {
  hasChanges: boolean;
  totalChanges: number;
} {
  if (showHeader) {
    console.log(
      `\n🚀 Generating diff for: ${path.basename(
        targetPath
      )} vs ${path.basename(sourcePath)}`
    );
    if (options.dryRun) {
      console.log("🔍 DRY RUN MODE - No files will be created\n");
    }
  }

  // Load backend file
  if (options.verbose || showHeader) {
    console.log(`📖 Loading backend file: ${path.basename(targetPath)}`);
  }
  const backendData = loadJsonFile(targetPath);

  // Generate diff
  if (options.verbose || showHeader) {
    console.log("🔍 Analyzing differences...");
  }

  const { diffResult, allStats } = generateDiff(
    sourceData,
    backendData,
    options.verbose
  );

  // Print statistics
  printStats(allStats, showHeader ? undefined : path.basename(targetPath));

  // Check if any changes exist
  const totalChanges =
    allStats.reduce((sum, stat) => sum + stat.itemsAdded, 0) +
    allStats.reduce((sum, stat) => sum + stat.itemsModified, 0);

  if (totalChanges === 0) {
    if (showHeader) {
      console.log("✨ No changes detected - backend matches source!\n");
    }
    return { hasChanges: false, totalChanges: 0 };
  }

  // Save diff file
  if (!options.dryRun) {
    const targetDir = path.dirname(targetPath);
    const targetFileName = path.basename(targetPath, ".json");
    const diffDir = path.join(targetDir, ".diff");
    const diffPath = path.join(diffDir, `${targetFileName}.diff.json`);

    // Create .diff directory if it doesn't exist
    if (!fs.existsSync(diffDir)) {
      fs.mkdirSync(diffDir, { recursive: true });
    }

    writeJsonFile(diffPath, diffResult);

    if (showHeader) {
      console.log(`💾 Diff saved: ${path.relative(process.cwd(), diffPath)}\n`);
    }
  } else if (showHeader) {
    console.log("🔍 Dry run completed - no files were created\n");
  }

  return { hasChanges: true, totalChanges };
}

function generateDiffForDirectory(
  targetDirPath: string,
  sourcePath: string,
  options: GenerateOptions
): void {
  console.log(`\n🚀 Generating diffs for directory: ${targetDirPath}`);
  if (options.dryRun) {
    console.log("🔍 DRY RUN MODE - No files will be created");
  }
  console.log();

  // Validate directory
  if (!fs.existsSync(targetDirPath)) {
    console.error(`❌ Error: Directory not found: ${targetDirPath}`);
    process.exit(1);
  }

  if (!fs.statSync(targetDirPath).isDirectory()) {
    console.error(`❌ Error: Path is not a directory: ${targetDirPath}`);
    process.exit(1);
  }

  // Load source file once
  console.log(`📖 Loading source file: ${path.basename(sourcePath)}`);
  const sourceData = loadJsonFile(sourcePath);

  // Find all JSON files in the directory
  const files = fs
    .readdirSync(targetDirPath)
    .filter((file) => file.endsWith(".json"))
    .filter((file) => !file.endsWith(".diff.json"))
    .sort();

  if (files.length === 0) {
    console.warn(`⚠️  Warning: No JSON files found in ${targetDirPath}`);
    return;
  }

  console.log(`📁 Found ${files.length} backend file(s) to process\n`);

  // Process each file
  let filesProcessed = 0;
  let filesWithChanges = 0;
  let totalChanges = 0;

  for (const file of files) {
    const targetPath = path.join(targetDirPath, file);
    console.log(`${"─".repeat(80)}`);
    console.log(`📄 Processing: ${file}`);

    try {
      const result = generateDiffForFile(
        targetPath,
        sourcePath,
        sourceData,
        options,
        false
      );
      filesProcessed++;
      totalChanges += result.totalChanges;
      if (result.hasChanges) {
        filesWithChanges++;
      }
    } catch (error) {
      console.error(`❌ Error processing ${file}:`);
      console.error(
        `   ${error instanceof Error ? error.message : String(error)}`
      );
    }

    console.log(); // Empty line between files
  }

  // Print overall summary
  console.log("=".repeat(80));
  console.log("📊 BATCH SUMMARY");
  console.log("=".repeat(80));
  console.log(`Files processed:        ${filesProcessed}`);
  console.log(`Files with changes:     ${filesWithChanges}`);
  console.log(`Total changes:          ${totalChanges}`);

  if (!options.dryRun && filesWithChanges > 0) {
    const diffDir = path.join(targetDirPath, ".diff");
    console.log(
      `💾 All diffs saved in: ${path.relative(process.cwd(), diffDir)}/`
    );
    console.log("✅ Diff generation completed successfully!\n");
  } else if (options.dryRun) {
    console.log("🔍 Dry run completed - no files were created\n");
  } else {
    console.log("✨ No changes detected - all backends match source!\n");
  }
}

function main() {
  const options = parseArgs();

  // Resolve and validate source file
  const resolvedSourcePath = resolvePath(options.sourceFile);
  validateFilePath(resolvedSourcePath);

  if (options.targetDir) {
    // Directory mode - process all JSON files in directory
    const resolvedDirPath = resolvePath(options.targetDir);
    generateDiffForDirectory(resolvedDirPath, resolvedSourcePath, options);
  } else if (options.targetFile) {
    // Single file mode
    const resolvedTargetPath = resolvePath(options.targetFile);
    validateFilePath(resolvedTargetPath);

    // Load source data once
    const sourceData = loadJsonFile(resolvedSourcePath);

    generateDiffForFile(
      resolvedTargetPath,
      resolvedSourcePath,
      sourceData,
      options,
      true
    );
  }
}

// Run the script
main();
