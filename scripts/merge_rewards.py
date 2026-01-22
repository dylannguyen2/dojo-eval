#!/usr/bin/env python3
"""
Merge reward functions from one file to another.

This script copies functions from a source reward file to a target reward file:
- Reward functions: Overwrites duplicates, adds new ones at bottom
- Helper functions: Only adds new ones (skips duplicates)
- Registry: Automatically updates with new/overwritten functions

Usage:
    python merge_rewards.py <source_file> <target_file>
    
Example:
    python merge_rewards.py \\
        dojo-bench-customer-colossus/rewards/dzaka_notion_v2.py \\
        dojo-bench-customer-colossus/rewards/notion_v2.py
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Set, Optional


def _is_backend_annotation(annotation: Optional[ast.AST]) -> bool:
    """
    Return True if `annotation` looks like `Backend` (either `Backend` or `x.Backend`).
    """
    if annotation is None:
        return False
    if isinstance(annotation, ast.Name):
        return annotation.id == "Backend"
    if isinstance(annotation, ast.Attribute):
        return annotation.attr == "Backend"
    return False


def _is_name_or_attr(annotation: ast.AST, allowed: Set[str]) -> bool:
    if isinstance(annotation, ast.Name):
        return annotation.id in allowed
    if isinstance(annotation, ast.Attribute):
        return annotation.attr in allowed
    return False


def _subscript_args(annotation: ast.Subscript) -> List[ast.AST]:
    """
    Normalize subscription args:
    - `Dict[str, Any]` -> [str, Any]
    - `dict[str, Any]` -> [str, Any]
    """
    slc = annotation.slice
    if isinstance(slc, ast.Tuple):
        return list(slc.elts)
    return [slc]


def _is_dict_str_any(annotation: Optional[ast.AST]) -> bool:
    """
    Return True if `annotation` looks like `Dict[str, Any]` / `dict[str, Any]`
    (also accepts `typing.Dict[...]` or `typing.Any` via Attribute nodes).
    """
    if annotation is None:
        return False
    if not isinstance(annotation, ast.Subscript):
        return False
    if not _is_name_or_attr(annotation.value, {"Dict", "dict"}):
        return False

    args = _subscript_args(annotation)
    if len(args) != 2:
        return False

    key_t, val_t = args
    if not _is_name_or_attr(key_t, {"str"}):
        return False
    if not _is_name_or_attr(val_t, {"Any"}):
        return False
    return True


def _is_reward_function_signature(node: ast.FunctionDef) -> bool:
    """
    Reward functions in this repo are identified by signature, not name:
    - Standard: `(backend: Backend, inputs: Dict[str, Any]) -> ...`
    - Hybrid/Dylan: `(backend: Backend, frontend_final_state: Dict[str, Any], final_answer: str) -> ...`
    """
    args = node.args
    # No *args/**kwargs/kw-only/pos-only allowed
    if args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg:
        return False
    
    # Check for 2-arg signature (standard)
    if len(args.args) == 2:
        backend_arg, inputs_arg = args.args
        return _is_backend_annotation(backend_arg.annotation) and _is_dict_str_any(inputs_arg.annotation)
    
    # Check for 3-arg signature (hybrid/Dylan functions)
    if len(args.args) == 3:
        backend_arg, inputs_arg, final_arg = args.args
        # Must be: Backend, Dict[str, Any], str with param name "final_answer"
        if not _is_backend_annotation(backend_arg.annotation):
            return False
        if not _is_dict_str_any(inputs_arg.annotation):
            return False
        # Check third arg is str type and named "final_answer"
        if final_arg.arg != "final_answer":
            return False
        if final_arg.annotation and _is_name_or_attr(final_arg.annotation, {"str"}):
            return True
    
    return False


def categorize_function(node: ast.FunctionDef) -> str:
    """
    Categorize a top-level function.

    Important: do NOT treat all `_validate*` as rewards; some `_validate_*` are helpers.
    We only treat a `_validate*` function as a reward if it matches the canonical signature:
    `(backend: Backend, inputs: Dict[str, Any])`.
    """
    func_name = node.name
    if func_name.startswith("_validate") and _is_reward_function_signature(node):
        return "reward"
    if func_name.startswith("_"):
        return "helper"
    return "other"


def parse_reward_file(file_path: str) -> Dict:
    """
    Parse a reward file and extract all components.
    
    Returns dict with:
    - imports: list of import code strings
    - module_docstring: module-level docstring
    - helper_functions: dict of {name: code}
    - reward_functions: dict of {name: code}
    - registry: dict of {key: value} or None
    - source_code: original source code
    """
    with open(file_path, 'r') as f:
        source_code = f.read()
    
    tree = ast.parse(source_code)
    lines = source_code.split('\n')
    
    result = {
        'imports': [],
        'module_docstring': ast.get_docstring(tree),
        # Module-level statements that are not imports / functions / registry, preserved as-is
        # (e.g. logger initialization, LIMIT constants, etc.)
        'preamble': [],
        'helper_functions': {},
        'reward_functions': {},
        'registry': None,
        'registry_name': None,
        'source_code': source_code
    }
    
    # Extract imports
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start_line = node.lineno - 1
            end_line = node.end_lineno if node.end_lineno else start_line + 1
            import_code = '\n'.join(lines[start_line:end_line])
            result['imports'].append(import_code)
    
    # Extract functions
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            func_name = node.name
            start_line = node.lineno - 1
            end_line = node.end_lineno if node.end_lineno else start_line + 1
            func_code = '\n'.join(lines[start_line:end_line])
            
            category = categorize_function(node)
            if category == 'reward':
                result['reward_functions'][func_name] = func_code
            elif category == 'helper':
                result['helper_functions'][func_name] = func_code
    
    # Extract registry
    registry_name, registry = extract_registry(tree, lines)
    if registry:
        result['registry'] = registry
        result['registry_name'] = registry_name

    # Extract module-level preamble statements (e.g. logger, constants), preserving order.
    # Skip:
    # - module docstring
    # - imports
    # - function defs
    # - registry assignment
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
            continue

        # Skip module docstring expression
        if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
            if isinstance(node.value.value, str):
                continue

        # Skip registry assignment itself
        if registry_name:
            if isinstance(node, ast.Assign):
                if any(isinstance(t, ast.Name) and t.id == registry_name for t in node.targets):
                    continue
            if isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == registry_name:
                    continue

        start_line = getattr(node, "lineno", None)
        end_line = getattr(node, "end_lineno", None)
        if not start_line or not end_line:
            continue

        stmt_code = '\n'.join(lines[start_line - 1:end_line])
        if stmt_code.strip():
            result['preamble'].append(stmt_code)
    
    return result


def _registry_var_name_matches(name: str) -> bool:
    upper = name.upper()
    # Common patterns in this repo:
    # - REWARD_FUNCTIONS_NOTION_V2
    # - REWARD_FUNCTIONS_NOTION_ANTHONY_V2
    # - ...REGISTRY...
    return upper.startswith("REWARD_FUNCTIONS_") or ("REGISTRY" in upper)


def extract_registry(tree: ast.Module, lines: List[str]) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
    """Extract a registry dict assignment from AST, returning (registry_name, registry_dict)."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and _registry_var_name_matches(target.id):
                    if isinstance(node.value, ast.Dict):
                        registry = {}
                        for key, value in zip(node.value.keys, node.value.values):
                            if isinstance(key, ast.Constant) and isinstance(value, ast.Name):
                                registry[key.value] = value.id
                        return target.id, registry
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and _registry_var_name_matches(node.target.id):
                if isinstance(node.value, ast.Dict):
                    registry = {}
                    for key, value in zip(node.value.keys, node.value.values):
                        if isinstance(key, ast.Constant) and isinstance(value, ast.Name):
                            registry[key.value] = value.id
                    return node.target.id, registry
    return None, None


