#!/usr/bin/env python3
"""
Transform reward functions from Tuple[float, str] to TaskScore format.

This script converts validation functions to accumulate errors/successes.

Key behavior:
- ALL checks accumulate errors (no early returns)
- If code crashes due to None access, catch exception and return with collected errors
- At the end, return TaskScore with all accumulated errors/successes
"""

import re
import sys
from pathlib import Path


def error_to_success_message(error_msg: str) -> str:
    """Convert an error message to a success message."""
    success = error_msg

    # Order matters - more specific patterns first
    replacements = [
        # Specific phrase replacements (more specific first)
        (r'\bdoes not have\b', 'has'),
        (r'\bdo not have\b', 'have'),
        (r'\bis not found\b', 'is found'),
        (r'\bnot found\b', 'found'),
        (r'\bnot have\b', 'has'),
        (r'\bnot present\b', 'present'),
        (r'\bnot marked\b', 'marked'),
        (r'\bnot under\b', 'under'),
        (r'\bnot a child\b', 'a child'),
        (r'\bnot contain\b', 'contains'),
        (r'\bdoes not\b', ''),
        (r'\bdo not\b', ''),
        (r'\bis not\b', 'is'),
        (r'\bno\s+', ''),
        (r'\bnot\s+', ''),
        (r'\bmissing\b', 'has'),
        (r'\bMissing\b', 'Has'),
        (r'\bisn\'t\b', 'is'),
        (r'\baren\'t\b', 'are'),
        (r'\bwasn\'t\b', 'was'),
        (r'\bweren\'t\b', 'were'),
        (r'\bhasn\'t\b', 'has'),
        (r'\bhaven\'t\b', 'have'),
        (r'\bcan\'t\b', 'can'),
        (r'\bcannot\b', 'can'),
        (r'\bfailed\b', 'succeeded'),
        (r'\bFailed\b', 'Succeeded'),
        (r'\binvalid\b', 'valid'),
        (r'\bInvalid\b', 'Valid'),
        (r'\bwrong\b', 'correct'),
        (r'\bWrong\b', 'Correct'),
        (r'\bincorrect\b', 'correct'),
        (r'\bIncorrect\b', 'Correct'),
        # For "Expected X, found Y" patterns - keep the actual found value
        (r'Expected at least (\d+)([^,]*), found (.+)$', r'Found at least \1\2 (\3)'),
        (r'Expected (\d+)([^,]*), found (.+)$', r'Found \1\2 as expected'),
    ]

    for pattern, replacement in replacements:
        success = re.sub(pattern, replacement, success, flags=re.IGNORECASE)

    # Remove f-string variables like {var_name} from success messages
    # Keep the text before and after but remove the variable reference
    success = re.sub(r',?\s*found:?\s*\{[^}]+\}', '', success)  # Remove ", found: {var}" patterns
    success = re.sub(r':\s*\{[^}]+\}', '', success)  # Remove ": {var}" patterns
    success = re.sub(r'\(\{[^}]+\}\)', '', success)  # Remove "({var})" patterns
    success = re.sub(r'\{[^}]+\}', '', success)  # Remove any remaining {var} patterns

    # Clean up trailing ", found ''" or ", found" patterns
    success = re.sub(r",?\s*found:?\s*['\"]?['\"]?\s*$", '', success)
    success = re.sub(r",?\s*found\s+vs\s+expected\s*$", '', success)

    # Clean up "Expected , found" (empty expected) -> just remove it
    success = re.sub(r'\.\s*Expected\s*,\s*found\s*$', '', success)
    success = re.sub(r'Expected\s*,\s*found\s*$', '', success)
    success = re.sub(r'\.\s*Expected\s*$', '', success)  # Remove trailing ". Expected"

    # Clean up empty parentheses and quotes artifacts
    success = re.sub(r"\s*\(\s*\)", '', success)  # Remove empty ()
    success = re.sub(r"\s*''\s*", ' ', success)  # Remove empty ''
    success = re.sub(r'\s*""\s*', ' ', success)  # Remove empty ""

    # Clean up trailing punctuation artifacts
    success = re.sub(r'\s*,\s*$', '', success)
    success = re.sub(r'\s*:\s*$', '', success)

    # Clean up double spaces
    success = re.sub(r'\s+', ' ', success).strip()

    # Clean up grammar issues
    success = re.sub(r'\bdoes\s+$', '', success)
    success = re.sub(r'\bdo\s+$', '', success)

    return success


