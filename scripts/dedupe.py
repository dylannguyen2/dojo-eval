#!/usr/bin/env python3
import json
import hashlib
import shutil
from pathlib import Path
import sys

if len(sys.argv) < 2:
    print("Usage: python3 dedupe.py /path/to/initial-backend-data/folder")
    sys.exit(1)

source_dir = Path(sys.argv[1])
output_dir = source_dir / "deduplicated"
output_dir.mkdir(exist_ok=True)

hash_to_file = {}
mapping = {}

# Step 1: Copy all deduplicated files to output_dir and build mapping
for f in sorted(source_dir.glob("*.json")):
    with open(f) as fp:
        content = json.dumps(json.load(fp), sort_keys=True, separators=(',', ':'))
    h = hashlib.sha256(content.encode()).hexdigest()
    
    # Strip .json extension for mapping (to match task file format)
    name_without_ext = f.stem  # f.stem gives filename without extension
    
    if h in hash_to_file:
        mapping[name_without_ext] = hash_to_file[h]
    else:
        hash_to_file[h] = name_without_ext
        mapping[name_without_ext] = name_without_ext
        shutil.copy(f, output_dir / f.name)

mapping_path = Path("mapping.json")
with open(mapping_path, "w") as fp:
    json.dump(mapping, fp, indent=2)

# Step 2: Delete all original json files in the source_dir
for f in source_dir.glob("*.json"):
    f.unlink()

# Step 3: Move deduplicated files back to the original source_dir
for dedupe_file in output_dir.glob("*.json"):
    shutil.move(str(dedupe_file), str(source_dir / dedupe_file.name))

# Step 4: Remove the deduplicated folder
try:
    output_dir.rmdir()
except OSError:
    shutil.rmtree(output_dir, ignore_errors=True)

dupes = sum(1 for k, v in mapping.items() if k != v)
print(f"Original: {len(mapping)} files")
print(f"Deduplicated: {len(mapping) - dupes} files")
print(f"Duplicates removed: {dupes}")
print(f"Deduplicated files moved back to {source_dir}")
print(f"Mapping saved to {mapping_path.absolute()}")