def extract_comment_flags(source_code: str) -> Dict[str, str]:
    """
    Extract leading top-level comment blocks that appear immediately before a function.
    Returns dict of {function_name: comment_block}

    Why: this script regenerates the target file. If we don't explicitly preserve
    these comment blocks (e.g. "Task 8: ...", separator lines, etc), they will be
    lost even if the function body itself is kept/merged.
    """
    lines = source_code.split('\n')
    comment_blocks: Dict[str, str] = {}

    for i, line in enumerate(lines):
        # Only consider top-level defs (no leading indentation)
        if line.startswith(' ') or line.startswith('\t'):
            continue
        if not line.startswith('def '):
            continue

        func_name = line.split('def ', 1)[1].split('(', 1)[0].strip()
        if not func_name:
            continue

        # Walk upwards collecting contiguous comment lines; allow blank lines within
        # the comment header, but stop at first real code line.
        collected: List[str] = []
        k = i - 1
        seen_comment = False
        while k >= 0:
            prev = lines[k]
            if not prev.strip():
                # keep blank lines only if we've already seen a comment line
                if seen_comment:
                    collected.append(prev)
                k -= 1
                continue
            if prev.lstrip().startswith('#'):
                seen_comment = True
                collected.append(prev)
                k -= 1
                continue
            break

        if seen_comment:
            comment_blocks[func_name] = '\n'.join(reversed(collected)).rstrip()

    return comment_blocks


