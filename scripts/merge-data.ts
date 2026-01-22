#!/usr/bin/env tsx

import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";
import { fileURLToPath } from "url";

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface MergeStats {
  collection: string;
  itemsAdded: number;
  itemsSkipped: number;
  conflicts: number;
  conflictIds: string[];
}

interface MergeOptions {
  targetFile?: string;
  targetDir?: string;
  originFile: string;
  dryRun: boolean;
  verbose: boolean;
  overwriteOnConflict: boolean;
}

function parseArgs(): MergeOptions {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes("--help") || args.includes("-h")) {
    console.log(`
Usage: pnpm tsx scripts/merge-data.ts <target-file> <origin-file> [options]
       pnpm tsx scripts/merge-data.ts --target-dir <dir-path> <origin-file> [options]

Description:
  Merges collections from an origin backend JSON file into target file(s).
  Uses content hashing to detect duplicates, ignoring _id differences.
  Creates backups in a .backup/ directory.

Arguments:
  target-file       Path to target JSON file (single file mode)
  origin-file       Path to origin JSON file to merge from
  --target-dir      Process all JSON files in the specified directory (batch mode)

Options:
  --dry-run              Preview changes without modifying files
  --verbose, -v          Show detailed output including item-by-item changes
  --overwrite-conflicts  On ID conflicts, overwrite target with origin (default: keep target)
  --help, -h             Show this help message

Examples:
  # Merge one file into another (single file mode)
  pnpm tsx scripts/merge-data.ts target.json origin.json

  # Merge into all files in a directory (batch mode)
  pnpm tsx scripts/merge-data.ts --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo weibo/app/initial_data.json

  # Dry run for batch mode
  pnpm tsx scripts/merge-data.ts --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo weibo/app/initial_data.json --dry-run

  # Verbose output
  pnpm tsx scripts/merge-data.ts target.json origin.json -v

  # Overwrite conflicts with origin data
  pnpm tsx scripts/merge-data.ts target.json origin.json --overwrite-conflicts
    `);
    process.exit(args.includes("--help") || args.includes("-h") ? 0 : 1);
  }

  const dryRun = args.includes("--dry-run");
  const verbose = args.includes("--verbose") || args.includes("-v");
  const overwriteOnConflict = args.includes("--overwrite-conflicts");

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
  let originFile: string;

  if (targetDir) {
    // Batch mode: only need origin file
    if (fileArgs.length < 1) {
      console.error("❌ Error: Must provide origin file path");
      console.error("   Run with --help for usage information");
      process.exit(1);
    }
    originFile = fileArgs[0];
  } else {
    // Single file mode: need both target and origin
    if (fileArgs.length < 2) {
      console.error("❌ Error: Must provide both target and origin file paths");
      console.error("   Run with --help for usage information");
      process.exit(1);
    }
    targetFile = fileArgs[0];
    originFile = fileArgs[1];
  }

  return { targetFile, targetDir, originFile, dryRun, verbose, overwriteOnConflict };
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

