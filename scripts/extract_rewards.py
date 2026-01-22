#!/usr/bin/env python3
"""
Extract reward functions from a source file based on tasks listed in a CSV file.

This script:
1. Reads task IDs from a CSV file
2. Loads each task JSON file to extract reward_function names
3. Parses the source reward file using AST to extract helper functions and matched reward functions
4. Generates an output file with the extracted functions

Usage:
    python extract_rewards.py <csv_file> <source_file> <output_file> <tasks_dir>
    
Example:
    python extract_rewards.py dzaka-traces.csv \\
        dojo-bench-customer-colossus/rewards/notion_v2.py \\
        dojo-bench-customer-colossus/rewards/dzaka_notion_v2.py \\
        dojo-bench-customer-colossus/tasks/notion-v2
"""

import argparse
import ast
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Set, Dict, Any


def read_task_ids_from_csv(csv_path: str) -> List[str]:
    """Read task IDs from the CSV file."""
    task_ids = []
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0].strip():
                task_ids.append(row[0].strip())
    return task_ids


def get_reward_function_names(task_ids: List[str], tasks_dir: str) -> tuple[Dict[str, str], List[str]]:
    """
    For each task ID, load the JSON file and extract the reward_function field.
    Returns a dict mapping reward function names to task IDs and a list of warnings.
    """
    reward_functions = {}  # Maps function name -> task_id
    warnings = []
    
    for task_id in task_ids:
        json_path = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(json_path):
            warnings.append(f"Warning: Task file not found: {json_path}")
            continue
        
        try:
            with open(json_path, 'r') as f:
                task_data = json.load(f)
            
            reward_function = task_data.get('reward_function')
            if reward_function:
                reward_functions[reward_function] = task_id
            else:
                warnings.append(f"Warning: Task {task_id} has no reward_function field")
        except json.JSONDecodeError as e:
            warnings.append(f"Warning: Failed to parse JSON for task {task_id}: {e}")
        except Exception as e:
            warnings.append(f"Warning: Error processing task {task_id}: {e}")
    
    return reward_functions, warnings


def extract_functions_from_source(source_path: str, reward_function_map: Dict[str, str]) -> tuple[str, List[str], List[tuple[str, str]], str]:
    """
    Parse the Python source file using AST and extract:
    - All imports
    - All helper functions (functions starting with _)
    - Reward functions that match the given names (with their task IDs)
    - Module-level docstring if present
    
    Returns: (imports_code, helper_functions_code, reward_functions_with_tasks, module_docstring)
    where reward_functions_with_tasks is a list of (task_id, function_code) tuples
    """
    with open(source_path, 'r') as f:
        source_code = f.read()
    
    tree = ast.parse(source_code)
    
    # Extract module docstring
    module_docstring = ast.get_docstring(tree)
    
    # Extract imports
    import_lines = []
    helper_function_lines = []
    reward_function_tuples = []  # List of (task_id, function_code)
    
    # Track line numbers for each top-level node
    lines = source_code.split('\n')
    
    for node in tree.body:
        # Handle imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start_line = node.lineno - 1
            end_line = node.end_lineno if node.end_lineno else start_line + 1
            import_lines.append('\n'.join(lines[start_line:end_line]))
        
        # Handle function definitions
        elif isinstance(node, ast.FunctionDef):
            func_name = node.name
            start_line = node.lineno - 1
            end_line = node.end_lineno if node.end_lineno else start_line + 1
            func_code = '\n'.join(lines[start_line:end_line])
            
            # Check if it's a reward function we want
            if func_name in reward_function_map:
                task_id = reward_function_map[func_name]
                reward_function_tuples.append((task_id, func_code))
            # Helper functions (start with _ but NOT _validate*)
            # Exclude all _validate* functions as they are reward functions, not helpers
            elif func_name.startswith('_') and not func_name.startswith('_validate'):
                helper_function_lines.append(func_code)
    
    imports_code = '\n'.join(import_lines)
    
    return imports_code, helper_function_lines, reward_function_tuples, module_docstring