def merge_functions(source: Dict, target: Dict) -> Tuple[Dict, Dict]:
    """
    Merge functions from source to target.
    
    Returns (merged_data, statistics)
    """
    stats = {
        'reward_new': 0,
        'reward_overwritten': 0,
        'helper_added': 0,
        'helper_skipped': 0,
        'reward_new_list': [],
        'reward_overwritten_list': [],
        'helper_added_list': [],
        'helper_skipped_list': []
    }
    
    # Extract comment flags from source
    source_comment_flags = extract_comment_flags(source['source_code'])
    target_comment_flags = extract_comment_flags(target['source_code'])
    
    # Merge helper functions (only add new ones)
    merged_helpers = dict(target['helper_functions'])
    for name, code in source['helper_functions'].items():
        if name in merged_helpers:
            stats['helper_skipped'] += 1
            stats['helper_skipped_list'].append(name)
        else:
            merged_helpers[name] = code
            stats['helper_added'] += 1
            stats['helper_added_list'].append(name)
    
    # Merge reward functions (replace in-place to avoid large diffs)
    merged_rewards = {}
    merged_rewards_flags = {}
    for name, code in target['reward_functions'].items():
        if name in source['reward_functions']:
            stats['reward_overwritten'] += 1
            stats['reward_overwritten_list'].append(name)
            merged_rewards[name] = source['reward_functions'][name]
            if name in source_comment_flags:
                merged_rewards_flags[name] = source_comment_flags[name]
            elif name in target_comment_flags:
                merged_rewards_flags[name] = target_comment_flags[name]
        else:
            merged_rewards[name] = code
            if name in target_comment_flags:
                merged_rewards_flags[name] = target_comment_flags[name]

    # Add any new reward functions from source at the end (rare)
    for name, code in source['reward_functions'].items():
        if name not in merged_rewards:
            stats['reward_new'] += 1
            stats['reward_new_list'].append(name)
            merged_rewards[name] = code
            if name in source_comment_flags:
                merged_rewards_flags[name] = source_comment_flags[name]
    
    # Merge registry with smart key preservation
    # Priority: 1) Source registry key, 2) Target registry key, 3) Function name
    source_registry = source.get('registry', {}) or {}
    target_registry = target.get('registry', {}) or {}
    
    # Create reverse lookup: function_name -> registry_key
    source_func_to_key = {v: k for k, v in source_registry.items()}
    target_func_to_key = {v: k for k, v in target_registry.items()}
    
    merged_registry = {}

    # Preserve target registry order when possible (important for small diffs)
    if target_registry:
        for key, func_name in target_registry.items():
            if func_name in merged_rewards:
                merged_registry[key] = func_name

    # Ensure every merged reward function is present
    for func_name in merged_rewards.keys():
        if func_name in source_func_to_key:
            key = source_func_to_key[func_name]
        elif func_name in target_func_to_key:
            key = target_func_to_key[func_name]
        else:
            key = func_name
        merged_registry.setdefault(key, func_name)
    
    result = {
        'imports': target['imports'],  # Keep target's imports
        'module_docstring': target['module_docstring'],
        'preamble': target.get('preamble', []),  # Keep target's module-level statements
        'helper_functions': merged_helpers,
        'reward_functions': merged_rewards,
        'reward_functions_flags': merged_rewards_flags,
        'registry': merged_registry,
        # Preserve target registry variable name if present (e.g. REWARD_FUNCTIONS_NOTION_V2)
        'registry_name': target.get('registry_name') or source.get('registry_name')
    }
    
    return result, stats


