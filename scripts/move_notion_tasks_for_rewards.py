#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class PlannedMove:
    src: Path
    dst: Path
    reason: str  # "move" | "skip_exists" | "skip_missing"


def _dotted_name_from_annotation(node: ast.AST) -> Optional[str]:
    """
    Return a dotted name string for Name/Attribute nodes.
    Examples:
      - Backend -> "Backend"
      - typing.Dict -> "typing.Dict"
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        cur: ast.AST = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
        return None
    return None


def _matches_backend_annotation(node: Optional[ast.AST]) -> bool:
    if node is None:
        return False
    name = _dotted_name_from_annotation(node)
    return bool(name) and name.split(".")[-1] == "Backend"


def _unwrap_subscript_slice(node: ast.AST) -> ast.AST:
    # Python 3.8 used ast.Index; 3.9+ removed it.
    if isinstance(node, ast.Index):  # type: ignore[attr-defined]
        return node.value  # type: ignore[attr-defined]
    return node


def _matches_name_or_attr(node: ast.AST, expected_leaf: str) -> bool:
    name = _dotted_name_from_annotation(node)
    return bool(name) and name.split(".")[-1] == expected_leaf


def _matches_dict_str_any_annotation(node: Optional[ast.AST]) -> bool:
    """
    Accept:
      - Dict[str, Any]
      - typing.Dict[str, Any]
      - dict[str, Any]
    """
    if node is None:
        return False

    if not isinstance(node, ast.Subscript):
        return False

    dict_name = _dotted_name_from_annotation(node.value)
    if not dict_name:
        return False
    dict_leaf = dict_name.split(".")[-1]
    if dict_leaf not in {"Dict", "dict"}:
        return False

    slice_node = _unwrap_subscript_slice(node.slice)
    if not isinstance(slice_node, ast.Tuple) or len(slice_node.elts) != 2:
        return False

    key_t, val_t = slice_node.elts
    if not _matches_name_or_attr(key_t, "str"):
        return False
    if not _matches_name_or_attr(val_t, "Any"):
        return False
    return True


def _is_reward_function_def(fn: ast.FunctionDef) -> bool:
    """
    A reward function is defined as any function that has two consecutive
    parameters annotated as:
      (Backend, Dict[str, Any])

    This is slightly more permissive than "first two params" and supports
    the (unlikely) case of `self` being present.
    """
    args = list(fn.args.posonlyargs) + list(fn.args.args)
    for i in range(len(args) - 1):
        if _matches_backend_annotation(args[i].annotation) and _matches_dict_str_any_annotation(
            args[i + 1].annotation
        ):
            return True
    return False


def extract_reward_function_names(reward_file: Path) -> set[str]:
    source = reward_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(reward_file))

    reward_fns: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and _is_reward_function_def(node):
            reward_fns.add(node.name)

    return reward_fns


def iter_task_json_paths(source_dir: Path) -> Iterable[Path]:
    # Non-recursive, matches current layout.
    for p in sorted(source_dir.iterdir()):
        if p.is_file() and p.suffix.lower() == ".json":
            yield p


def iter_task_json_paths_if_dir_exists(maybe_dir: Optional[Path]) -> Iterable[Path]:
    if maybe_dir is None or not maybe_dir.exists() or not maybe_dir.is_dir():
        return []
    return iter_task_json_paths(maybe_dir)


def read_task_reward_function(task_path: Path) -> Optional[str]:
    """
    Return the reward function string if the file is a task JSON.
    Skip non-task JSONs like mapping dicts/arrays.
    """
    try:
        data = json.loads(task_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None
    rf = data.get("reward_function")
    if not isinstance(rf, str) or not rf:
        return None
    return rf


def read_task_trace_id(task_path: Path) -> Optional[str]:
    """
    Return the trace_id string if the file is a task JSON.
    Skip non-task JSONs like mapping dicts/arrays.
    """
    try:
        data = json.loads(task_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None
    trace_id = data.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id:
        return None
    return trace_id


def plan_moves(
    *,
    reward_function_names: set[str],
    source_dir: Path,
    dest_dir: Path,
    traces_source_dir: Optional[Path] = None,
    traces_dest_dir: Optional[Path] = None,
) -> tuple[list[PlannedMove], dict[str, list[Path]], int, int]:
    """
    Returns:
      - planned moves (including skips due to existing destination)
      - mapping of reward_function -> task files that matched it
      - count of task files scanned for traces (matched, across source+dest)
      - count of unique trace_ids found (matched, across source+dest)
    """
    by_reward_fn: dict[str, list[Path]] = {}
    planned: list[PlannedMove] = []

    matched_task_paths_source: list[Path] = []
    for task_path in iter_task_json_paths(source_dir):
        rf = read_task_reward_function(task_path)
        if rf is None or rf not in reward_function_names:
            continue

        matched_task_paths_source.append(task_path)
        by_reward_fn.setdefault(rf, []).append(task_path)
        dst = dest_dir / task_path.name
        if dst.exists():
            planned.append(PlannedMove(src=task_path, dst=dst, reason="skip_exists"))
        else:
            planned.append(PlannedMove(src=task_path, dst=dst, reason="move"))

    # Plan trace moves separately from task moves so that even if tasks have already
    # been moved out of source_dir, we can still move traces by scanning dest_dir.
    trace_task_paths: list[Path] = []
    if traces_source_dir is not None and traces_dest_dir is not None:
        trace_task_paths.extend(matched_task_paths_source)
        for task_path in iter_task_json_paths_if_dir_exists(dest_dir):
            rf = read_task_reward_function(task_path)
            if rf is None or rf not in reward_function_names:
                continue
            trace_task_paths.append(task_path)

        unique_trace_ids: set[str] = set()
        for task_path in trace_task_paths:
            trace_id = read_task_trace_id(task_path)
            if not trace_id or trace_id in unique_trace_ids:
                continue
            unique_trace_ids.add(trace_id)

            src_trace = traces_source_dir / f"{trace_id}.json"
            dst_trace = traces_dest_dir / f"{trace_id}.json"
            if dst_trace.exists():
                planned.append(PlannedMove(src=src_trace, dst=dst_trace, reason="skip_exists"))
            elif not src_trace.exists():
                planned.append(PlannedMove(src=src_trace, dst=dst_trace, reason="skip_missing"))
            else:
                planned.append(PlannedMove(src=src_trace, dst=dst_trace, reason="move"))

        return planned, by_reward_fn, len(trace_task_paths), len(unique_trace_ids)

    return planned, by_reward_fn, 0, 0


def apply_moves(planned: list[PlannedMove], *, dry_run: bool) -> tuple[int, int, int]:
    moved = 0
    skipped_exists = 0
    skipped_missing = 0
    for mv in planned:
        if mv.reason == "skip_exists":
            skipped_exists += 1
            print(f"SKIP (exists): {mv.src} -> {mv.dst}")
            continue
        if mv.reason == "skip_missing":
            skipped_missing += 1
            print(f"SKIP (missing): {mv.src} -> {mv.dst}")
            continue

        if dry_run:
            print(f"DRY-RUN: {mv.src} -> {mv.dst}")
            continue

        mv.dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(mv.src), str(mv.dst))
        moved += 1
        print(f"MOVED: {mv.src} -> {mv.dst}")

    return moved, skipped_exists, skipped_missing


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Move Notion task JSONs whose `reward_function` matches reward functions "
            "found in a reward file (by signature: Backend + Dict[str, Any])."
        )
    )
    parser.add_argument(
        "--reward-file",
        required=True,
        type=Path,
        help="Path to the Python reward file to parse (required).",
    )
    parser.add_argument(
        "--source-dir",
        default=Path("dojo-bench-customer-colossus/tasks/notion-v2"),
        type=Path,
        help="Directory containing Notion v2 task JSON files.",
    )
    parser.add_argument(
        "--dest-dir",
        default=Path("dojo-bench-customer-colossus/tasks/notion-database-v2"),
        type=Path,
        help="Directory to move matching task JSON files into.",
    )
    parser.add_argument(
        "--traces-source-dir",
        default=Path("dojo-bench-customer-colossus/traces/notion"),
        type=Path,
        help="Directory containing Notion trace JSON files (defaults to traces/notion).",
    )
    parser.add_argument(
        "--traces-dest-dir",
        default=Path("dojo-bench-customer-colossus/traces/notion-database"),
        type=Path,
        help="Directory to move matching trace JSON files into (defaults to traces/notion-database).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned moves without modifying files.",
    )

    args = parser.parse_args(argv)

    reward_file = args.reward_file
    source_dir = args.source_dir
    dest_dir = args.dest_dir
    traces_source_dir = args.traces_source_dir
    traces_dest_dir = args.traces_dest_dir
    dry_run = bool(args.dry_run)

    if not reward_file.exists() or not reward_file.is_file():
        print(f"ERROR: reward file not found: {reward_file}", file=sys.stderr)
        return 2
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"ERROR: source dir not found: {source_dir}", file=sys.stderr)
        return 2
    if traces_source_dir is not None and (not traces_source_dir.exists() or not traces_source_dir.is_dir()):
        print(f"ERROR: traces source dir not found: {traces_source_dir}", file=sys.stderr)
        return 2

    reward_fn_names = extract_reward_function_names(reward_file)
    planned, by_reward_fn, trace_task_count, trace_id_count = plan_moves(
        reward_function_names=reward_fn_names,
        source_dir=source_dir,
        dest_dir=dest_dir,
        traces_source_dir=traces_source_dir,
        traces_dest_dir=traces_dest_dir,
    )

    print(f"Extracted reward functions: {len(reward_fn_names)}")
    print(f"Matched task files (source): {sum(len(v) for v in by_reward_fn.values())}")
    if traces_source_dir is not None and traces_dest_dir is not None:
        print(f"Matched task files for traces (source+dest): {trace_task_count}")
        print(f"Unique trace_ids found: {trace_id_count}")
    print(f"Planned operations (including skips): {len(planned)}")
    if dry_run:
        print("Mode: DRY-RUN")
    else:
        print("Mode: APPLY")

    moved, skipped_exists, skipped_missing = apply_moves(planned, dry_run=dry_run)

    # In dry-run mode, `moved` stays 0; we still want a clear count of would-move vs skip.
    would_move = sum(1 for mv in planned if mv.reason == "move")
    would_skip_exists = sum(1 for mv in planned if mv.reason == "skip_exists")
    would_skip_missing = sum(1 for mv in planned if mv.reason == "skip_missing")

    if dry_run:
        print(f"Would move: {would_move}")
        print(f"Would skip (exists): {would_skip_exists}")
        print(f"Would skip (missing): {would_skip_missing}")
    else:
        print(f"Moved: {moved}")
        print(f"Skipped (exists): {skipped_exists}")
        print(f"Skipped (missing): {skipped_missing}")

    missing_tasks = sorted([fn for fn in reward_fn_names if fn not in by_reward_fn])
    print(f"Reward functions with no matching tasks: {len(missing_tasks)}")
    for fn in missing_tasks:
        print(f"NO-TASK: {fn}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