def generate_output_file(output_path: str, imports: str, helper_functions: List[str], 
                         reward_functions_with_tasks: List[tuple[str, str]], original_docstring: str = None,
                         csv_file: str = None, source_file: str = None):
    """Generate the output Python file with extracted functions."""
    with open(output_path, 'w') as f:
        # Write header comment
        f.write('"""\n')
        f.write('Extracted reward functions\n')
        f.write(f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        if source_file:
            f.write(f'Source: {source_file}\n')
        if csv_file:
            f.write(f'Task list: {csv_file}\n')
        f.write(f'Total helper functions: {len(helper_functions)}\n')
        f.write(f'Total reward functions: {len(reward_functions_with_tasks)}\n')
        f.write('"""\n\n')
        
        # Write original module docstring if present
        if original_docstring:
            f.write('"""\n')
            f.write(original_docstring)
            f.write('\n"""\n\n')
        
        # Write imports
        f.write(imports)
        f.write('\n\n')
        
        # Write helper functions
        f.write('# Helper Functions\n')
        f.write('# ' + '=' * 78 + '\n\n')
        for func in helper_functions:
            f.write(func)
            f.write('\n\n')
        
        # Write reward functions with task ID comments
        f.write('\n')
        f.write('# Reward Functions\n')
        f.write('# ' + '=' * 78 + '\n\n')
        
        # Extract function names for registry
        function_names = []
        for task_id, func_code in reward_functions_with_tasks:
            # Add comment flag with task name
            f.write('# ' + '-' * 77 + '\n')
            f.write(f'# {task_id}\n')
            f.write('# ' + '-' * 77 + '\n')
            f.write(func_code)
            f.write('\n\n')
            
            # Extract function name from code
            lines = func_code.split('\n')
            for line in lines:
                if line.strip().startswith('def '):
                    func_name = line.split('def ')[1].split('(')[0].strip()
                    function_names.append((task_id, func_name))
                    break
        
        # Write registry
        f.write('\n')
        f.write('# Task Registry\n')
        f.write('# ' + '=' * 78 + '\n')
        f.write('# Maps task IDs to their reward validation functions\n\n')
        f.write('TASK_REGISTRY: Dict[str, Callable[[Backend, Dict[str, Any]], Tuple[float, str]]] = {\n')
        for _, func_name in function_names:
            f.write(f'    "{func_name}": {func_name},\n')
        f.write('}\n')


def main():
    parser = argparse.ArgumentParser(
        description='Extract reward functions from a source file based on tasks in a CSV file.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract dzaka traces
  python extract_rewards.py dzaka-traces.csv \\
      dojo-bench-customer-colossus/rewards/notion_v2.py \\
      dojo-bench-customer-colossus/rewards/dzaka_notion_v2.py \\
      dojo-bench-customer-colossus/tasks/notion-v2

  # Extract weibo traces
  python extract_rewards.py weibo-traces.csv \\
      dojo-bench-customer-colossus/rewards/weibo_v2.py \\
      dojo-bench-customer-colossus/rewards/my_weibo_v2.py \\
      dojo-bench-customer-colossus/tasks/weibo-v2
        """
    )
    
    parser.add_argument('csv_file', help='Path to CSV file containing task IDs (one per line)')
    parser.add_argument('source_file', help='Path to source Python file with reward functions')
    parser.add_argument('output_file', help='Path to output Python file to generate')
    parser.add_argument('tasks_dir', help='Directory containing task JSON files')
    
    args = parser.parse_args()
    
    # Convert to absolute paths relative to workspace
    script_dir = Path(__file__).parent
    workspace_dir = script_dir.parent
    
    csv_path = Path(args.csv_file)
    if not csv_path.is_absolute():
        csv_path = workspace_dir / csv_path
    
    source_path = Path(args.source_file)
    if not source_path.is_absolute():
        source_path = workspace_dir / source_path
    
    output_path = Path(args.output_file)
    if not output_path.is_absolute():
        output_path = workspace_dir / output_path
    
    tasks_dir = Path(args.tasks_dir)
    if not tasks_dir.is_absolute():
        tasks_dir = workspace_dir / tasks_dir
    
    # Validate inputs
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    
    if not source_path.exists():
        print(f"Error: Source file not found: {source_path}", file=sys.stderr)
        sys.exit(1)
    
    if not tasks_dir.exists():
        print(f"Error: Tasks directory not found: {tasks_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Reading task IDs from: {csv_path}")
    task_ids = read_task_ids_from_csv(str(csv_path))
    print(f"Found {len(task_ids)} task IDs in CSV")
    
    print(f"\nExtracting reward function names from task JSON files...")
    reward_function_map, warnings = get_reward_function_names(task_ids, str(tasks_dir))
    print(f"Found {len(reward_function_map)} unique reward functions")
    
    if warnings:
        print(f"\n{len(warnings)} warnings encountered:")
        for warning in warnings:
            print(f"  {warning}")
    
    print(f"\nParsing source file: {source_path}")
    imports, helper_functions, reward_functions_with_tasks, module_docstring = extract_functions_from_source(
        str(source_path), reward_function_map
    )
    
    print(f"Extracted {len(helper_functions)} helper functions")
    print(f"Extracted {len(reward_functions_with_tasks)} reward functions")
    
    print(f"\nGenerating output file: {output_path}")
    generate_output_file(
        str(output_path), 
        imports, 
        helper_functions, 
        reward_functions_with_tasks,
        module_docstring,
        str(csv_path.relative_to(workspace_dir) if csv_path.is_relative_to(workspace_dir) else csv_path),
        str(source_path.relative_to(workspace_dir) if source_path.is_relative_to(workspace_dir) else source_path)
    )
    
    print(f"\n✓ Successfully generated {output_path}")
    print(f"\nSummary:")
    print(f"  - Task IDs processed: {len(task_ids)}")
    print(f"  - Reward functions found: {len(reward_function_map)}")
    print(f"  - Helper functions: {len(helper_functions)}")
    print(f"  - Reward functions written: {len(reward_functions_with_tasks)}")
    print(f"  - Warnings: {len(warnings)}")


if __name__ == '__main__':
    main()