def generate_output(merged_data: Dict, output_path: str):
    """Generate the merged output file."""
    with open(output_path, 'w') as f:
        # Write module docstring if present
        if merged_data['module_docstring']:
            f.write('"""\n')
            f.write(merged_data['module_docstring'])
            f.write('\n"""\n\n')
        
        # Write imports
        if merged_data['imports']:
            f.write('\n'.join(merged_data['imports']))
            f.write('\n\n')

        # Write preserved module-level statements (logger, constants, etc.)
        preamble = merged_data.get('preamble', [])
        if preamble:
            f.write('\n'.join(preamble))
            f.write('\n\n')
        
        # Write helper functions
        f.write('# Helper Functions\n')
        f.write('# ' + '=' * 78 + '\n\n')
        for name in merged_data['helper_functions'].keys():
            f.write(merged_data['helper_functions'][name])
            f.write('\n\n')
        
        # Write existing reward functions (not being overwritten)
        f.write('\n# Reward Functions\n')
        f.write('# ' + '=' * 78 + '\n\n')
        for name in merged_data['reward_functions'].keys():
            # Write comment flag if it exists
            if name in merged_data.get('reward_functions_flags', {}):
                f.write(merged_data['reward_functions_flags'][name])
                f.write('\n')
            f.write(merged_data['reward_functions'][name])
            f.write('\n\n')
        
        # Write registry
        if merged_data['registry']:
            f.write('\n# Task Registry\n')
            f.write('# ' + '=' * 78 + '\n')
            f.write('# Maps function names to themselves for easy lookup\n\n')
            registry_name = merged_data.get('registry_name') or 'REWARD_FUNCTIONS_REGISTRY'
            f.write(f'{registry_name}: Dict[str, Callable[[Backend, Dict[str, Any]], Tuple[float, str]]] = {{\n')
            for name in merged_data['registry'].keys():
                value = merged_data['registry'][name]
                f.write(f'    "{name}": {value},\n')
            f.write('}\n')