function createBackup(sourcePath: string): string {
  const sourceDir = path.dirname(sourcePath);
  const fileName = path.basename(sourcePath);
  const backupDir = path.join(sourceDir, ".backup");
  const backupPath = path.join(backupDir, fileName);

  try {
    // Create .backup directory if it doesn't exist
    if (!fs.existsSync(backupDir)) {
      fs.mkdirSync(backupDir, { recursive: true });
    }

    fs.copyFileSync(sourcePath, backupPath);
    return backupPath;
  } catch (error) {
    console.error(`❌ Error creating backup:`);
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
 * Merge collections from origin into target, detecting duplicates via content hash.
 */
function mergeCollections(
  targetData: any,
  originData: any,
  verbose: boolean,
  overwriteOnConflict: boolean
): {
  mergedData: any;
  allStats: MergeStats[];
} {
  const mergedData = { ...targetData };
  const allStats: MergeStats[] = [];

  // Get all top-level array collections from origin
  const originCollections = Object.keys(originData).filter((key) =>
    Array.isArray(originData[key])
  );

  for (const collectionName of originCollections) {
    const stats: MergeStats = {
      collection: collectionName,
      itemsAdded: 0,
      itemsSkipped: 0,
      conflicts: 0,
      conflictIds: [],
    };

    // Initialize target collection if it doesn't exist
    if (!mergedData[collectionName]) {
      mergedData[collectionName] = [];
    }

    const targetCollection = mergedData[collectionName];
    const originCollection = originData[collectionName];

    // Build maps for target collection
    const targetContentHashes = new Set<string>();
    const targetIdToHash = new Map<string, string>();

    for (const item of targetCollection) {
      if (!item || typeof item !== "object") continue;

      const contentHash = hashItemContent(item);
      targetContentHashes.add(contentHash);

      if (item._id) {
        targetIdToHash.set(item._id, contentHash);
      }
    }

    // Process origin items
    for (const originItem of originCollection) {
      if (!originItem || typeof originItem !== "object") continue;

      const contentHash = hashItemContent(originItem);

      // Check if this content already exists in target
      if (targetContentHashes.has(contentHash)) {
        stats.itemsSkipped++;
        if (verbose) {
          const id = originItem._id || "unknown";
          console.log(
            `   [${collectionName}] Skipping duplicate content: ${id}`
          );
        }
        continue;
      }

      // Check for ID conflict (same ID, different content)
      if (originItem._id && targetIdToHash.has(originItem._id)) {
        const existingHash = targetIdToHash.get(originItem._id);
        if (existingHash && existingHash !== contentHash) {
          stats.conflicts++;
          stats.conflictIds.push(originItem._id);

          if (overwriteOnConflict) {
            // Find and replace the existing item with the origin item
            const existingIndex = targetCollection.findIndex(
              (item: any) => item._id === originItem._id
            );
            if (existingIndex !== -1) {
              targetCollection[existingIndex] = originItem;
              targetContentHashes.delete(existingHash);
              targetContentHashes.add(contentHash);
              targetIdToHash.set(originItem._id, contentHash);
              stats.itemsAdded++;
              if (verbose) {
                console.log(
                  `   ⚠️  [${collectionName}] ID conflict: ${originItem._id} (overwriting target with origin)`
                );
              }
            }
          } else {
            // Keep target version
            if (verbose) {
              console.log(
                `   ⚠️  [${collectionName}] ID conflict: ${originItem._id} (different content, keeping target version)`
              );
            }
            stats.itemsSkipped++;
          }
          continue;
        }
      }

      // Add the item to target
      targetCollection.push(originItem);
      targetContentHashes.add(contentHash);
      if (originItem._id) {
        targetIdToHash.set(originItem._id, contentHash);
      }
      stats.itemsAdded++;

      if (verbose) {
        const id = originItem._id || "unknown";
        console.log(`   [${collectionName}] Added: ${id}`);
      }
    }

    mergedData[collectionName] = targetCollection;
    allStats.push(stats);
  }

  return { mergedData, allStats };
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

function printStats(
  stats: MergeStats[],
  showConflicts: boolean = true,
  overwriteOnConflict: boolean = false
): {
  totalAdded: number;
  totalConflicts: number;
} {
  let totalAdded = 0;
  let totalConflicts = 0;

  for (const stat of stats) {
    if (stat.itemsAdded === 0 && stat.conflicts === 0) {
      continue; // Skip collections with no changes
    }

    if (stat.itemsAdded > 0) {
      console.log(
        `📦 ${stat.collection}: ${stat.itemsAdded} item(s) added${
          stat.itemsSkipped > 0 ? `, ${stat.itemsSkipped} already exist` : ""
        }`
      );
    }

    if (showConflicts && stat.conflicts > 0) {
      const conflictAction = overwriteOnConflict
        ? "overwritten with origin"
        : "kept target version";
      for (const conflictId of stat.conflictIds) {
        console.log(
          `⚠️  ID conflict: ${conflictId} (different content, ${conflictAction})`
        );
      }
    }

    totalAdded += stat.itemsAdded;
    totalConflicts += stat.conflicts;
  }

  return { totalAdded, totalConflicts };
}

function mergeSingleFile(
  targetPath: string,
  originPath: string,
  originData: any,
  options: MergeOptions,
  showHeader: boolean = true
): {
  itemsAdded: number;
  conflicts: number;
} {
  if (showHeader) {
    console.log(`\n🚀 Merging data from origin into target`);
    if (options.dryRun) {
      console.log("🔍 DRY RUN MODE - No files will be modified\n");
    }
  }

  // Load target file
  if (options.verbose || showHeader) {
    console.log(`📖 Loading target file: ${path.basename(targetPath)}`);
  }
  const targetData = loadJsonFile(targetPath);

  if (options.verbose || showHeader) {
    console.log(`📖 Loading origin file: ${path.basename(originPath)}`);
    console.log("🔄 Processing merge...\n");
  }

  // Perform merge
  const { mergedData, allStats } = mergeCollections(
    targetData,
    originData,
    options.verbose,
    options.overwriteOnConflict
  );

  // Print statistics
  const { totalAdded, totalConflicts } = printStats(allStats, true, options.overwriteOnConflict);

  if (totalAdded === 0 && totalConflicts === 0) {
    if (showHeader) {
      console.log("✨ No new items to add - target already has all data!\n");
    }
    return { itemsAdded: 0, conflicts: 0 };
  }

  if (showHeader) {
    console.log(
      `\n📈 TOTAL: ${totalAdded} item(s) added from origin to target`
    );
    if (totalConflicts > 0) {
      const conflictAction = options.overwriteOnConflict
        ? "overwritten with origin data"
        : "kept target version";
      console.log(
        `⚠️  ${totalConflicts} conflict(s) detected (${conflictAction})`
      );
    }
  }

  // Save results
  if (!options.dryRun) {
    const backupPath = createBackup(targetPath);
    if (showHeader) {
      console.log(
        `✅ Backup created: ${path.relative(process.cwd(), backupPath)}`
      );
    }

    if (options.verbose || showHeader) {
      console.log("💾 Writing updated data to target file...");
    }
    writeJsonFile(targetPath, mergedData);

    if (showHeader) {
      console.log("✅ Merge completed successfully!\n");
    }
  } else if (showHeader) {
    console.log("🔍 Dry run completed - no files were modified\n");
  }

  return { itemsAdded: totalAdded, conflicts: totalConflicts };
}

function mergeToDirectory(
  targetDirPath: string,
  originPath: string,
  options: MergeOptions
): void {
  console.log(`\n🚀 Merging origin into multiple targets in directory`);
  if (options.dryRun) {
    console.log("🔍 DRY RUN MODE - No files will be modified");
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

  // Load origin file once
  console.log(`📖 Loading origin file: ${path.basename(originPath)}`);
  const originData = loadJsonFile(originPath);

  // Find all JSON files in the directory
  const files = fs
    .readdirSync(targetDirPath)
    .filter((file) => file.endsWith(".json"))
    .filter((file) => !file.endsWith(".backup.json"))
    .sort();

  if (files.length === 0) {
    console.warn(`⚠️  Warning: No JSON files found in ${targetDirPath}`);
    return;
  }

  console.log(`📁 Found ${files.length} target file(s) to process\n`);

  // Process each file
  let filesProcessed = 0;
  let totalItemsAdded = 0;
  let totalConflicts = 0;

  for (const file of files) {
    const targetPath = path.join(targetDirPath, file);
    console.log(`${"─".repeat(80)}`);
    console.log(`📄 Processing: ${file}`);

    try {
      const result = mergeSingleFile(
        targetPath,
        originPath,
        originData,
        options,
        false
      );
      filesProcessed++;
      totalItemsAdded += result.itemsAdded;
      totalConflicts += result.conflicts;
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
  console.log(`Total items added:      ${totalItemsAdded}`);
  if (totalConflicts > 0) {
    console.log(`Conflicts detected:     ${totalConflicts}`);
  }

  if (!options.dryRun && totalItemsAdded > 0) {
    const backupDir = path.join(targetDirPath, ".backup");
    console.log(
      `✅ All backups created in: ${path.relative(process.cwd(), backupDir)}/`
    );
    console.log("💾 All files updated successfully\n");
  } else if (options.dryRun) {
    console.log("🔍 Dry run completed - no files were modified\n");
  } else {
    console.log("✨ No changes needed - all files already have the data!\n");
  }
}

function main() {
  const options = parseArgs();

  if (options.targetDir) {
    // Batch mode - process all JSON files in directory
    const resolvedDirPath = resolvePath(options.targetDir);
    const resolvedOriginPath = resolvePath(options.originFile);
    validateFilePath(resolvedOriginPath);
    mergeToDirectory(resolvedDirPath, resolvedOriginPath, options);
  } else if (options.targetFile) {
    // Single file mode
    const resolvedTargetPath = resolvePath(options.targetFile);
    const resolvedOriginPath = resolvePath(options.originFile);
    validateFilePath(resolvedTargetPath);
    validateFilePath(resolvedOriginPath);

    // Load origin data once
    const originData = loadJsonFile(resolvedOriginPath);

    mergeSingleFile(
      resolvedTargetPath,
      resolvedOriginPath,
      originData,
      options,
      true
    );
  }
}

// Run the script
main();