def create_task_score_return(indent: str, score: str = "0.0") -> str:
    """Create the TaskScore return statement with deduped lists."""
    return f"""{indent}return TaskScore(
{indent}    score={score},
{indent}    metadata=ScoreMetadata(
{indent}        success_accumulator=list(dict.fromkeys(checks_passed)),
{indent}        error_accumulator=list(dict.fromkeys(errors)),
{indent}    )
{indent})"""


def transform_function(func_text: str) -> str:
    """Transform a single function from Tuple[float, str] to TaskScore."""

    # Match both Tuple[float, str] (typing module) and tuple[float, str] (Python 3.9+)
    if not re.search(r'->\s*[Tt]uple\[float,\s*str\]', func_text):
        return func_text

    # Change return type annotation
    func_text = re.sub(
        r'->\s*[Tt]uple\[float,\s*str\]:',
        '-> TaskScore:',
        func_text
    )

    # Check if errors/checks_passed already exist (must be standalone variable, not part of another name)
    # Match both "errors = []" and "errors: list[str] = []" patterns
    has_errors = bool(re.search(r'\berrors\s*(?::\s*list\[str\])?\s*=\s*\[\]', func_text))
    has_checks = bool(re.search(r'\bchecks_passed\s*(?::\s*list\[str\])?\s*=\s*\[\]', func_text))

    # Find the position after the docstring to insert errors/checks_passed
    docstring_pattern = r'("""[\s\S]*?""")'
    docstring_match = re.search(docstring_pattern, func_text)

    insert_vars = ""
    if not has_errors:
        insert_vars += "    errors: list[str] = []\n"
    if not has_checks:
        insert_vars += "    checks_passed: list[str] = []\n"

    if insert_vars and docstring_match:
        end_pos = docstring_match.end()
        func_text = func_text[:end_pos] + "\n" + insert_vars + func_text[end_pos:]
    elif insert_vars:
        sig_match = re.search(r'\):\s*\n', func_text)
        if sig_match:
            end_pos = sig_match.end()
            func_text = func_text[:end_pos] + insert_vars + func_text[end_pos:]

    lines = func_text.split('\n')
    new_lines = []
    i = 0

    # Track function body start for try-except wrapping
    func_body_start = 0
    for idx, line in enumerate(lines):
        if re.match(r'^\s+errors:\s*list', line) or re.match(r'^\s+checks_passed:\s*list', line):
            func_body_start = idx + 1
        elif re.match(r'^\s+errors\s*=\s*\[\]', line) or re.match(r'^\s+checks_passed\s*=\s*\[\]', line):
            func_body_start = idx + 1

    while i < len(lines):
        line = lines[i]

        # Check for return 0.0, "error" pattern
        # Single line patterns - both with and without parentheses
        error_patterns = [
            r'^(\s*)return\s+0\.0,\s*f"([^"]*)"',
            r'^(\s*)return\s+0\.0,\s*f\'([^\']*)\'',
            r'^(\s*)return\s+0\.0,\s*"([^"]*)"',
            r'^(\s*)return\s+0\.0,\s*\'([^\']*)\'',
            # Parenthesized tuple returns: return (0.0, "msg")
            r'^(\s*)return\s+\(0\.0,\s*f"([^"]*)"\)',
            r'^(\s*)return\s+\(0\.0,\s*f\'([^\']*)\'\)',
            r'^(\s*)return\s+\(0\.0,\s*"([^"]*)"\)',
            r'^(\s*)return\s+\(0\.0,\s*\'([^\']*)\'\)',
        ]
        # Pattern for return 0.0, variable (where variable is an error message)
        # Also matches: return (0.0, "; ".join(errors)) style
        error_variable_pattern = r'^(\s*)return\s+\(?0\.0,\s*([a-z_][a-z0-9_]*(?:\s*\.\s*join\s*\([^)]+\))?)\s*\)?\s*$'
        # Pattern for return (0.0, "; ".join(errors)) - string literal join
        error_join_pattern = r'^(\s*)return\s+\(?0\.0,\s*["\'].*["\']\s*\.\s*join\s*\(\s*errors\s*\)\s*\)?\s*$'
        # Multiline pattern: return 0.0, (
        multiline_error_pattern = r'^(\s*)return\s+0\.0,\s*\(\s*$'

        # Check multiline error pattern first
        multiline_error_match = re.match(multiline_error_pattern, line)
        if multiline_error_match:
            indent = multiline_error_match.group(1)
            # Collect the multiline error message
            error_lines = []
            i += 1
            paren_depth = 1
            while i < len(lines) and paren_depth > 0:
                skip_line = lines[i]
                paren_depth += skip_line.count('(') - skip_line.count(')')
                if paren_depth > 0:  # Don't include the closing )
                    error_lines.append(skip_line.strip())
                i += 1

            # Create error message from the multiline content
            raw_content = ' '.join(error_lines)
            # Check if original was an f-string (contains f" or f')
            is_fstring = 'f"' in raw_content or "f'" in raw_content
            error_content = raw_content.replace('f"', '').replace('"', '').replace("f'", '').replace("'", '')
            # Use f-string if original had f-string or if there are {placeholders}
            if is_fstring or ('{' in error_content and '}' in error_content):
                error_append = f'{indent}errors.append(f"[X] {error_content}")'
            else:
                error_append = f'{indent}errors.append("[X] {error_content}")'

            # Calculate else indentation
            if len(indent) >= 4:
                else_indent = indent[:-4] if indent.endswith('    ') else indent[:-1]
            else:
                else_indent = ""

            # Check if next line already has checks_passed.append()
            next_line = lines[i] if i < len(lines) else ""
            has_existing_success = 'checks_passed.append(' in next_line

            # Check if we're inside an else: block
            start_idx = i - len(error_lines) - 1  # Index of the return 0.0, ( line
            inside_else_block = False
            for back_idx in range(start_idx - 1, max(0, start_idx - 30), -1):
                back_line = lines[back_idx].rstrip()
                if back_line.endswith('else:') and len(back_line) - len(back_line.lstrip()) < len(indent):
                    inside_else_block = True
                    break
                if back_line.strip() and not back_line.strip().startswith('#'):
                    if len(back_line) - len(back_line.lstrip()) <= len(indent) - 4:
                        break

            # Check if next non-empty line is elif (can't add else before elif)
            has_following_elif = False
            for fwd_idx in range(i, min(len(lines), i + 5)):
                fwd_line = lines[fwd_idx].strip()
                if fwd_line and not fwd_line.startswith('#'):
                    if fwd_line.startswith('elif '):
                        has_following_elif = True
                    break

            new_lines.append(error_append)

            if has_existing_success and not inside_else_block and not has_following_elif:
                # Wrap the existing checks_passed.append() in an else block
                new_lines.append(f'{else_indent}else:')
                existing_line = lines[i]
                existing_stripped = existing_line.strip()
                # Add [C] prefix if not present
                if '[C]' not in existing_stripped:
                    existing_stripped = existing_stripped.replace(
                        'checks_passed.append("',
                        'checks_passed.append("[C] '
                    ).replace(
                        "checks_passed.append('",
                        "checks_passed.append('[C] "
                    ).replace(
                        'checks_passed.append(f"',
                        'checks_passed.append(f"[C] '
                    ).replace(
                        "checks_passed.append(f'",
                        "checks_passed.append(f'[C] "
                    )
                new_lines.append(f'{indent}{existing_stripped}')
                i += 1  # Skip the original checks_passed.append line
            elif not has_existing_success and not inside_else_block and not has_following_elif:
                success_msg = error_to_success_message(error_content)
                # Use f-string if original had f-string or if there are {placeholders}
                if is_fstring or ('{' in success_msg and '}' in success_msg):
                    success_append = f'{indent}checks_passed.append(f"[C] {success_msg}")'
                else:
                    success_append = f'{indent}checks_passed.append("[C] {success_msg}")'
                new_lines.append(f'{else_indent}else:')
                new_lines.append(success_append)

            continue

        matched = False
        for pattern_idx, pattern in enumerate(error_patterns):
            match = re.match(pattern, line)
            if match:
                matched = True
                indent = match.group(1)
                error_msg = match.group(2)
                is_fstring = pattern_idx < 2

                # Check if we're inside an except block
                inside_except = False
                for back_idx in range(i - 1, max(0, i - 10), -1):
                    back_line = lines[back_idx].rstrip()
                    if re.match(r'^\s*except\s+', back_line):
                        inside_except = True
                        break
                    if back_line.strip() and not back_line.strip().startswith('#'):
                        # Hit non-empty, non-comment line that's not except
                        if not back_line.strip().startswith('errors.append'):
                            break

                # Create error append (NO early return - just accumulate)
                if is_fstring:
                    error_append = f'{indent}errors.append(f"[X] {error_msg}")'
                else:
                    error_append = f'{indent}errors.append("[X] {error_msg}")'

                # Calculate else indentation
                if len(indent) >= 4:
                    else_indent = indent[:-4] if indent.endswith('    ') else indent[:-1]
                else:
                    else_indent = ""

                # Check if next line already has checks_passed.append()
                # If so, don't add our own success message
                next_line = lines[i + 1] if i + 1 < len(lines) else ""
                has_existing_success = 'checks_passed.append(' in next_line

                # Check if we're inside an else: block by looking back for 'else:' at shallower indentation
                inside_else_block = False
                for back_idx in range(i - 1, max(0, i - 30), -1):
                    back_line = lines[back_idx].rstrip()
                    if back_line.endswith('else:') and len(back_line) - len(back_line.lstrip()) < len(indent):
                        inside_else_block = True
                        break
                    # Stop if we hit a line with code at same or shallower indentation
                    if back_line.strip() and not back_line.strip().startswith('#'):
                        if len(back_line) - len(back_line.lstrip()) <= len(indent) - 4:
                            break

                # Check if next non-empty line is elif at same/shallower indent (can't add else before elif)
                has_following_elif = False
                for fwd_idx in range(i + 1, min(len(lines), i + 5)):
                    fwd_line = lines[fwd_idx].strip()
                    if fwd_line and not fwd_line.startswith('#'):
                        if fwd_line.startswith('elif '):
                            has_following_elif = True
                        break

                new_lines.append(error_append)

                # If inside an except block, add return statement
                if inside_except:
                    return_stmt = create_task_score_return(indent, "0.0")
                    new_lines.append(return_stmt)
                    break  # Don't add else block for except handlers

                if has_existing_success and not inside_else_block and not has_following_elif:
                    # Wrap the existing checks_passed.append() in an else block
                    new_lines.append(f'{else_indent}else:')
                    # Modify the existing line to have proper indentation and [C] prefix
                    existing_line = lines[i + 1]
                    existing_stripped = existing_line.strip()
                    # Add [C] prefix if not present
                    if '[C]' not in existing_stripped:
                        existing_stripped = existing_stripped.replace(
                            'checks_passed.append("',
                            'checks_passed.append("[C] '
                        ).replace(
                            "checks_passed.append('",
                            "checks_passed.append('[C] "
                        ).replace(
                            'checks_passed.append(f"',
                            'checks_passed.append(f"[C] '
                        ).replace(
                            "checks_passed.append(f'",
                            "checks_passed.append(f'[C] "
                        )
                    new_lines.append(f'{indent}{existing_stripped}')
                    i += 1  # Skip the original checks_passed.append line
                elif not has_existing_success and not inside_else_block and not has_following_elif:
                    # Create success message
                    success_msg = error_to_success_message(error_msg)
                    if is_fstring:
                        success_append = f'{indent}checks_passed.append(f"[C] {success_msg}")'
                    else:
                        success_append = f'{indent}checks_passed.append("[C] {success_msg}")'

                    new_lines.append(f'{else_indent}else:')
                    new_lines.append(success_append)

                break

        if matched:
            i += 1
            continue

        # Check for return (0.0, "; ".join(errors)) - convert to TaskScore return
        error_join_match = re.match(error_join_pattern, line)
        if error_join_match:
            indent = error_join_match.group(1)
            # This is already accumulating errors, just return TaskScore
            task_score = create_task_score_return(indent, "0.0")
            new_lines.append(task_score)
            i += 1
            continue

        # Check for return 0.0, variable_name (error message in variable)
        error_var_match = re.match(error_variable_pattern, line)
        if error_var_match:
            indent = error_var_match.group(1)
            var_name = error_var_match.group(2)

            # Convert to errors.append with the variable
            error_append = f'{indent}errors.append(f"[X] {{{var_name}}}")'

            # Calculate else indentation
            if len(indent) >= 4:
                else_indent = indent[:-4] if indent.endswith('    ') else indent[:-1]
            else:
                else_indent = ""

            # Check if we're inside an else: block
            inside_else_block = False
            for back_idx in range(i - 1, max(0, i - 30), -1):
                back_line = lines[back_idx].rstrip()
                if back_line.endswith('else:') and len(back_line) - len(back_line.lstrip()) < len(indent):
                    inside_else_block = True
                    break
                if back_line.strip() and not back_line.strip().startswith('#'):
                    if len(back_line) - len(back_line.lstrip()) <= len(indent) - 4:
                        break

            # Check if next non-empty line is elif
            has_following_elif = False
            for fwd_idx in range(i + 1, min(len(lines), i + 5)):
                fwd_line = lines[fwd_idx].strip()
                if fwd_line and not fwd_line.startswith('#'):
                    if fwd_line.startswith('elif '):
                        has_following_elif = True
                    break

            new_lines.append(error_append)

            if not inside_else_block and not has_following_elif:
                # For variable errors, we don't know the success message, use generic
                success_append = f'{indent}checks_passed.append(f"[C] Check passed")'
                new_lines.append(f'{else_indent}else:')
                new_lines.append(success_append)

            i += 1
            continue

        # Check for success return (return 1.0, ...)
        # Single line: return 1.0, "message" or return (1.0, "message")
        # Multi line variant 1: return 1.0, (\n  f"..."\n  f"..."\n)
        # Multi line variant 2: return (\n    1.0,\n    f"..."\n)
        success_pattern = r'^(\s*)return\s+\(?1\.0,\s*(?:f?["\'].*["\']|[^)]*)\)?\s*$'
        multiline_success_pattern = r'^(\s*)return\s+1\.0,\s*\(\s*$'
        multiline_success_pattern_alt = r'^(\s*)return\s*\(\s*$'  # return ( with 1.0 on next line

        success_match = re.match(success_pattern, line)
        multiline_match = re.match(multiline_success_pattern, line)
        multiline_match_alt = re.match(multiline_success_pattern_alt, line)

        # Check if next line starts with 1.0 for the alt pattern
        if multiline_match_alt and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if not next_line.startswith('1.0,'):
                multiline_match_alt = None  # Not a success return

        if multiline_match or multiline_match_alt:
            # Skip the multiline return and all continuation lines until closing paren
            indent = (multiline_match or multiline_match_alt).group(1)
            task_score = create_task_score_return(indent, "1.0 if len(errors) == 0 else 0.0")
            new_lines.append(task_score)
            i += 1
            # Skip lines until we find the closing )
            paren_depth = 1
            while i < len(lines) and paren_depth > 0:
                skip_line = lines[i]
                paren_depth += skip_line.count('(') - skip_line.count(')')
                i += 1
            continue
        elif success_match:
            indent = success_match.group(1)
            task_score = create_task_score_return(indent, "1.0 if len(errors) == 0 else 0.0")
            new_lines.append(task_score)
            i += 1
            continue

        new_lines.append(line)
        i += 1

    # Now wrap the function body in try-except
    # Find where the function body starts (after docstring and variable declarations)
    result = wrap_in_try_except(new_lines)

    # Post-processing: add [C] prefix to checks_passed.append() lines without it
    # These are leftover original lines that need to be standardized
    final_result = []
    for line in result:
        stripped = line.strip()
        if stripped.startswith('checks_passed.append(') and '[C]' not in stripped:
            # Add [C] prefix to the message
            line = line.replace(
                'checks_passed.append("',
                'checks_passed.append("[C] '
            ).replace(
                "checks_passed.append('",
                "checks_passed.append('[C] "
            ).replace(
                'checks_passed.append(f"',
                'checks_passed.append(f"[C] '
            ).replace(
                "checks_passed.append(f'",
                "checks_passed.append(f'[C] "
            )
        final_result.append(line)

    return '\n'.join(final_result)


