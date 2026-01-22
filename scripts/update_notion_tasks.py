#!/usr/bin/env python3
"""
Update Notion task JSON files with missing initial_state, environment, and success_criteria fields.

This script:
1. Loads CSV mapping of prompts to verification criteria
2. Updates Notion tasks only if fields are empty
3. Handles environment subfields individually
4. Matches user_prompt with CSV to populate success_criteria
5. Sets environment_type to "mcp" if empty or not "mcp"
6. Sets trace_id to task id if empty
7. Sets env_version to "1.4" if missing/empty
"""

import argparse
import csv
import json
import logging
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Fixed values for fields
FIXED_INITIAL_STATE = '{"currentUser":{"_id":"user-1","name":"Alice Chen","email":"alice@company.com"},"currentPageId":null,"currentWorkspaceId":"workspace-1","showHome":true,"sidebarOpen":true,"recentPageIds":[],"favoritePageIds":[]}'
FIXED_ENVIRONMENT_TYPE = "url"
FIXED_ENVIRONMENT_PATH = "https://d1r7ci8wg1jzo8.cloudfront.net/index.html"
FIXED_ENVIRONMENT_TYPE_FIELD = "gui"
FIXED_ENV_VERSION = "1.4"

# Fuzzy matching threshold
FUZZY_MATCH_THRESHOLD = 0.80


def load_csv_mapping(csv_path: Path) -> Dict[str, str]:
    """Load CSV file and create mapping from Prompt to Verification."""
    mapping = {}
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                prompt = row.get('Prompt', '').strip()
                verification = row.get('Verification', '').strip()
                if prompt:  # Only add if prompt is not empty
                    mapping[prompt] = verification
        
        logger.info(f"Loaded {len(mapping)} prompt-verification mappings from CSV")
        return mapping
    
    except Exception as e:
        logger.error(f"Failed to load CSV file: {e}")
        return {}


def fuzzy_match_prompt(user_prompt: str, csv_prompts: List[str], threshold: float = FUZZY_MATCH_THRESHOLD) -> Optional[str]:
    """Find best fuzzy match for user_prompt in CSV prompts."""
    best_match = None
    best_ratio = 0.0
    
    for csv_prompt in csv_prompts:
        ratio = SequenceMatcher(None, user_prompt.lower(), csv_prompt.lower()).ratio()
        if ratio > best_ratio and ratio >= threshold:
            best_ratio = ratio
            best_match = csv_prompt
    
    return best_match


def find_verification_for_prompt(user_prompt: str, csv_mapping: Dict[str, str]) -> Tuple[Optional[str], bool]:
    """
    Find verification criteria for a user prompt.
    
    Returns:
        (verification_text, found_match)
        - If exact match: (verification_text, True)
        - If fuzzy match: (verification_text, True)
        - If no match: (None, False)
    """
    # Try exact match first
    if user_prompt in csv_mapping:
        return csv_mapping[user_prompt], True
    
    # Try fuzzy match
    csv_prompts = list(csv_mapping.keys())
    best_match = fuzzy_match_prompt(user_prompt, csv_prompts)
    
    if best_match:
        return csv_mapping[best_match], True
    
    return None, False


