#!/usr/bin/env tsx

import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";
import { fileURLToPath } from "url";

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface GenerateStats {
  collection: string;
  totalItems: number;
  itemsWithExistingIds: number;
  idsGenerated: number;
  generatedIds: string[];
}

interface GenerateOptions {
  filePath?: string;
  dirPath?: string;
  dryRun: boolean;
  collections?: string[];
  verbose: boolean;
}

function parseArgs(): GenerateOptions {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes("--help") || args.includes("-h")) {
    console.log(`
Usage: pnpm tsx scripts/generate-collection-ids.ts <file-path|--dir dir-path> [options]

Description:
  Generates deterministic _id fields for items in high-level collections (arrays)
  within JSON backend data files. IDs are content-based hashes, so they remain
  stable across multiple runs if the item content doesn't change.

Arguments:
  file-path         Path to a single JSON file (relative or absolute)
  --dir dir-path    Process all JSON files in the specified directory

Options:
  --dry-run         Preview changes without modifying files
  --collections     Comma-separated list of collections to process (e.g., users,posts)
                    If not specified, all top-level array collections are processed
  --verbose, -v     Show detailed output including generated IDs
  --help, -h        Show this help message

Examples:
  # Generate IDs for all collections in a single file
  pnpm tsx scripts/generate-collection-ids.ts weibo/app/initial_data.json

  # Process all JSON files in a directory
  pnpm tsx scripts/generate-collection-ids.ts --dir dojo-bench-customer-colossus/initial-backend-data/weibo

  # Dry run for a directory
  pnpm tsx scripts/generate-collection-ids.ts --dir dojo-bench-customer-colossus/initial-backend-data/weibo --dry-run

  # Process directory with specific collections only
  pnpm tsx scripts/generate-collection-ids.ts --dir ../dojo-bench-customer-colossus/initial-backend-data/jd --collections users,posts

  # Verbose output for a single file
  pnpm tsx scripts/generate-collection-ids.ts weibo/app/initial_data.json -v

  # Process bench file
  pnpm tsx scripts/generate-collection-ids.ts dojo-bench-customer-colossus/initial-backend-data/weibo/default_backend.json
    `);
    process.exit(args.includes("--help") || args.includes("-h") ? 0 : 1);
  }

  const dryRun = args.includes("--dry-run");
  const verbose = args.includes("--verbose") || args.includes("-v");

  // Check for --dir flag
  let dirPath: string | undefined;
  const dirIndex = args.findIndex((arg) => arg === "--dir");
  if (dirIndex !== -1 && args[dirIndex + 1]) {
    dirPath = args[dirIndex + 1];
  }

  // Get file path (if not using --dir)
  let filePath: string | undefined;
  if (!dirPath) {
    // Find the first arg that's not a flag
    filePath = args.find(
      (arg) => !arg.startsWith("--") && !arg.startsWith("-")
    );
  }

  let collections: string[] | undefined;
  const collectionsIndex = args.findIndex((arg) =>
    arg.startsWith("--collections")
  );
  if (collectionsIndex !== -1) {
    if (args[collectionsIndex].includes("=")) {
      // Format: --collections=users,posts
      collections = args[collectionsIndex].split("=")[1].split(",");
    } else if (args[collectionsIndex + 1]) {
      // Format: --collections users,posts
      collections = args[collectionsIndex + 1].split(",");
    }
  }

  if (!filePath && !dirPath) {
    console.error("❌ Error: Must provide either a file path or --dir flag");
    console.error("   Run with --help for usage information");
    process.exit(1);
  }

  return { filePath, dirPath, dryRun, collections, verbose };
}

function resolveFilePath(filePath: string): string {
  // If absolute path, return as is
  if (path.isAbsolute(filePath)) {
    return filePath;
  }

  // Try relative to current working directory
  const cwdPath = path.resolve(process.cwd(), filePath);
  if (fs.existsSync(cwdPath)) {
    return cwdPath;
  }

  // Try relative to script directory's parent (project root)
  const rootPath = path.resolve(__dirname, "..", filePath);
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
    console.log(
      `✅ Backup created: ${path.relative(process.cwd(), backupPath)}`
    );
    return backupPath;
  } catch (error) {
    console.error(`❌ Error creating backup:`);
    console.error(
      `   ${error instanceof Error ? error.message : String(error)}`
    );
    process.exit(1);
  }
}

function hasIdField(item: any): boolean {
  return item && typeof item === "object" && "_id" in item;
}

/**
 * Generate a deterministic ID for an item based on its content.
 * Uses SHA-256 hash of the stringified item (sorted keys for consistency).
 */