def wrap_in_try_except(lines: list[str]) -> list[str]:
    """Wrap the function body in try-except to catch runtime errors."""
    result = []

    # Find the start of the function body (after def, docstring, and initial declarations)
    body_start = 0
    in_docstring = False
    found_def = False
    found_errors_decl = False
    found_checks_decl = False

    # First pass: find where declarations end
    for i, line in enumerate(lines):
        stripped = line.strip()

        if not found_def and stripped.startswith('def '):
            found_def = True
            result.append(line)
            continue

        if not found_def:
            result.append(line)
            continue

        # Handle docstring
        if '"""' in stripped:
            if stripped.count('"""') >= 2:
                # Single-line docstring
                result.append(line)
                continue
            else:
                in_docstring = not in_docstring
                result.append(line)
                continue

        if in_docstring:
            result.append(line)
            continue

        # Look for errors declaration
        if re.match(r'^\s+errors\s*[:=]', line):
            result.append(line)
            found_errors_decl = True
            continue

        # Look for checks_passed declaration (keep it outside try block)
        if re.match(r'^\s+checks_passed\s*[:=]', line):
            result.append(line)
            found_checks_decl = True
            continue

        # After at least errors declaration, start the try block
        if found_errors_decl and stripped and not stripped.startswith('#'):
            body_start = i
            break

        result.append(line)

    if body_start == 0:
        return lines  # Couldn't find where to insert try-except

    # Check if the function already has a try block anywhere in the body
    # Look for "    try:" (function-level indentation try block)
    has_existing_try = any(line.strip() == "try:" for line in lines[1:])  # Skip def line
    if has_existing_try:
        # Function already has try-except, don't wrap again
        return lines

    # If checks_passed wasn't declared yet, add it before try
    if not found_checks_decl:
        result.append("    checks_passed: list[str] = []")

    # Add try statement
    result.append("    try:")

    # Add rest of body with extra indentation
    for i in range(body_start, len(lines)):
        element = lines[i]
        # Skip checks_passed declarations inside try (we moved it out)
        if re.match(r'^\s+checks_passed\s*[:=]', element):
            continue
        # Handle multiline strings (like TaskScore returns)
        sub_lines = element.split('\n')
        for sub_line in sub_lines:
            if sub_line.strip():
                # Preserve existing indentation and add 4 more spaces for try block
                result.append("    " + sub_line)
            else:
                result.append(sub_line)

    # Add except block to catch runtime errors
    except_block = """    except Exception as e:
        errors.append(f"[X] Runtime error during validation: {str(e)}")
        return TaskScore(
            score=0.0,
            metadata=ScoreMetadata(
                success_accumulator=list(dict.fromkeys(checks_passed)),
                error_accumulator=list(dict.fromkeys(errors)),
            )
        )"""
    result.append(except_block)

    return result


