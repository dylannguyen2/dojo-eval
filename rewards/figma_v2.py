"""
Reward functions for Figma SPA tasks - V2 Architecture.

This module contains validation functions for Figma/FigJam tasks.
Each function follows the naming convention `_validate_figma_*` and returns
a TaskScore dict with score (1.0 or 0.0) and metadata containing
success_accumulator and error_accumulator lists.

Collections available in Figma backend:
- currentUser: Current authenticated user
- users: All users
- teams: Team definitions with members
- projects: Projects within teams
- files: Design files (editorType: "figma" or "figjam")
- pages: Pages within files
- nodes: All design nodes (frames, shapes, sticky notes, etc.)
- components: Reusable components
- componentSets: Component variant sets
- styles: Color, text, and effect styles
- variables: Design tokens
- variableCollections: Variable collection definitions
"""

from typing import Any, Dict, List, TypedDict, Literal
from .backend import Backend


class ScoreMetadata(TypedDict):
    success_accumulator: List[str]
    error_accumulator: List[str]


class TaskScore(TypedDict):
    score: Literal[1.0, 0.0]
    metadata: ScoreMetadata


def _validate_figma_create_sticky_note(
    backend: Backend,
    final_state_frontend: Dict[str, Any],
    final_answer: str = ""
) -> TaskScore:
    """
    Task: Create a yellow sticky note with specific text in FigJam.

    Validates:
    1. A sticky node exists in the nodes collection
    2. The sticky has stickyColor "yellow"
    3. The sticky contains the expected text about design team follow-up
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        # Query for sticky nodes
        sticky_nodes = backend.query({
            "collection": "nodes",
            "filter": {"type": "sticky"}
        })

        if not sticky_nodes:
            errors.append("[X] No sticky notes found in the canvas")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append(f"[✓] Found {len(sticky_nodes)} sticky note(s)")

        # Check for yellow sticky with correct text
        expected_text_keywords = ["follow up", "design team", "color palette"]
        found_matching_sticky = False

        for sticky in sticky_nodes:
            sticky_color = sticky.get("stickyColor", "")
            sticky_text = sticky.get("text", "").lower()

            # Check if yellow
            is_yellow = sticky_color == "yellow"

            # Check if text contains expected keywords
            has_keywords = all(
                keyword.lower() in sticky_text
                for keyword in ["follow up", "design team", "color palette"]
            )

            if is_yellow and has_keywords:
                found_matching_sticky = True
                checks_passed.append(f"[✓] Found yellow sticky with correct text: '{sticky.get('text', '')[:50]}...'")
                break
            elif is_yellow:
                checks_passed.append(f"[✓] Found yellow sticky note")
            elif has_keywords:
                errors.append(f"[X] Found sticky with correct text but wrong color: {sticky_color}")

        if not found_matching_sticky:
            # Check what's missing
            yellow_stickies = [s for s in sticky_nodes if s.get("stickyColor") == "yellow"]
            if not yellow_stickies:
                errors.append("[X] No yellow sticky notes found. Expected a yellow sticky.")
            else:
                errors.append("[X] Yellow sticky exists but text does not contain expected content about 'follow up', 'design team', and 'color palette'")

        return TaskScore(
            score=1.0 if found_matching_sticky else 0.0,
            metadata=ScoreMetadata(
                success_accumulator=checks_passed,
                error_accumulator=errors
            )
        )

    except Exception as e:
        errors.append(f"[X] Exception during validation: {str(e)}")
        return TaskScore(
            score=0.0,
            metadata=ScoreMetadata(
                success_accumulator=checks_passed,
                error_accumulator=errors
            )
        )


def _validate_figma_create_shape_with_text(
    backend: Backend,
    final_state_frontend: Dict[str, Any],
    final_answer: str = ""
) -> TaskScore:
    """
    Task: Create a diamond shape with text "Decision Point" in FigJam.

    Validates:
    1. A shape-with-text node exists
    2. The shape type is "diamond"
    3. The text is "Decision Point"
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        # Query for shape-with-text nodes
        shape_nodes = backend.query({
            "collection": "nodes",
            "filter": {"type": "shape-with-text"}
        })

        if not shape_nodes:
            errors.append("[X] No shape-with-text nodes found in the canvas")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append(f"[✓] Found {len(shape_nodes)} shape-with-text node(s)")

        # Look for diamond shape with "Decision Point" text
        found_matching_shape = False

        for shape in shape_nodes:
            shape_type = shape.get("shapeType", "")
            shape_text = shape.get("text", "").strip()

            is_diamond = shape_type == "diamond"
            has_correct_text = shape_text.lower() == "decision point"

            if is_diamond and has_correct_text:
                found_matching_shape = True
                checks_passed.append(f"[✓] Found diamond shape with text 'Decision Point'")
                break
            elif is_diamond:
                checks_passed.append(f"[✓] Found diamond shape")
                errors.append(f"[X] Diamond shape text is '{shape_text}', expected 'Decision Point'")
            elif has_correct_text:
                errors.append(f"[X] Shape with 'Decision Point' text is {shape_type}, expected 'diamond'")

        if not found_matching_shape and not any("diamond" in e.lower() for e in errors):
            errors.append("[X] No diamond shape found with text 'Decision Point'")

        return TaskScore(
            score=1.0 if found_matching_shape else 0.0,
            metadata=ScoreMetadata(
                success_accumulator=checks_passed,
                error_accumulator=errors
            )
        )

    except Exception as e:
        errors.append(f"[X] Exception during validation: {str(e)}")
        return TaskScore(
            score=0.0,
            metadata=ScoreMetadata(
                success_accumulator=checks_passed,
                error_accumulator=errors
            )
        )


