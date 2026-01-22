#!/usr/bin/env tsx

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface ApplyStats {
  collection: string;
  itemsModified: number;
  itemsAdded: number;
  totalResultItems: number;
}

interface ApplyOptions {
  targetFile?: string;
  targetDir?: string;
  mergedSourceFile: string;
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

function parseArgs(): ApplyOptions {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes("--help") || args.includes("-h")) {
    console.log(`
Usage: pnpm tsx scripts/apply-diff.ts <target-file|--target-dir dir-path> <merged-source-file> [options]

Description:
  Applies property-level diffs to merged source data, creating enriched backend files.
  Reads diff files from .diff/ directory next to backend files.
  Preserves both task-specific customizations and scraped data enrichments.

Arguments:
  target-file           Path to a single backend JSON file
  --target-dir          Process all JSON files in the specified directory
  merged-source-file    Path to merged source file (initial_data + scrapped_data)

Options:
  --dry-run             Preview changes without modifying files
  --verbose, -v         Show detailed output including item-by-item changes
  --help, -h            Show this help message

Examples:
  # Apply diff for single file
  pnpm tsx scripts/apply-diff.ts \\
    dojo-bench-customer-colossus/initial-backend-data/weibo/accept_search_suggestion_backend.json \\
    weibo/app/merged_data.json

  # Apply diffs for all files in directory
  pnpm tsx scripts/apply-diff.ts \\
    --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo \\
    weibo/app/merged_data.json

  # Dry run with verbose output
  pnpm tsx scripts/apply-diff.ts \\
    --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo \\
    weibo/app/merged_data.json --dry-run -v
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
  let mergedSourceFile: string;

  if (targetDir) {
    // Directory mode: only need merged source file
    if (fileArgs.length < 1) {
      console.error("❌ Error: Must provide merged source file path");
      console.error("   Run with --help for usage information");
      process.exit(1);
    }
    mergedSourceFile = fileArgs[0];
  } else {
    // Single file mode: need both target and merged source
    if (fileArgs.length < 2) {
      console.error(
        "❌ Error: Must provide both target and merged source file paths"
      );
      console.error("   Run with --help for usage information");
      process.exit(1);
    }
    targetFile = fileArgs[0];
    mergedSourceFile = fileArgs[1];
  }

  return { targetFile, targetDir, mergedSourceFile, dryRun, verbose };
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
 * Apply diff to a single collection
 */
function applyDiffToCollection(
  mergedCollection: any[],
  diff: CollectionDiff,
  collectionName: string,
  verbose: boolean
): {
  result: any[];
  stats: ApplyStats;
} {
  const stats: ApplyStats = {
    collection: collectionName,
    itemsModified: 0,
    itemsAdded: 0,
    totalResultItems: 0,
  };

  // Start with a deep copy of merged collection
  const result = mergedCollection.map((item) => ({ ...item }));
  const itemMap = new Map(result.map((item) => [item._id, item]));

  // Apply modifications
  if (diff.modified) {
    for (const mod of diff.modified) {
      const existing = itemMap.get(mod._id);
      if (existing) {
        // Overlay changes onto existing item
        Object.assign(existing, mod.changes);
        stats.itemsModified++;

        if (verbose) {
          console.log(
            `   [${collectionName}] Modified: ${mod._id} (${
              Object.keys(mod.changes).length
            } properties)`
          );
          console.log(`      Changed: ${Object.keys(mod.changes).join(", ")}`);
        }
      } else if (verbose) {
        console.log(
          `   ⚠️  [${collectionName}] Item not found for modification: ${mod._id}`
        );
      }
    }
  }

  // Add new items
  if (diff.added) {
    for (const item of diff.added) {
      if (!itemMap.has(item._id)) {
        result.push(item);
        itemMap.set(item._id, item);
        stats.itemsAdded++;

        if (verbose) {
          console.log(`   [${collectionName}] Added: ${item._id || "no-id"}`);
        }
      } else if (verbose) {
        console.log(
          `   ⚠️  [${collectionName}] Item already exists, skipping add: ${item._id}`
        );
      }
    }
  }

  stats.totalResultItems = result.length;
  return { result, stats };
}

/**
 * Apply full diff to merged data
 */
function applyDiff(
  mergedData: any,
  diffResult: DiffResult,
  verbose: boolean
): {
  enrichedData: any;
  allStats: ApplyStats[];
} {
  const enrichedData = { ...mergedData };
  const allStats: ApplyStats[] = [];

  // Process each collection in the diff
  for (const collectionName of Object.keys(diffResult)) {
    const mergedCollection = Array.isArray(mergedData[collectionName])
      ? mergedData[collectionName]
      : [];
    const collectionDiff = diffResult[collectionName];

    if (verbose) {
      console.log(`\n🔄 Applying diff to collection: ${collectionName}`);
    }

    const { result, stats } = applyDiffToCollection(
      mergedCollection,
      collectionDiff,
      collectionName,
      verbose
    );

    enrichedData[collectionName] = result;
    allStats.push(stats);
  }

  return { enrichedData, allStats };
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

function printStats(stats: ApplyStats[], targetFileName?: string): void {
  const header = targetFileName
    ? `APPLY SUMMARY - ${targetFileName}`
    : "APPLY SUMMARY";
  console.log("\n" + "=".repeat(80));
  console.log(header);
  console.log("=".repeat(80));

  let totalModified = 0;
  let totalAdded = 0;

  for (const stat of stats) {
    if (stat.itemsModified === 0 && stat.itemsAdded === 0) {
      continue; // Skip collections with no changes
    }

    console.log(`\n📦 ${stat.collection}:`);
    console.log(`   Result items:       ${stat.totalResultItems}`);
    if (stat.itemsModified > 0) {
      console.log(`   ✏️  Modified:        ${stat.itemsModified}`);
    }
    if (stat.itemsAdded > 0) {
      console.log(`   ✨ Added:           ${stat.itemsAdded}`);
    }

    totalModified += stat.itemsModified;
    totalAdded += stat.itemsAdded;
  }

  console.log("\n" + "-".repeat(80));
  if (totalModified > 0 || totalAdded > 0) {
    console.log(
      `📈 TOTAL: ${totalModified} item(s) modified, ${totalAdded} item(s) added`
    );
  } else {
    console.log(`📈 TOTAL: No changes applied`);
  }
  console.log("=".repeat(80) + "\n");
}

function applyDiffForFile(
  targetPath: string,
  mergedSourcePath: string,
  mergedData: any,
  options: ApplyOptions,
  showHeader: boolean = true
): {
  hasChanges: boolean;
  totalChanges: number;
} {
  const targetFileName = path.basename(targetPath);
  const targetDir = path.dirname(targetPath);
  const targetFileBaseName = path.basename(targetPath, ".json");
  const diffPath = path.join(
    targetDir,
    ".diff",
    `${targetFileBaseName}.diff.json`
  );

  if (showHeader) {
    console.log(`\n🚀 Applying diff for: ${targetFileName}`);
    if (options.dryRun) {
      console.log("🔍 DRY RUN MODE - No files will be modified\n");
    }
  }

  // Check if diff file exists
  let enrichedData: any;
  let totalChanges = 0;

  if (!fs.existsSync(diffPath)) {
    // No diff file means no task-specific changes, but we still need to enrich with merged data
    if (showHeader || options.verbose) {
      console.log(
        `ℹ️  No diff file found - using merged data as-is (no task-specific changes)`
      );
    }
    enrichedData = mergedData;
  } else {
    // Load diff file
    if (options.verbose || showHeader) {
      console.log(`📖 Loading diff file: ${path.basename(diffPath)}`);
    }
    const diffResult: DiffResult = loadJsonFile(diffPath);

    // Apply diff
    if (options.verbose || showHeader) {
      console.log("🔄 Applying changes...");
    }

    const { enrichedData: data, allStats } = applyDiff(
      mergedData,
      diffResult,
      options.verbose
    );

    enrichedData = data;

    // Print statistics
    printStats(allStats, showHeader ? undefined : targetFileName);

    // Check if any changes were applied
    totalChanges =
      allStats.reduce((sum, stat) => sum + stat.itemsModified, 0) +
      allStats.reduce((sum, stat) => sum + stat.itemsAdded, 0);
  }

  // Save enriched backend file
  if (!options.dryRun) {
    // Create backup
    const backupPath = createBackup(targetPath);
    if (showHeader || options.verbose) {
      console.log(
        `✅ Backup created: ${path.relative(process.cwd(), backupPath)}`
      );
    }

    // Write enriched data
    writeJsonFile(targetPath, enrichedData);

    if (showHeader) {
      console.log(
        `💾 Enriched data saved: ${path.relative(process.cwd(), targetPath)}`
      );
      if (totalChanges > 0) {
        console.log(
          `✅ Applied ${totalChanges} task-specific changes + base enrichment!\n`
        );
      } else {
        console.log("✅ Applied base enrichment (no task-specific changes)!\n");
      }
    }
  } else if (showHeader) {
    console.log("🔍 Dry run completed - no files were modified\n");
  }

  return { hasChanges: true, totalChanges };
}

function applyDiffForDirectory(
  targetDirPath: string,
  mergedSourcePath: string,
  options: ApplyOptions
): void {
  console.log(`\n🚀 Applying diffs for directory: ${targetDirPath}`);
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

  // Load merged source file once
  console.log(
    `📖 Loading merged source file: ${path.basename(mergedSourcePath)}`
  );
  const mergedData = loadJsonFile(mergedSourcePath);

  // Check if .diff directory exists
  const diffDir = path.join(targetDirPath, ".diff");
  if (!fs.existsSync(diffDir)) {
    console.warn(
      `⚠️  Warning: No .diff directory found at ${path.relative(
        process.cwd(),
        diffDir
      )}`
    );
    console.warn("   Run generate-diff first to create diff files.");
    return;
  }

  // Find all JSON files in the target directory
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
  let filesEnriched = 0;
  let filesWithTaskChanges = 0;
  let totalChanges = 0;
  let filesSkipped = 0;

  for (const file of files) {
    const targetPath = path.join(targetDirPath, file);
    console.log(`${"─".repeat(80)}`);
    console.log(`📄 Processing: ${file}`);

    try {
      const result = applyDiffForFile(
        targetPath,
        mergedSourcePath,
        mergedData,
        options,
        false
      );
      filesProcessed++;
      totalChanges += result.totalChanges;
      if (result.hasChanges) {
        filesEnriched++;
        if (result.totalChanges > 0) {
          filesWithTaskChanges++;
        }
      } else {
        filesSkipped++;
      }
    } catch (error) {
      console.error(`❌ Error processing ${file}:`);
      console.error(
        `   ${error instanceof Error ? error.message : String(error)}`
      );
      filesSkipped++;
    }

    console.log(); // Empty line between files
  }

  // Print overall summary
  console.log("=".repeat(80));
  console.log("📊 BATCH SUMMARY");
  console.log("=".repeat(80));
  console.log(`Files processed:                ${filesProcessed}`);
  console.log(`Files enriched:                 ${filesEnriched}`);
  console.log(`Files with task-specific data:  ${filesWithTaskChanges}`);
  if (filesSkipped > 0) {
    console.log(`Files skipped (errors):         ${filesSkipped}`);
  }
  console.log(`Total task-specific changes:    ${totalChanges}`);

  if (!options.dryRun && filesEnriched > 0) {
    const backupDir = path.join(targetDirPath, ".backup");
    console.log(
      `✅ All backups saved in: ${path.relative(process.cwd(), backupDir)}/`
    );
    console.log("💾 All enriched files saved successfully!");
    console.log(`   ${filesEnriched} files now have scraped data enrichment`);
    if (filesWithTaskChanges > 0) {
      console.log(
        `   ${filesWithTaskChanges} files also have task-specific customizations\n`
      );
    } else {
      console.log();
    }
  } else if (options.dryRun) {
    console.log("🔍 Dry run completed - no files were modified\n");
  } else {
    console.log("⚠️  No files enriched\n");
  }
}

function main() {
  const options = parseArgs();

  // Resolve and validate merged source file
  const resolvedMergedSourcePath = resolvePath(options.mergedSourceFile);
  validateFilePath(resolvedMergedSourcePath);

  if (options.targetDir) {
    // Directory mode - process all JSON files in directory
    const resolvedDirPath = resolvePath(options.targetDir);
    applyDiffForDirectory(resolvedDirPath, resolvedMergedSourcePath, options);
  } else if (options.targetFile) {
    // Single file mode
    const resolvedTargetPath = resolvePath(options.targetFile);
    validateFilePath(resolvedTargetPath);

    // Load merged source data once
    const mergedData = loadJsonFile(resolvedMergedSourcePath);

    applyDiffForFile(
      resolvedTargetPath,
      resolvedMergedSourcePath,
      mergedData,
      options,
      true
    );
  }
}

// Run the script
main();