function generateDeterministicId(
  item: any,
  collectionName: string,
  index: number
): string {
  // Create a stable representation of the item (excluding _id if it exists)
  const { _id, ...itemWithoutId } = item;
  const stableItem = JSON.stringify(
    itemWithoutId,
    Object.keys(itemWithoutId).sort()
  );
  const hash = crypto.createHash("sha256").update(stableItem).digest("hex");

  // Use first 12 characters of hash + collection prefix for readability
  // Include index as fallback for collision detection
  return `${collectionName}_${hash.substring(0, 12)}`;
}

/**
 * Process a single collection and generate IDs for items that don't have them.
 */
function processCollection(
  collection: any[],
  collectionName: string,
  verbose: boolean
): {
  processedCollection: any[];
  stats: GenerateStats;
} {
  if (!Array.isArray(collection)) {
    throw new Error(`Collection "${collectionName}" is not an array`);
  }

  const stats: GenerateStats = {
    collection: collectionName,
    totalItems: collection.length,
    itemsWithExistingIds: 0,
    idsGenerated: 0,
    generatedIds: [],
  };

  const processedCollection = collection.map((item, index) => {
    // Skip non-object items
    if (!item || typeof item !== "object") {
      return item;
    }

    // Check if item already has an ID
    if (hasIdField(item)) {
      stats.itemsWithExistingIds++;
      return item;
    }

    // Generate new ID
    const newId = generateDeterministicId(item, collectionName, index);
    stats.idsGenerated++;
    stats.generatedIds.push(newId);

    if (verbose) {
      console.log(`   Generated ID: ${newId} (index: ${index})`);
    }

    return { _id: newId, ...item };
  });

  return { processedCollection, stats };
}

/**
 * Process the entire JSON data file and generate IDs for specified collections.
 */
