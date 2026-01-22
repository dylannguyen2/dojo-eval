import { readFileSync, existsSync } from "fs";
import { resolve } from "path";

const LOCAL_SERVER_URL =
  process.env.LOCAL_SERVER_URL || "http://localhost:8081";

interface IndexConfig {
  collection: string;
  name: string;
  fields: Record<string, string>;
  options?: Record<string, unknown>;
}

interface IndicesFile {
  indices: IndexConfig[];
}

interface IndexStatus {
  collection: string;
  status: "in_progress" | "pending" | "completed" | "failed";
}
async function pollIndexCreationStatus(
  timeoutSeconds = 600,
  pollInterval = 5
): Promise<void> {
  console.log("Polling for index creation completion...");
  let elapsed = 0;

  while (elapsed < timeoutSeconds) {
    try {
      const response = await fetch(`${LOCAL_SERVER_URL}/search-index-status`);

      if (!response.ok) {
        console.log(
          `Warning: Failed to get index creation status: ${response.status}`
        );
        await new Promise((resolve) =>
          setTimeout(resolve, pollInterval * 1000)
        );
        elapsed += pollInterval;
        continue;
      }

      const indexes: IndexStatus[] = (await response.json())["indexes"];

      let in_progress = indexes.filter(
        (index: IndexStatus) => index.status === "in_progress"
      );
      let pending = indexes.filter(
        (index: IndexStatus) => index.status === "pending"
      );
      let completed = indexes.filter(
        (index: IndexStatus) => index.status === "completed"
      );
      let failed = indexes.filter(
        (index: IndexStatus) => index.status === "failed"
      );

      if (in_progress.length > 0) {
        console.log("Index creation in progress:", in_progress);
      }
      if (pending.length > 0) {
        console.log("Index creation pending:", pending);
      }
      if (completed.length > 0) {
        console.log("Index creation completed:", completed);
      }
      if (failed.length > 0) {
        console.log("Index creation failed:", failed);
      }

      if (in_progress.length === 0 && pending.length === 0) {
        if (failed.length > 0) {
          throw new Error(
            `Index creation failed: ${failed
              .map((index: IndexStatus) => index.collection)
              .join(", ")}`
          );
        }
        return;
      }

      await new Promise((resolve) => setTimeout(resolve, pollInterval * 1000));
      elapsed += pollInterval;
    } catch (error) {
      console.log(`Warning: Error polling index creation status: ${error}`);
      await new Promise((resolve) => setTimeout(resolve, pollInterval * 1000));
      elapsed += pollInterval;
    }
  }

  throw new Error(
    `Index creation did not complete within ${timeoutSeconds} seconds`
  );
}

async function createIndices(indicesPath: string) {
  console.log(`\nCreating indices from: ${indicesPath}`);

  const indicesData: IndicesFile = JSON.parse(
    readFileSync(indicesPath, "utf-8")
  );

  if (!indicesData.indices || indicesData.indices.length === 0) {
    console.log("No indices configured");
    return;
  }

  try {
    const response = await fetch(`${LOCAL_SERVER_URL}/create-search-index`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ indexes: indicesData.indices }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `Failed to create search indices: ${response.status} ${errorText}`
      );
    }

    console.log(
      `✓ Index creation started for ${indicesData.indices.length} search indices`
    );

    // Poll until index creation is complete.
    await pollIndexCreationStatus();
  } catch (error) {
    console.error(
      `✗ Failed to create search indices:`,
      error instanceof Error ? error.message : error
    );
    throw error;
  }
}

function parseArgs(): { jsonPath: string; indicesPath?: string } {
  const args = process.argv.slice(2);
  let jsonPath: string | undefined;
  let indicesPath: string | undefined;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--indices" && args[i + 1]) {
      indicesPath = args[i + 1];
      i++;
    } else if (!jsonPath) {
      jsonPath = args[i];
    }
  }

  if (!jsonPath) {
    console.error("Usage: npm run seed <json-file> [--indices <indices-file>]");
    process.exit(1);
  }

  return { jsonPath, indicesPath };
}

function chunkArray<T>(array: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < array.length; i += size) {
    chunks.push(array.slice(i, i + size));
  }
  return chunks;
}

async function seedCollection(
  collection: string,
  documents: any[]
): Promise<void> {
  if (!Array.isArray(documents) || documents.length === 0) {
    return;
  }

  // Chunk documents to avoid exceeding MongoDB's 48MB message size limit
  const CHUNK_SIZE = 10_000;
  const chunks = chunkArray(documents, CHUNK_SIZE);

  console.log(
    `Seeding ${collection}: ${documents.length} documents in ${chunks.length} chunks`
  );

  let totalInserted = 0;

  for (let i = 0; i < chunks.length; i++) {
    const chunk = chunks[i];

    try {
      const response = await fetch(`${LOCAL_SERVER_URL}/transaction`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Skip-Transaction-Log": "true",
        },
        body: JSON.stringify({
          mutations: [
            {
              type: "insert",
              collection,
              documents: chunk,
            },
          ],
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          `Failed to seed ${collection} (chunk ${i + 1}/${chunks.length}): ${
            response.status
          } ${errorText}`
        );
      }

      const result = await response.json();
      const insertedCount = Object.keys(result.insertedIds || {}).length;
      totalInserted += insertedCount;

      if (chunks.length > 1) {
        console.log(
          `  Chunk ${i + 1}/${
            chunks.length
          }: inserted ${insertedCount} documents`
        );
      }
    } catch (error) {
      console.error(
        `✗ Failed to seed ${collection} (chunk ${i + 1}/${chunks.length}):`,
        error instanceof Error ? error.message : error
      );
      throw error;
    }
  }

  console.log(`✓ Inserted ${totalInserted} documents into ${collection}`);
}

async function seed() {
  const { jsonPath, indicesPath: providedIndicesPath } = parseArgs();

  const fullPath = resolve(jsonPath);
  const data = JSON.parse(readFileSync(fullPath, "utf-8"));

  try {
    console.log("Seeding collections...");
    for (const [collection, documents] of Object.entries(data)) {
      await seedCollection(collection, documents as any[]);
    }

    // Create indices
    let indicesPath: string | null = null;

    if (!providedIndicesPath) {
      console.log(
        "\nNo indices file provided - skipping search index creation. You can provide an indices file with the --indices flag."
      );
    } else {
      const resolvedPath = resolve(providedIndicesPath);
      if (existsSync(resolvedPath)) {
        indicesPath = resolvedPath;
      } else {
        throw new Error(`Indices file not found: ${resolvedPath}`);
      }
    }

    // We create indices after seeding the collections because  it's faster
    if (indicesPath) {
      await createIndices(indicesPath);
    } else {
      console.log("\nNo indices file found - skipping index creation");
    }

    console.log("\nDone!");
  } catch (error) {
    console.error("Seeding failed:", error);
    process.exit(1);
  }
}

seed().catch(console.error);
