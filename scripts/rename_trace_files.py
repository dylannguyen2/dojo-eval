#!/usr/bin/env python3
"""
Rename trace files that end with '-trace.json' to remove the '-trace' suffix.
This ensures trace filenames match their corresponding task IDs.

Example:
  add-sprint-goals-alignment-v2-trace.json -> add-sprint-goals-alignment-v2.json
"""

import argparse
import logging
from pathlib import Path
from typing import List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def find_trace_files_to_rename(traces_dir: Path) -> List[Tuple[Path, Path]]:
    """
    Find all trace files ending with '-trace.json' and generate new names.
    
    Returns:
        List of tuples (old_path, new_path) for files to rename
    """
    renames = []
    
    for trace_file in traces_dir.glob('*-trace.json'):
        # Generate new name by removing '-trace' before '.json'
        new_name = trace_file.name.replace('-trace.json', '.json')
        new_path = trace_file.parent / new_name
        
        # Check if target file already exists
        if new_path.exists():
            logger.warning(f"⚠️  Target file already exists: {new_name}")
            logger.warning(f"   Will NOT rename: {trace_file.name}")
            continue
        
        renames.append((trace_file, new_path))
    
    return renames


def main():
    parser = argparse.ArgumentParser(
        description='Rename trace files to remove -trace suffix'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be renamed without actually renaming'
    )
    parser.add_argument(
        '--traces-dir',
        type=Path,
        default=Path('dojo-bench-customer-colossus/traces/notion'),
        help='Path to traces directory (default: ./dojo-bench-customer-colossus/traces/notion)'
    )
    
    args = parser.parse_args()
    
    # Validate path
    if not args.traces_dir.exists():
        logger.error(f"Traces directory not found: {args.traces_dir}")
        return 1
    
    if not args.traces_dir.is_dir():
        logger.error(f"Path is not a directory: {args.traces_dir}")
        return 1
    
    # Find files to rename
    logger.info(f"Searching for trace files in: {args.traces_dir}")
    renames = find_trace_files_to_rename(args.traces_dir)
    
    if not renames:
        logger.info("\n✓ No trace files found with '-trace.json' suffix")
        return 0
    
    # Display what will be renamed
    logger.info(f"\nFound {len(renames)} file(s) to rename:")
    if args.dry_run:
        logger.info("[DRY RUN MODE - No files will be renamed]\n")
    else:
        logger.info("")
    
    for old_path, new_path in renames:
        prefix = "[DRY RUN]" if args.dry_run else "Renaming:"
        logger.info(f"{prefix} {old_path.name}")
        logger.info(f"       -> {new_path.name}")
        logger.info("")
        
        # Perform rename if not dry run
        if not args.dry_run:
            try:
                old_path.rename(new_path)
            except Exception as e:
                logger.error(f"✗ Failed to rename {old_path.name}: {e}")
                return 1
    
    # Print summary
    logger.info("=" * 80)
    if args.dry_run:
        logger.info(f"Would rename {len(renames)} file(s)")
        logger.info("\nRun without --dry-run to perform the rename")
    else:
        logger.info(f"✓ Successfully renamed {len(renames)} file(s)")
    
    return 0


if __name__ == '__main__':
    exit(main())
