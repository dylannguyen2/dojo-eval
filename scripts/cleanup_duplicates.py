#!/usr/bin/env python3
"""
Clean up duplicate backend files after deduplication.

This script:
1. Replaces original files with deduplicated versions (for unique files)
2. Deletes duplicate files (where mapping[filename] != filename)
3. Removes the deduplicated folder
4. Optionally removes mapping.json
"""
import json
import shutil
from pathlib import Path
import sys

if len(sys.argv) < 2:
    print("Usage: python3 cleanup_duplicates.py /path/to/initial-backend-data/folder [--keep-mapping]")
    print("       Expects mapping.json in current directory")
    sys.exit(1)

source_dir = Path(sys.argv[1])
deduplicated_dir = source_dir / "deduplicated"
mapping_path = Path("mapping.json")
keep_mapping = "--keep-mapping" in sys.argv

if not mapping_path.exists():
    print(f"Error: {mapping_path.absolute()} not found")
    sys.exit(1)

if not deduplicated_dir.exists():
    print(f"Error: {deduplicated_dir} not found")
    print("Make sure you've run dedupe.py first")
    sys.exit(1)

with open(mapping_path) as fp:
    mapping = json.load(fp)

# Step 1: Replace original files with deduplicated versions (for unique files)
replaced = 0
for original_name, deduplicated_name in mapping.items():
    original_path = source_dir / original_name
    deduplicated_path = deduplicated_dir / deduplicated_name
    
    # Only replace if it's a unique file (mapping points to itself)
    if original_name == deduplicated_name:
        if deduplicated_path.exists():
            shutil.copy2(deduplicated_path, original_path)
            replaced += 1
        else:
            print(f"Warning: Deduplicated file not found: {deduplicated_path}")

# Step 2: Delete duplicate files
deleted = 0
for original_name, deduplicated_name in mapping.items():
    original_path = source_dir / original_name
    
    # Delete if it's a duplicate (mapping points to different file)
    if original_name != deduplicated_name:
        if original_path.exists():
            original_path.unlink()
            deleted += 1
            print(f"Deleted duplicate: {original_name} -> {deduplicated_name}")

# Step 3: Remove deduplicated folder
if deduplicated_dir.exists():
    shutil.rmtree(deduplicated_dir)
    print(f"Removed deduplicated folder: {deduplicated_dir}")

# Step 4: Remove mapping.json (unless --keep-mapping flag is set)
if not keep_mapping:
    mapping_path.unlink()
    print(f"Removed mapping file: {mapping_path}")

print(f"\nSummary:")
print(f"  Files replaced: {replaced}")
print(f"  Duplicates deleted: {deleted}")
print(f"  Deduplicated folder removed: ✓")
if not keep_mapping:
    print(f"  Mapping file removed: ✓")
else:
    print(f"  Mapping file kept: ✓")
