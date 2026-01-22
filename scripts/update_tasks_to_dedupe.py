#!/usr/bin/env python3
import json
from pathlib import Path
import sys

if len(sys.argv) < 2:
    print("Usage: python3 update_tasks_to_dedupe.py /path/to/tasks/folder [--dry-run]")
    print("       Expects mapping.json in current directory")
    sys.exit(1)

tasks_dir = Path(sys.argv[1])
mapping_path = Path("mapping.json")
dry_run = "--dry-run" in sys.argv

if not mapping_path.exists():
    print(f"Error: {mapping_path.absolute()} not found")
    sys.exit(1)

with open(mapping_path) as fp:
    mapping = json.load(fp)

updated = 0
unchanged = 0

for f in sorted(tasks_dir.glob("*.json")):
    with open(f) as fp:
        data = json.load(fp)
    
    old_name = data.get("initial_backend_state_name")
    if old_name and old_name in mapping and old_name != mapping[old_name]:
        new_name = mapping[old_name]
        print(f"{f.name}: {old_name} -> {new_name}")
        
        if not dry_run:
            data["initial_backend_state_name"] = new_name
            with open(f, "w") as fp:
                json.dump(data, fp, indent=2)
        updated += 1
    else:
        unchanged += 1

print(f"\n{'Would update' if dry_run else 'Updated'}: {updated}")
print(f"Unchanged: {unchanged}")