def extract_functions(content: str) -> list[tuple[int, int, str]]:
    """Extract all function definitions with their start/end positions."""
    functions = []

    func_pattern = r'^def\s+\w+\s*\('

    lines = content.split('\n')
    i = 0
    while i < len(lines):
        if re.match(func_pattern, lines[i]):
            start = i
            j = i + 1
            while j < len(lines):
                # Stop at next function or class
                if re.match(r'^def\s+\w+', lines[j]) or re.match(r'^class\s+', lines[j]):
                    break
                # Stop at section headers
                if re.match(r'^# =+', lines[j]):
                    break
                # Stop at module-level variable declarations (like REWARD_FUNCTIONS_NOTION_V2: Dict[)
                if re.match(r'^[A-Z][A-Z_0-9]*\s*[:=]', lines[j]):
                    break
                j += 1

            while j > start + 1 and lines[j-1].strip() == '':
                j -= 1

            func_text = '\n'.join(lines[start:j])
            functions.append((start, j, func_text))
            i = j
        else:
            i += 1

    return functions


def transform_file(input_path: str, output_path: str = None):
    """Transform all reward functions in a file."""

    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    task_score_types = '''
# TaskScore type definitions for accumulated error/success tracking
from typing import Literal, TypedDict as TaskTypedDict

class ScoreMetadata(TaskTypedDict):
    success_accumulator: list[str]
    error_accumulator: list[str]

class TaskScore(TaskTypedDict):
    score: Literal[1.0, 0.0]
    metadata: ScoreMetadata

'''

    if 'class TaskScore' not in content:
        import_end = 0
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('from ') or line.startswith('import '):
                import_end = i + 1
            elif import_end > 0 and line.strip() and not line.startswith('#'):
                break

        lines = lines[:import_end] + [''] + task_score_types.strip().split('\n') + [''] + lines[import_end:]
        content = '\n'.join(lines)

    result_lines = content.split('\n')
    functions = extract_functions(content)

    transformed_content = []
    last_end = 0

    for start, end, func_text in functions:
        transformed_content.extend(result_lines[last_end:start])

        if re.search(r'->\s*[Tt]uple\[float,\s*str\]', func_text):
            transformed_func = transform_function(func_text)
            transformed_content.extend(transformed_func.split('\n'))
        else:
            transformed_content.extend(func_text.split('\n'))

        last_end = end

    transformed_content.extend(result_lines[last_end:])

    final_content = '\n'.join(transformed_content)

    while '\n\n\n' in final_content:
        final_content = final_content.replace('\n\n\n', '\n\n')

    output = output_path or input_path
    with open(output, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f"Transformed file written to: {output}")

    original_count = len(re.findall(r'->\s*[Tt]uple\[float,\s*str\]', content))
    new_count = final_content.count('-> TaskScore')
    print(f"Functions transformed: {new_count} (original had {original_count} Tuple/tuple[float, str] functions)")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python transform_reward_functions.py <input_file> [output_file]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    transform_file(input_file, output_file)