def main():
    parser = argparse.ArgumentParser(
        description='Merge reward functions from source file to target file.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python merge_rewards.py \\
      dojo-bench-customer-colossus/rewards/dzaka_notion_v2.py \\
      dojo-bench-customer-colossus/rewards/notion_v2.py
        """
    )
    
    parser.add_argument('source_file', help='Source file to copy functions from')
    parser.add_argument('target_file', help='Target file to merge functions into')
    parser.add_argument('--backup', action='store_true', help='Create backup of target file')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be merged without making changes')
    
    args = parser.parse_args()
    
    # Convert to absolute paths
    script_dir = Path(__file__).parent
    workspace_dir = script_dir.parent
    
    source_path = Path(args.source_file)
    if not source_path.is_absolute():
        source_path = workspace_dir / source_path
    
    target_path = Path(args.target_file)
    if not target_path.is_absolute():
        target_path = workspace_dir / target_path
    
    # Validate inputs
    if not source_path.exists():
        print(f"Error: Source file not found: {source_path}", file=sys.stderr)
        sys.exit(1)
    
    if not target_path.exists():
        print(f"Error: Target file not found: {target_path}", file=sys.stderr)
        sys.exit(1)
    
    # Create backup if requested
    if args.backup:
        # Create backup with .backup.py extension (not .py.backup)
        backup_path = str(target_path).replace('.py', '.backup.py')
        print(f"Creating backup: {backup_path}")
        with open(target_path, 'r') as src, open(backup_path, 'w') as dst:
            dst.write(src.read())
    
    print(f"Parsing source file: {source_path}")
    source_data = parse_reward_file(str(source_path))
    
    print(f"Parsing target file: {target_path}")
    target_data = parse_reward_file(str(target_path))
    
    print("\nMerging functions...")
    merged_data, stats = merge_functions(source_data, target_data)
    
    if args.dry_run:
        print("\n" + "="*70)
        print("DRY RUN - No changes will be made")
        print("="*70)
        
        # Show what would be added/overwritten
        print("\n📝 Changes Preview:")
        print("\nReward Functions to Add/Overwrite:")
        for name in stats['reward_overwritten_list']:
            print(f"  [OVERWRITE] {name}")
        for name in stats['reward_new_list']:
            print(f"  [NEW] {name}")
        
        print("\nHelper Functions to Add:")
        new_helpers = [name for name in source_data['helper_functions'].keys() 
                      if name not in target_data['helper_functions']]
        for name in new_helpers:
            print(f"  [NEW] {name}")
        
        print("\nHelper Functions to Skip:")
        skipped_helpers = [name for name in source_data['helper_functions'].keys() 
                          if name in target_data['helper_functions']]
        for name in skipped_helpers:
            print(f"  [SKIP] {name}")
        
    else:
        print(f"Generating output: {target_path}")
        generate_output(merged_data, str(target_path))
        
        # Verify syntax
        try:
            with open(target_path, 'r') as f:
                compile(f.read(), str(target_path), 'exec')
            print("✓ Output file syntax is valid")
        except SyntaxError as e:
            print(f"⚠ Warning: Output file has syntax errors: {e}", file=sys.stderr)
    
    # Print statistics
    print("\n" + "=" * 70)
    print("Merge Complete!")
    print("=" * 70)
    print("\nReward Functions:")
    print(f"  - New: {stats['reward_new']}")
    print(f"  - Overwritten: {stats['reward_overwritten']}")
    total_rewards = len(merged_data['reward_functions'])
    print(f"  - Total in target: {total_rewards}")
    
    print("\nHelper Functions:")
    print(f"  - Added: {stats['helper_added']}")
    print(f"  - Skipped (already exist): {stats['helper_skipped']}")
    print(f"  - Total in target: {len(merged_data['helper_functions'])}")
    
    if merged_data['registry']:
        print(f"\nRegistry:")
        print(f"  - Total entries: {len(merged_data['registry'])}")
    
    print("=" * 70)
    
    # Generate detailed JSON output
    if not args.dry_run:
        output_json = {
            "summary": {
                "reward_functions": {
                    "new": stats['reward_new'],
                    "overwritten": stats['reward_overwritten'],
                    "total": len(merged_data['reward_functions'])
                },
                "helper_functions": {
                    "added": stats['helper_added'],
                    "skipped": stats['helper_skipped'],
                    "total": len(merged_data['helper_functions'])
                },
                "registry_entries": len(merged_data['registry']) if merged_data['registry'] else 0
            },
            "details": {
                "reward_functions_new": sorted(stats['reward_new_list']),
                "reward_functions_overwritten": sorted(stats['reward_overwritten_list']),
                "helper_functions_added": sorted(stats['helper_added_list']),
                "helper_functions_skipped": sorted(stats['helper_skipped_list'])
            },
            "source_file": str(source_path.relative_to(workspace_dir) if source_path.is_relative_to(workspace_dir) else source_path),
            "target_file": str(target_path.relative_to(workspace_dir) if target_path.is_relative_to(workspace_dir) else target_path)
        }
        
        json_output_path = str(target_path).replace('.py', '_merge_result.json')
        with open(json_output_path, 'w') as f:
            json.dump(output_json, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {json_output_path}")
        print(f"   - {len(stats['reward_overwritten_list'])} functions overwritten")
        print(f"   - {len(stats['reward_new_list'])} functions added")
        print(f"   - {len(stats['helper_added_list'])} helpers added")
        print(f"   - {len(stats['helper_skipped_list'])} helpers skipped")


if __name__ == '__main__':
    main()