def _validate_figma_create_frame_with_rectangles(
    backend: Backend,
    final_state_frontend: Dict[str, Any],
    final_answer: str = ""
) -> TaskScore:
    """
    Task: Create a frame named 'Button States' (400x300) with 3 rectangles.

    Validates:
    1. A frame named 'Button States' exists
    2. Frame has dimensions 400x300
    3. Frame contains exactly 3 rectangle nodes
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        # Query for frame nodes
        frame_nodes = backend.query({
            "collection": "nodes",
            "filter": {"type": "frame"}
        })

        # Find frame named 'Button States'
        button_states_frame = None
        for frame in frame_nodes:
            if frame.get("name", "").lower() == "button states":
                button_states_frame = frame
                break

        if not button_states_frame:
            errors.append("[X] Frame named 'Button States' not found")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] Found frame named 'Button States'")

        # Check dimensions
        width = button_states_frame.get("width", 0)
        height = button_states_frame.get("height", 0)

        if width == 400 and height == 300:
            checks_passed.append(f"[✓] Frame dimensions are correct: {width}x{height}")
        else:
            errors.append(f"[X] Frame dimensions are {width}x{height}, expected 400x300")

        # Query for rectangles inside this frame
        frame_id = button_states_frame.get("_id")
        rectangle_nodes = backend.query({
            "collection": "nodes",
            "filter": {"type": "rectangle", "parentId": frame_id}
        })

        rect_count = len(rectangle_nodes)
        if rect_count == 3:
            checks_passed.append(f"[✓] Frame contains exactly 3 rectangles")
        else:
            errors.append(f"[X] Frame contains {rect_count} rectangles, expected 3")

        # All checks passed if no errors
        all_passed = len(errors) == 0

        return TaskScore(
            score=1.0 if all_passed else 0.0,
            metadata=ScoreMetadata(
                success_accumulator=checks_passed,
                error_accumulator=errors
            )
        )

    except Exception as e:
        errors.append(f"[X] Exception during validation: {str(e)}")
        return TaskScore(
            score=0.0,
            metadata=ScoreMetadata(
                success_accumulator=checks_passed,
                error_accumulator=errors
            )
        )


def _validate_figma_rename_file(
    backend: Backend,
    final_state_frontend: Dict[str, Any],
    final_answer: str = ""
) -> TaskScore:
    """
    Task: Rename 'Login Flow' file to 'Authentication Screens v2'.

    Validates:
    1. A file named 'Authentication Screens v2' exists
    2. No file named 'Login Flow' exists (it was renamed)
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        # Query all files
        files = backend.query({
            "collection": "files",
            "filter": {}
        })

        file_names = [f.get("name", "") for f in files]

        # Check for new name
        has_new_name = "Authentication Screens v2" in file_names
        has_old_name = "Login Flow" in file_names

        if has_new_name:
            checks_passed.append("[✓] File 'Authentication Screens v2' exists")
        else:
            errors.append("[X] File 'Authentication Screens v2' not found")

        if not has_old_name:
            checks_passed.append("[✓] File 'Login Flow' no longer exists (was renamed)")
        else:
            errors.append("[X] File 'Login Flow' still exists - rename not completed")

        all_passed = has_new_name and not has_old_name

        return TaskScore(
            score=1.0 if all_passed else 0.0,
            metadata=ScoreMetadata(
                success_accumulator=checks_passed,
                error_accumulator=errors
            )
        )

    except Exception as e:
        errors.append(f"[X] Exception during validation: {str(e)}")
        return TaskScore(
            score=0.0,
            metadata=ScoreMetadata(
                success_accumulator=checks_passed,
                error_accumulator=errors
            )
        )


