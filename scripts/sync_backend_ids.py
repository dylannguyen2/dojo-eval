#!/usr/bin/env python3
"""
Backend ID Synchronization Script

Syncs _id fields from a source backend JSON file to target files by matching
items based on their content hash (excluding top-level _id).
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'


def create_content_hash(item: Dict[str, Any]) -> str:
    """
    Create a SHA256 hash of an item's content, excluding top-level _id.
    
    Args:
        item: Dictionary representing a data item
        
    Returns:
        SHA256 hash string
    """
    # Create a copy without top-level _id
    item_copy = {k: v for k, v in item.items() if k != '_id'}
    # Sort keys for deterministic hashing
    json_str = json.dumps(item_copy, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """
    Load and parse a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Parsed JSON data
        
    Raises:
        ValueError: If the file is invalid JSON
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {file_path}: {e}")


def build_hash_to_id_map(data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Build a mapping of content hashes to IDs for all arrays in the data.
    
    Args:
        data: Source data dictionary
        
    Returns:
        Dictionary mapping root keys to {hash: id} mappings
    """
    hash_maps = {}
    
    for key, value in data.items():
        if isinstance(value, list):
            hash_map = {}
            for item in value:
                if isinstance(item, dict) and '_id' in item:
                    content_hash = create_content_hash(item)
                    hash_map[content_hash] = item['_id']
            hash_maps[key] = hash_map
    
    return hash_maps


def sync_ids(
    source_data: Dict[str, Any],
    target_data: Dict[str, Any],
    dry_run: bool = False
) -> Tuple[Dict[str, Any], Dict[str, Tuple[int, int]]]:
    """
    Sync IDs from source to target based on content hash matching.
    
    Args:
        source_data: Source data with correct IDs
        target_data: Target data to update
        dry_run: If True, don't modify target_data
        
    Returns:
        Tuple of (updated_target_data, stats_per_key)
        where stats_per_key maps key -> (matched_count, updated_count)
    """
    # Build hash to ID mappings from source
    source_hash_maps = build_hash_to_id_map(source_data)
    
    stats = {}
    updated_data = json.loads(json.dumps(target_data))  # Deep copy
    
    for key, value in updated_data.items():
        if not isinstance(value, list):
            continue
            
        if key not in source_hash_maps:
            stats[key] = (0, 0)
            continue
        
        source_hash_map = source_hash_maps[key]
        matched_count = 0
        updated_count = 0
        
        for item in value:
            if not isinstance(item, dict) or '_id' not in item:
                continue
            
            content_hash = create_content_hash(item)
            
            if content_hash in source_hash_map:
                matched_count += 1
                source_id = source_hash_map[content_hash]
                
                if item['_id'] != source_id:
                    updated_count += 1
                    if not dry_run:
                        item['_id'] = source_id
        
        stats[key] = (matched_count, updated_count)
    
    return updated_data, stats


def create_backup(file_path: Path) -> Path:
    """
    Create a backup of the file with .bak extension.
    
    Args:
        file_path: Path to the file to backup
        
    Returns:
        Path to the backup file
    """
    backup_path = file_path.with_suffix(file_path.suffix + '.bak')
    shutil.copy2(file_path, backup_path)
    return backup_path


def write_json_file(file_path: Path, data: Dict[str, Any]) -> None:
    """
    Write data to a JSON file atomically using a temporary file.
    
    Args:
        file_path: Path to the target file
        data: Data to write
    """
    temp_path = file_path.with_suffix(file_path.suffix + '.tmp')
    
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Atomic rename
        temp_path.replace(file_path)
    except Exception:
        # Clean up temp file if write failed
        if temp_path.exists():
            temp_path.unlink()
        raise


def process_target_file(
    source_data: Dict[str, Any],
    target_path: Path,
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Process a single target file, syncing IDs from source.
    
    Args:
        source_data: Source data with correct IDs
        target_path: Path to target file
        dry_run: If True, don't modify files
        
    Returns:
        Tuple of (total_matched, total_updated)
    """
    prefix = f"{Colors.CYAN}[DRY RUN]{Colors.RESET} " if dry_run else ""
    
    print(f"\n{prefix}Processing: {Colors.BOLD}{target_path.name}{Colors.RESET}")
    
    try:
        target_data = load_json_file(target_path)
    except Exception as e:
        print(f"  {Colors.RED}✗ Error loading file: {e}{Colors.RESET}")
        return 0, 0
    
    # Sync IDs
    updated_data, stats = sync_ids(source_data, target_data, dry_run=True)
    
    total_matched = 0
    total_updated = 0
    
    # Print stats for each key
    for key, (matched, updated) in sorted(stats.items()):
        if matched > 0:
            verb = "would be updated" if dry_run else "updated"
            print(f"  {key}: {matched} matched, {updated} IDs {verb}")
            total_matched += matched
            total_updated += updated
    
    # If no updates needed, we're done
    if total_updated == 0:
        if total_matched > 0:
            print(f"  {Colors.GREEN}✓ All IDs already match{Colors.RESET}")
        return total_matched, total_updated
    
    # Perform actual updates if not dry run
    if not dry_run:
        try:
            # Re-sync without dry_run to get actual updated data
            updated_data, _ = sync_ids(source_data, target_data, dry_run=False)
            
            # Create backup
            backup_path = create_backup(target_path)
            print(f"  {Colors.GREEN}✓ Backup created: {backup_path.name}{Colors.RESET}")
            
            # Write updated file
            write_json_file(target_path, updated_data)
            print(f"  {Colors.GREEN}✓ File updated{Colors.RESET}")
        except Exception as e:
            print(f"  {Colors.RED}✗ Error updating file: {e}{Colors.RESET}")
            return total_matched, 0
    else:
        print(f"  {prefix}Would create backup and update file")
    
    return total_matched, total_updated


def main():
    parser = argparse.ArgumentParser(
        description='Sync _id fields from source backend file to target files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes without modifying files (recommended first)
  python scripts/sync_backend_ids.py \\
    --source weibo/app/initial_data.json \\
    --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo \\
    --dry-run

  # Actually sync IDs (creates backups)
  python scripts/sync_backend_ids.py \\
    --source weibo/app/initial_data.json \\
    --target-dir dojo-bench-customer-colossus/initial-backend-data/weibo
        """
    )
    
    parser.add_argument(
        '--source',
        type=str,
        required=True,
        help='Path to source JSON file (e.g., weibo/app/initial_data.json)'
    )
    
    parser.add_argument(
        '--target-dir',
        type=str,
        required=True,
        help='Path to directory containing target JSON files'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    
    args = parser.parse_args()
    
    # Convert to Path objects
    source_path = Path(args.source)
    target_dir = Path(args.target_dir)
    
    # Validate paths
    if not source_path.exists():
        print(f"{Colors.RED}Error: Source file not found: {source_path}{Colors.RESET}")
        sys.exit(1)
    
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"{Colors.RED}Error: Target directory not found: {target_dir}{Colors.RESET}")
        sys.exit(1)
    
    # Load source data
    print(f"{Colors.BOLD}Loading source file:{Colors.RESET} {source_path}")
    try:
        source_data = load_json_file(source_path)
    except Exception as e:
        print(f"{Colors.RED}Error loading source file: {e}{Colors.RESET}")
        sys.exit(1)
    
    # Get all JSON files in target directory
    target_files = sorted(target_dir.glob('*.json'))
    
    if not target_files:
        print(f"{Colors.YELLOW}Warning: No JSON files found in {target_dir}{Colors.RESET}")
        sys.exit(0)
    
    print(f"{Colors.BOLD}Target directory:{Colors.RESET} {target_dir}")
    print(f"{Colors.BOLD}Files to process:{Colors.RESET} {len(target_files)}")
    
    if args.dry_run:
        print(f"\n{Colors.CYAN}{Colors.BOLD}[DRY RUN MODE] No files will be modified{Colors.RESET}\n")
    
    # Process each target file
    total_files = 0
    total_matched = 0
    total_updated = 0
    
    for target_path in target_files:
        matched, updated = process_target_file(source_data, target_path, args.dry_run)
        if matched > 0:
            total_files += 1
        total_matched += matched
        total_updated += updated
    
    # Print summary
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    prefix = f"{Colors.CYAN}[DRY RUN] {Colors.RESET}" if args.dry_run else ""
    print(f"{Colors.BOLD}{prefix}Summary:{Colors.RESET}")
    print(f"  Files processed: {total_files}")
    print(f"  Total items matched: {total_matched:,}")
    
    if args.dry_run:
        print(f"  Total IDs that would be synchronized: {total_updated:,}")
        print(f"  {Colors.CYAN}No files were modified (dry-run mode){Colors.RESET}")
    else:
        print(f"  Total IDs synchronized: {total_updated:,}")
        if total_updated > 0:
            print(f"  {Colors.GREEN}✓ Files updated successfully{Colors.RESET}")
    
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")


if __name__ == '__main__':
    main()