def update_task_file(task_path: Path, csv_mapping: Dict[str, str], dry_run: bool = False, backup: bool = False) -> Dict[str, any]:
    """
    Update a single task file with missing fields.
    
    Returns dict with update statistics.
    """
    stats = {
        'updated': False,
        'changes': [],
        'warnings': []
    }
    
    try:
        # Load task JSON
        with open(task_path, 'r', encoding='utf-8') as f:
            task_data = json.load(f)
        
        # Track if we made actual changes
        made_changes = False
        
        # Update initial_state if missing or empty
        if not task_data.get('initial_state') or task_data.get('initial_state', '').strip() == '':
            task_data['initial_state'] = FIXED_INITIAL_STATE
            stats['changes'].append('initial_state: added')
            made_changes = True
        
        # Update environment subfields
        environment = task_data.get('environment', '')
        
        # Parse environment if it's a JSON string
        if isinstance(environment, str):
            try:
                env_obj = json.loads(environment) if environment else {}
            except json.JSONDecodeError:
                env_obj = {}
                stats['warnings'].append('environment: invalid JSON, recreating')
                # Don't set made_changes here - only set it if we actually fix the fields below
        else:
            env_obj = environment if isinstance(environment, dict) else {}
        
        env_changed = False
        
        # Check and update type subfield
        if not env_obj.get('type') or env_obj.get('type', '').strip() == '':
            env_obj['type'] = FIXED_ENVIRONMENT_TYPE
            stats['changes'].append('environment.type: set to "url"')
            env_changed = True
        
        # Check and update path subfield
        if not env_obj.get('path') or env_obj.get('path', '').strip() == '':
            env_obj['path'] = FIXED_ENVIRONMENT_PATH
            stats['changes'].append('environment.path: set to CDN URL')
            env_changed = True
        
        # Only update environment if we changed it
        if env_changed:
            task_data['environment'] = json.dumps(env_obj, ensure_ascii=False)
            made_changes = True
        
        # Update success_criteria in instructions
        instructions = task_data.get('instructions', '')
        
        # Parse instructions if it's a JSON string
        if isinstance(instructions, str):
            try:
                instr_obj = json.loads(instructions) if instructions else {}
            except json.JSONDecodeError:
                instr_obj = {}
                stats['warnings'].append('instructions: invalid JSON')
                # Don't set made_changes here - only set it if we actually fix the fields below
        else:
            instr_obj = instructions if isinstance(instructions, dict) else {}
        
        instr_changed = False
        
        # Check if success_criteria is empty
        success_criteria = instr_obj.get('success_criteria', '')
        if not success_criteria or success_criteria.strip() == '':
            user_prompt = instr_obj.get('user_prompt', '')
            
            if user_prompt:
                # Try to find matching verification in CSV
                verification, found = find_verification_for_prompt(user_prompt, csv_mapping)
                
                if found and verification:
                    instr_obj['success_criteria'] = verification
                    stats['changes'].append('success_criteria: matched prompt in CSV')
                    instr_changed = True
                else:
                    instr_obj['success_criteria'] = ''
                    stats['changes'].append('success_criteria: no CSV match, set to empty string')
                    stats['warnings'].append('No CSV match found for user_prompt')
                    instr_changed = True
            else:
                instr_obj['success_criteria'] = ''
                stats['changes'].append('success_criteria: set to empty string (no user_prompt)')
                instr_changed = True
        
        # Only update instructions if we changed it
        if instr_changed:
            task_data['instructions'] = json.dumps(instr_obj, ensure_ascii=False)
            made_changes = True
        
        # Update environment_type field to "mcp" if empty or not "mcp"
        current_env_type = task_data.get('environment_type', '').strip()
        if not current_env_type or current_env_type != FIXED_ENVIRONMENT_TYPE_FIELD:
            task_data['environment_type'] = FIXED_ENVIRONMENT_TYPE_FIELD
            stats['changes'].append(f'environment_type: set to "{FIXED_ENVIRONMENT_TYPE_FIELD}"')
            made_changes = True
        
        # Update trace_id field to match task id if empty
        task_id = task_data.get('id', '')
        current_trace_id = task_data.get('trace_id', '').strip()
        if not current_trace_id and task_id:
            task_data['trace_id'] = task_id
            stats['changes'].append(f'trace_id: set to "{task_id}"')
            made_changes = True

        # Update env_version if missing or empty
        # env_version = task_data.get('env_version', '')
        # if not isinstance(env_version, str) or not env_version.strip():
        #     task_data['env_version'] = FIXED_ENV_VERSION
        #     stats['changes'].append(f'env_version: set to "{FIXED_ENV_VERSION}"')
        #     made_changes = True
        
        # Only write if we made actual changes
        if made_changes:
            stats['updated'] = True
            
            if not dry_run:
                # Create backup if requested
                if backup:
                    backup_path = task_path.with_suffix('.json.backup')
                    with open(backup_path, 'w', encoding='utf-8') as f:
                        # Write original data to backup
                        with open(task_path, 'r', encoding='utf-8') as orig:
                            f.write(orig.read())
                
                # Write updated task
                new_data = json.dumps(task_data, indent=2, ensure_ascii=False)
                with open(task_path, 'w', encoding='utf-8') as f:
                    f.write(new_data)
        
        return stats
    
    except Exception as e:
        logger.error(f"Error processing {task_path.name}: {e}")
        stats['warnings'].append(f'Error: {e}')
        return stats


def main():
    parser = argparse.ArgumentParser(
        description='Update Notion task JSON files with missing fields'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show changes without modifying files'
    )
    parser.add_argument(
        '--backup',
        action='store_true',
        help='Create .backup files before modifying'
    )
    parser.add_argument(
        '--csv',
        type=Path,
        default=Path('scripts/Notion Tasks - Sheet1.csv'),
        help='Path to CSV file (default: ./scripts/Notion Tasks - Sheet1.csv)'
    )
    parser.add_argument(
        '--tasks-dir',
        type=Path,
        default=Path('dojo-bench-customer-colossus/tasks/notion-v2'),
        help='Path to tasks directory (default: ./dojo-bench-customer-colossus/tasks/notion-v2)'
    )
    
    args = parser.parse_args()
    
    # Validate paths
    if not args.csv.exists():
        logger.error(f"CSV file not found: {args.csv}")
        return 1
    
    if not args.tasks_dir.exists():
        logger.error(f"Tasks directory not found: {args.tasks_dir}")
        return 1
    
    # Load CSV mapping
    logger.info("Processing Notion tasks...")
    csv_mapping = load_csv_mapping(args.csv)
    
    if not csv_mapping:
        logger.error("No mappings loaded from CSV. Exiting.")
        return 1
    
    # Find all task files
    task_files = sorted(args.tasks_dir.glob('*.json'))
    
    if not task_files:
        logger.warning(f"No task files found in {args.tasks_dir}")
        return 0
    
    logger.info(f"\nProcessing {len(task_files)} task files...")
    if args.dry_run:
        logger.info("[DRY RUN MODE - No files will be modified]\n")
    
    # Process each task file
    total_processed = 0
    total_updated = 0
    total_no_match = 0
    
    for task_file in task_files:
        stats = update_task_file(task_file, csv_mapping, args.dry_run, args.backup)
        total_processed += 1
        
        if stats['updated']:
            total_updated += 1
            prefix = "[DRY RUN] Would update:" if args.dry_run else "Updated:"
            logger.info(f"{prefix} {task_file.name}")
            
            for change in stats['changes']:
                logger.info(f"  - {change}")
            
            if stats['warnings']:
                for warning in stats['warnings']:
                    logger.info(f"  ⚠️  {warning}")
                    if 'No CSV match' in warning:
                        total_no_match += 1
            
            logger.info("")
    
    # Print summary
    logger.info("=" * 80)
    logger.info("Summary:")
    logger.info(f"  Total tasks processed: {total_processed}")
    logger.info(f"  Tasks with changes: {total_updated}")
    logger.info(f"  Tasks already complete: {total_processed - total_updated}")
    logger.info(f"  Tasks without CSV match: {total_no_match}")
    
    if args.dry_run:
        logger.info("\nNo files were modified (dry-run mode)")
    
    return 0


if __name__ == '__main__':
    exit(main())