def _validate_figma_create_color_style(
    backend: Backend,
    final_state_frontend: Dict[str, Any],
    final_answer: str = ""
) -> TaskScore:
    """
    Task: Create a color style named 'Brand/Primary' with color #6366F1.

    Validates:
    1. A style named 'Brand/Primary' exists
    2. The style type is 'fill' or 'color'
    3. The color value is #6366F1 (or equivalent RGB)
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        # Query all styles
        styles = backend.query({
            "collection": "styles",
            "filter": {}
        })

        # Find style named 'Brand/Primary'
        brand_primary_style = None
        for style in styles:
            if style.get("name", "") == "Brand/Primary":
                brand_primary_style = style
                break

        if not brand_primary_style:
            errors.append("[X] Style named 'Brand/Primary' not found")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] Found style named 'Brand/Primary'")

        # Check style type
        style_type = brand_primary_style.get("type", "")
        if style_type in ["fill", "color", "FILL"]:
            checks_passed.append(f"[✓] Style type is '{style_type}'")
        else:
            errors.append(f"[X] Style type is '{style_type}', expected 'fill' or 'color'")

        # Check color value
        # Color could be in different formats: hex string, or RGB object
        expected_hex = "#6366F1".lower()
        expected_rgb = (99, 102, 241)  # RGB equivalent

        color_value = brand_primary_style.get("color", brand_primary_style.get("value", {}))
        color_matched = False

        if isinstance(color_value, str):
            if color_value.lower() == expected_hex:
                color_matched = True
        elif isinstance(color_value, dict):
            r = int(color_value.get("r", 0) * 255) if color_value.get("r", 0) <= 1 else color_value.get("r", 0)
            g = int(color_value.get("g", 0) * 255) if color_value.get("g", 0) <= 1 else color_value.get("g", 0)
            b = int(color_value.get("b", 0) * 255) if color_value.get("b", 0) <= 1 else color_value.get("b", 0)
            if (r, g, b) == expected_rgb or abs(r - 99) <= 2 and abs(g - 102) <= 2 and abs(b - 241) <= 2:
                color_matched = True

        if color_matched:
            checks_passed.append(f"[✓] Color value matches #6366F1")
        else:
            errors.append(f"[X] Color value does not match #6366F1. Found: {color_value}")

        all_passed = len(errors) == 0

        return TaskScore(
            score=1.0 if all_passed else 0.0,
            metadata=ScoreMetadata(
                success_accumulator=checks_passed,
                error_accumulator=errors
            )
        )

    except Exception as e:
        errors.append(f"[X] Exception during validation: {str(e)}")
        return TaskScore(
            score=0.0,
            metadata=ScoreMetadata(
                success_accumulator=checks_passed,
                error_accumulator=errors
            )
        )