function generateCollectionIds(
  data: any,
  targetCollections?: string[],
  verbose: boolean = false
): {
  processedData: any;
  allStats: GenerateStats[];
} {
  const processedData = { ...data };
  const allStats: GenerateStats[] = [];

  // Get all top-level array collections
  const allCollections = Object.keys(data).filter((key) =>
    Array.isArray(data[key])
  );

  // Determine which collections to process
  const collectionsToProcess = targetCollections
    ? allCollections.filter((col) => targetCollections.includes(col))
    : allCollections;

  if (targetCollections && collectionsToProcess.length === 0) {
    console.warn(
      `⚠️  Warning: None of the specified collections (${targetCollections.join(
        ", "
      )}) found in the file`
    );
    console.warn(`   Available collections: ${allCollections.join(", ")}`);
  }

  if (verbose && collectionsToProcess.length > 0) {
    console.log(
      `\n📋 Processing ${
        collectionsToProcess.length
      } collection(s): ${collectionsToProcess.join(", ")}\n`
    );
  }

  for (const collectionName of collectionsToProcess) {
    if (verbose) {
      console.log(`\n🔄 Processing collection: ${collectionName}`);
    }

    try {
      const { processedCollection, stats } = processCollection(
        data[collectionName],
        collectionName,
        verbose
      );

      processedData[collectionName] = processedCollection;
      allStats.push(stats);
    } catch (error) {
      console.error(`❌ Error processing collection "${collectionName}":`);
      console.error(
        `   ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  return { processedData, allStats };
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

function printStats(stats: GenerateStats[], filename?: string): void {
  const header = filename
    ? `ID GENERATION SUMMARY - ${filename}`
    : "ID GENERATION SUMMARY";
  console.log("\n" + "=".repeat(80));
  console.log(header);
  console.log("=".repeat(80));

  let totalItems = 0;
  let totalExisting = 0;
  let totalGenerated = 0;

  for (const stat of stats) {
    if (
      stat.idsGenerated === 0 &&
      stat.itemsWithExistingIds === stat.totalItems
    ) {
      continue; // Skip collections where all items already have IDs
    }

    console.log(`\n📦 ${stat.collection}:`);
    console.log(`   Total items:        ${stat.totalItems}`);
    console.log(`   Existing IDs:       ${stat.itemsWithExistingIds}`);
    if (stat.idsGenerated > 0) {
      console.log(`   ✨ Generated IDs:   ${stat.idsGenerated}`);
    }

    totalItems += stat.totalItems;
    totalExisting += stat.itemsWithExistingIds;
    totalGenerated += stat.idsGenerated;
  }

  console.log("\n" + "-".repeat(80));
  if (totalGenerated > 0) {
    console.log(
      `📈 TOTAL: ${totalGenerated} ID(s) generated out of ${totalItems} item(s)`
    );
    console.log(`   (${totalExisting} item(s) already had IDs)`);
  } else {
    console.log(`📈 TOTAL: No IDs generated - all items already have IDs`);
  }
  console.log("=".repeat(80) + "\n");
}

function processFile(
  filePath: string,
  options: GenerateOptions,
  showHeader: boolean = true
): { totalGenerated: number; hasChanges: boolean } {
  if (showHeader) {
    console.log(
      `\n🚀 Generating collection IDs for: ${path.basename(filePath)}`
    );
    if (options.dryRun) {
      console.log("🔍 DRY RUN MODE - No files will be modified\n");
    }
    if (options.collections) {
      console.log(`🎯 Target collections: ${options.collections.join(", ")}\n`);
    }
  }

  // Validate file path
  try {
    validateFilePath(filePath);
  } catch (error) {
    console.error(`❌ Skipping file: ${error}`);
    return { totalGenerated: 0, hasChanges: false };
  }

  // Load JSON file
  if (options.verbose || showHeader) {
    console.log("📖 Loading JSON file...");
  }
  const data = loadJsonFile(filePath);

  // Generate IDs
  if (options.verbose || showHeader) {
    console.log("🔑 Generating IDs for items without _id field...");
  }
  const { processedData, allStats } = generateCollectionIds(
    data,
    options.collections,
    options.verbose
  );

  // Print statistics
  printStats(allStats, showHeader ? undefined : path.basename(filePath));

  // Check if any IDs were generated
  const totalGenerated = allStats.reduce(
    (sum, stat) => sum + stat.idsGenerated,
    0
  );

  if (totalGenerated === 0) {
    if (showHeader) {
      console.log("✨ All items already have IDs - nothing to do!\n");
    }
    return { totalGenerated: 0, hasChanges: false };
  }

  // Save results
  if (!options.dryRun) {
    createBackup(filePath);

    console.log("💾 Writing updated data to file...");
    writeJsonFile(filePath, processedData);

    if (showHeader) {
      console.log("✅ ID generation completed successfully!\n");
    }
  } else {
    if (showHeader) {
      console.log("🔍 Dry run completed - no files were modified\n");
    }
  }

  return { totalGenerated, hasChanges: true };
}

function processDirectory(dirPath: string, options: GenerateOptions): void {
  console.log(`\n🚀 Processing directory: ${dirPath}`);
  if (options.dryRun) {
    console.log("🔍 DRY RUN MODE - No files will be modified");
  }
  if (options.collections) {
    console.log(`🎯 Target collections: ${options.collections.join(", ")}`);
  }
  console.log();

  // Validate directory
  if (!fs.existsSync(dirPath)) {
    console.error(`❌ Error: Directory not found: ${dirPath}`);
    process.exit(1);
  }

  if (!fs.statSync(dirPath).isDirectory()) {
    console.error(`❌ Error: Path is not a directory: ${dirPath}`);
    process.exit(1);
  }

  // Find all JSON files in the directory
  const files = fs
    .readdirSync(dirPath)
    .filter((file) => file.endsWith(".json"))
    .sort();

  if (files.length === 0) {
    console.warn(`⚠️  Warning: No JSON files found in ${dirPath}`);
    return;
  }

  console.log(`📁 Found ${files.length} JSON file(s) to process\n`);

  // Process each file
  let filesProcessed = 0;
  let filesWithChanges = 0;
  let totalIdsGenerated = 0;
  let filesSkipped = 0;

  for (const file of files) {
    const filePath = path.join(dirPath, file);
    console.log(`\n${"─".repeat(80)}`);
    console.log(`📄 Processing: ${file}`);
    console.log("─".repeat(80));

    try {
      const result = processFile(filePath, options, false);
      filesProcessed++;
      totalIdsGenerated += result.totalGenerated;
      if (result.hasChanges) {
        filesWithChanges++;
      }
    } catch (error) {
      console.error(`❌ Error processing ${file}:`);
      console.error(
        `   ${error instanceof Error ? error.message : String(error)}`
      );
      filesSkipped++;
    }
  }

  // Print overall summary
  console.log("\n" + "=".repeat(80));
  console.log("DIRECTORY PROCESSING SUMMARY");
  console.log("=".repeat(80));
  console.log(`\n📊 Files processed:        ${filesProcessed}`);
  console.log(`   Files with changes:    ${filesWithChanges}`);
  console.log(`   Files skipped/errors:  ${filesSkipped}`);
  console.log(`   Total IDs generated:   ${totalIdsGenerated}`);
  console.log("\n" + "=".repeat(80));

  if (!options.dryRun && totalIdsGenerated > 0) {
    console.log("\n✅ Directory processing completed successfully!\n");
  } else if (options.dryRun) {
    console.log("\n🔍 Dry run completed - no files were modified\n");
  } else {
    console.log("\n✨ All files already have IDs - nothing to do!\n");
  }
}

function main() {
  const options = parseArgs();

  if (options.dirPath) {
    // Directory mode - process all JSON files in directory
    const resolvedDirPath = resolveFilePath(options.dirPath);
    processDirectory(resolvedDirPath, options);
  } else if (options.filePath) {
    // Single file mode
    const resolvedPath = resolveFilePath(options.filePath);
    processFile(resolvedPath, options, true);
  }
}

// Run the script
main();
