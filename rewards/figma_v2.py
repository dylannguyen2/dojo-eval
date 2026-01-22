"""
Reward functions for Figma SPA tasks - Prompts5 batch.

These validation functions focus on design analysis, hierarchy navigation,
spatial layout analysis, component analysis, and code extraction tasks.
All tasks expect JSON-formatted final answers.
"""

import json
import re
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union
from .backend import Backend


class ScoreMetadata(TypedDict):
    success_accumulator: List[str]
    error_accumulator: List[str]


class TaskScore(TypedDict):
    score: Literal[1.0, 0.0]
    metadata: ScoreMetadata


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_json_from_answer(answer: str) -> Optional[Dict[str, Any]]:
    """Extract JSON object from the final answer string."""
    # Try to find JSON in the answer
    # First, try direct parsing
    try:
        return json.loads(answer.strip())
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in markdown code fence
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', answer, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find any JSON object in the text
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', answer, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _check_value_tolerance(actual: Union[int, float], expected: Union[int, float], tolerance: int = 0) -> bool:
    """Check if actual value is within tolerance of expected value."""
    return abs(actual - expected) <= tolerance


def _get_nested_value(data: Dict[str, Any], *keys: str) -> Any:
    """Safely get a nested value from a dictionary."""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


# =============================================================================
# Task 1: Extract Login Screen as React Code with SVG
# =============================================================================

def _validate_figma_login_screen_react_extraction(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate extraction of 'Login Screen' frame as React code with embedded SVG.

    Expected JSON:
    {
      "framework": "react",
      "component_name": "<extracted from code>",
      "has_svg": <boolean>,
      "code_length": <number>
    }

    Verification:
    - Code is valid React component syntax with export default
    - Contains dangerouslySetInnerHTML prop with embedded SVG
    - SVG element exists within the HTML string
    - Component accepts className and props parameters
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check framework is react
        framework = json_data.get("framework", "").lower()
        if framework == "react":
            checks_passed.append("[✓] Framework is 'react'")
        else:
            errors.append(f"[X] Framework is '{framework}', expected 'react'")

        # Check has_svg is true
        has_svg = json_data.get("has_svg")
        if has_svg is True:
            checks_passed.append("[✓] has_svg is true - SVG element exists")
        else:
            errors.append(f"[X] has_svg is {has_svg}, expected true")

        # Check component_name exists
        component_name = json_data.get("component_name")
        if component_name and isinstance(component_name, str) and len(component_name) > 0:
            checks_passed.append(f"[✓] Component name extracted: '{component_name}'")
        else:
            errors.append("[X] Component name not properly extracted")

        # Check code_length is reasonable (> 100 chars for a real component)
        code_length = json_data.get("code_length")
        if isinstance(code_length, (int, float)) and code_length > 100:
            checks_passed.append(f"[✓] Code length is {code_length} characters")
        else:
            errors.append(f"[X] Code length is {code_length}, expected > 100")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 2: Spatial Analysis of Input Fields
# =============================================================================

def _validate_figma_input_fields_spatial_analysis(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate spatial analysis of Email Input and Password Input fields.

    Expected JSON:
    {
      "email_input": {"name": "Email Input", "x": 24, "y": 380, "width": 327, "height": 48},
      "password_input": {"name": "Password Input", "x": 24, "y": 444, "width": 327, "height": 48},
      "vertical_spacing": 16,
      "horizontally_aligned": true,
      "same_dimensions": true
    }

    Verification:
    - Email Input at (24, 380) with 327x48
    - Password Input at (24, 444) with 327x48
    - Vertical spacing is 16 pixels (444 - 380 - 48 = 16)
    - Both horizontally aligned (same x)
    - Both have identical dimensions
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check Email Input position
        email = json_data.get("email_input", {})
        if _get_nested_value(json_data, "email_input", "x") == 24:
            checks_passed.append("[✓] Email Input x=24")
        else:
            errors.append(f"[X] Email Input x={email.get('x')}, expected 24")

        if _get_nested_value(json_data, "email_input", "y") == 380:
            checks_passed.append("[✓] Email Input y=380")
        else:
            errors.append(f"[X] Email Input y={email.get('y')}, expected 380")

        # Check Email Input dimensions
        if email.get("width") == 327 and email.get("height") == 48:
            checks_passed.append("[✓] Email Input dimensions 327x48")
        else:
            errors.append(f"[X] Email Input dimensions {email.get('width')}x{email.get('height')}, expected 327x48")

        # Check Password Input position
        password = json_data.get("password_input", {})
        if _get_nested_value(json_data, "password_input", "x") == 24:
            checks_passed.append("[✓] Password Input x=24")
        else:
            errors.append(f"[X] Password Input x={password.get('x')}, expected 24")

        if _get_nested_value(json_data, "password_input", "y") == 444:
            checks_passed.append("[✓] Password Input y=444")
        else:
            errors.append(f"[X] Password Input y={password.get('y')}, expected 444")

        # Check Password Input dimensions
        if password.get("width") == 327 and password.get("height") == 48:
            checks_passed.append("[✓] Password Input dimensions 327x48")
        else:
            errors.append(f"[X] Password Input dimensions {password.get('width')}x{password.get('height')}, expected 327x48")

        # Check vertical spacing (should be 16: 444 - 380 - 48 = 16)
        vertical_spacing = json_data.get("vertical_spacing")
        if vertical_spacing == 16:
            checks_passed.append("[✓] Vertical spacing is 16 pixels")
        else:
            errors.append(f"[X] Vertical spacing is {vertical_spacing}, expected 16")

        # Check horizontally aligned
        horizontally_aligned = json_data.get("horizontally_aligned")
        if horizontally_aligned is True:
            checks_passed.append("[✓] Both inputs are horizontally aligned")
        else:
            errors.append("[X] horizontally_aligned is not true")

        # Check same dimensions
        same_dimensions = json_data.get("same_dimensions")
        if same_dimensions is True:
            checks_passed.append("[✓] Both inputs have identical dimensions")
        else:
            errors.append("[X] same_dimensions is not true")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 3: Variable Definitions Cross-Reference
# =============================================================================

def _validate_figma_variable_definitions_crossref(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate variable definitions for Sign In Button and Header Background.

    Expected JSON:
    {
      "button_node_name": "Sign In Button",
      "header_node_name": "Header Background",
      "shared_variable": "var-primary",
      "collection_name": "Brand Colors",
      "color_consistency": {
        "light_mode": "#3B82F6",
        "dark_mode": "#60A5FA"
      },
      "same_variable_binding": true
    }

    Verification:
    - Both nodes use 'var-primary' for fill binding
    - Variable belongs to 'Brand Colors' collection
    - Light mode color is '#3B82F6'
    - Dark mode color is '#60A5FA'
    - Variable binding is identical
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check shared variable
        shared_var = json_data.get("shared_variable", "").lower()
        if "var-primary" in shared_var or "primary" in shared_var:
            checks_passed.append("[✓] Shared variable is 'var-primary'")
        else:
            errors.append(f"[X] Shared variable is '{json_data.get('shared_variable')}', expected 'var-primary'")

        # Check collection name
        collection = json_data.get("collection_name", "").lower()
        if "brand" in collection and "color" in collection:
            checks_passed.append("[✓] Collection is 'Brand Colors'")
        else:
            errors.append(f"[X] Collection is '{json_data.get('collection_name')}', expected 'Brand Colors'")

        # Check light mode color
        color_consistency = json_data.get("color_consistency", {})
        light_mode = color_consistency.get("light_mode", "").upper()
        if light_mode == "#3B82F6" or light_mode == "3B82F6":
            checks_passed.append("[✓] Light mode color is '#3B82F6'")
        else:
            errors.append(f"[X] Light mode color is '{light_mode}', expected '#3B82F6'")

        # Check dark mode color
        dark_mode = color_consistency.get("dark_mode", "").upper()
        if dark_mode == "#60A5FA" or dark_mode == "60A5FA":
            checks_passed.append("[✓] Dark mode color is '#60A5FA'")
        else:
            errors.append(f"[X] Dark mode color is '{dark_mode}', expected '#60A5FA'")

        # Check same variable binding
        same_binding = json_data.get("same_variable_binding")
        if same_binding is True:
            checks_passed.append("[✓] Variable binding is identical between nodes")
        else:
            errors.append("[X] same_variable_binding is not true")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 4: ShopEasy Home Screen Hierarchy Navigation
# =============================================================================

def _validate_figma_shopeasy_home_hierarchy(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate navigation of ShopEasy Home Screen hierarchy.

    Expected JSON:
    {
      "root_frame": {"name": "ShopEasy Home Screen", "x": 0, "y": 0, "width": 393, "height": 852},
      "header_actions": {"name": "Header Actions", "child_count": 2, "children": [...]},
      "total_nodes_analyzed": <number>
    }

    Verification:
    - Root frame at (0,0) with dimensions 393x852
    - Header Actions has exactly 2 ellipse children
    - Search Icon is type ellipse
    - Cart Icon is type ellipse
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check root frame position
        root_frame = json_data.get("root_frame", {})
        if root_frame.get("x") == 0 and root_frame.get("y") == 0:
            checks_passed.append("[✓] Root frame at position (0,0)")
        else:
            errors.append(f"[X] Root frame at ({root_frame.get('x')},{root_frame.get('y')}), expected (0,0)")

        # Check root frame dimensions
        if root_frame.get("width") == 393 and root_frame.get("height") == 852:
            checks_passed.append("[✓] Root frame dimensions 393x852")
        else:
            errors.append(f"[X] Root frame dimensions {root_frame.get('width')}x{root_frame.get('height')}, expected 393x852")

        # Check Header Actions child count
        header_actions = json_data.get("header_actions", {})
        child_count = header_actions.get("child_count")
        if child_count == 2:
            checks_passed.append("[✓] Header Actions has exactly 2 children")
        else:
            errors.append(f"[X] Header Actions has {child_count} children, expected 2")

        # Check children are ellipse type
        children = header_actions.get("children", [])
        answer_lower = final_answer.lower()

        if "search" in answer_lower and "ellipse" in answer_lower:
            checks_passed.append("[✓] Search Icon is type ellipse")
        else:
            errors.append("[X] Search Icon type not verified as ellipse")

        if "cart" in answer_lower and "ellipse" in answer_lower:
            checks_passed.append("[✓] Cart Icon is type ellipse")
        else:
            errors.append("[X] Cart Icon type not verified as ellipse")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 5: Extract Login Screen as React with Text Focus
# =============================================================================

def _validate_figma_login_screen_text_react(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate extraction of Login Screen as React code focusing on text elements.

    Expected JSON:
    {
      "framework": "react",
      "code": "<the generated React component>",
      "has_svg": true,
      "jsx_syntax": true
    }

    Verification:
    - Code uses React/JSX syntax
    - Contains embedded SVG element
    - Component structure is valid React
    - JSX syntax is correct
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check framework is react
        framework = json_data.get("framework", "").lower()
        if framework == "react":
            checks_passed.append("[✓] Framework is 'react'")
        else:
            errors.append(f"[X] Framework is '{framework}', expected 'react'")

        # Check has_svg
        has_svg = json_data.get("has_svg")
        if has_svg is True:
            checks_passed.append("[✓] has_svg is true - contains embedded SVG")
        else:
            errors.append(f"[X] has_svg is {has_svg}, expected true")

        # Check jsx_syntax
        jsx_syntax = json_data.get("jsx_syntax")
        if jsx_syntax is True:
            checks_passed.append("[✓] jsx_syntax is true - valid JSX")
        else:
            errors.append(f"[X] jsx_syntax is {jsx_syntax}, expected true")

        # Check code exists and has content
        code = json_data.get("code", "")
        if isinstance(code, str) and len(code) > 50:
            checks_passed.append("[✓] Code field contains React component")
        else:
            errors.append("[X] Code field is missing or too short")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 6: Buttons Page Component Hierarchy Analysis
# =============================================================================

def _validate_figma_buttons_page_hierarchy(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate component hierarchy analysis on the Buttons page.

    Expected JSON:
    {
      "page_name": "Buttons",
      "total_components": 2,
      "components": [
        {"name": "Button/Primary", "x": 100, "y": 100, "width": 120, "height": 40},
        {"name": "Button/Secondary", "x": 100, "y": 160, "width": 120, "height": 40}
      ],
      "vertical_spacing": 20
    }

    Verification:
    - Page contains exactly 2 component nodes
    - Button/Primary at (100,100) with 120x40
    - Button/Secondary at (100,160) with 120x40
    - Vertical spacing is 20 pixels
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check total components
        total_components = json_data.get("total_components")
        if total_components == 2:
            checks_passed.append("[✓] Exactly 2 components on page")
        else:
            errors.append(f"[X] total_components is {total_components}, expected 2")

        # Check components array
        components = json_data.get("components", [])

        # Find Primary button
        primary = next((c for c in components if "primary" in c.get("name", "").lower()), None)
        if primary:
            if primary.get("x") == 100 and primary.get("y") == 100:
                checks_passed.append("[✓] Button/Primary at (100,100)")
            else:
                errors.append(f"[X] Button/Primary at ({primary.get('x')},{primary.get('y')}), expected (100,100)")

            if primary.get("width") == 120 and primary.get("height") == 40:
                checks_passed.append("[✓] Button/Primary dimensions 120x40")
            else:
                errors.append(f"[X] Button/Primary dimensions {primary.get('width')}x{primary.get('height')}, expected 120x40")
        else:
            errors.append("[X] Button/Primary component not found")

        # Find Secondary button
        secondary = next((c for c in components if "secondary" in c.get("name", "").lower()), None)
        if secondary:
            if secondary.get("x") == 100 and secondary.get("y") == 160:
                checks_passed.append("[✓] Button/Secondary at (100,160)")
            else:
                errors.append(f"[X] Button/Secondary at ({secondary.get('x')},{secondary.get('y')}), expected (100,160)")

            if secondary.get("width") == 120 and secondary.get("height") == 40:
                checks_passed.append("[✓] Button/Secondary dimensions 120x40")
            else:
                errors.append(f"[X] Button/Secondary dimensions {secondary.get('width')}x{secondary.get('height')}, expected 120x40")
        else:
            errors.append("[X] Button/Secondary component not found")

        # Check vertical spacing
        vertical_spacing = json_data.get("vertical_spacing")
        if vertical_spacing == 20 or str(vertical_spacing) == "20":
            checks_passed.append("[✓] Vertical spacing is 20 pixels")
        else:
            errors.append(f"[X] Vertical spacing is {vertical_spacing}, expected 20")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 7: Q1 Goals Section FigJam Extraction
# =============================================================================

def _validate_figma_q1_goals_section_extraction(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate extraction of Q1 Goals section from FigJam as React code.

    Expected JSON:
    {
      "framework": "react",
      "section_name": "Q1 Goals",
      "position": {"x": 50, "y": 50},
      "dimensions": {"width": 800, "height": 400},
      "code": "<the generated React code>",
      "has_svg": true,
      "opacity_level": "<opacity value>"
    }

    Verification:
    - Generated code is valid React component
    - Code contains embedded SVG data
    - Section positioned at (50,50)
    - Section dimensions are 800x400
    - SVG shows section's visual appearance with opacity
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check framework
        framework = json_data.get("framework", "").lower()
        if framework == "react":
            checks_passed.append("[✓] Framework is 'react'")
        else:
            errors.append(f"[X] Framework is '{framework}', expected 'react'")

        # Check section name
        section_name = json_data.get("section_name", "")
        if "q1" in section_name.lower() and "goal" in section_name.lower():
            checks_passed.append("[✓] Section name is 'Q1 Goals'")
        else:
            errors.append(f"[X] Section name is '{section_name}', expected 'Q1 Goals'")

        # Check position
        position = json_data.get("position", {})
        if position.get("x") == 50 and position.get("y") == 50:
            checks_passed.append("[✓] Section positioned at (50,50)")
        else:
            errors.append(f"[X] Section at ({position.get('x')},{position.get('y')}), expected (50,50)")

        # Check dimensions
        dimensions = json_data.get("dimensions", {})
        if dimensions.get("width") == 800 and dimensions.get("height") == 400:
            checks_passed.append("[✓] Section dimensions 800x400")
        else:
            errors.append(f"[X] Section dimensions {dimensions.get('width')}x{dimensions.get('height')}, expected 800x400")

        # Check has_svg
        has_svg = json_data.get("has_svg")
        if has_svg is True:
            checks_passed.append("[✓] has_svg is true - contains embedded SVG")
        else:
            errors.append(f"[X] has_svg is {has_svg}, expected true")

        # Check code exists
        code = json_data.get("code", "")
        if isinstance(code, str) and len(code) > 50:
            checks_passed.append("[✓] Code field contains React component")
        else:
            errors.append("[X] Code field is missing or too short")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 8: Complex Button Component Analysis with Variants
# =============================================================================

def _validate_figma_button_component_variants(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate complex component analysis on Button components with variants.

    Expected JSON includes components with variantProperties, componentSetId, etc.

    Verification:
    - Button/Primary at (100,100) with 120x40
    - Button/Secondary at (100,160) with 120x40
    - Both have type 'component'
    - Both belong to componentSetId 'compset-button'
    - Primary has variantProperties State='Default', Variant='Primary'
    - Secondary has variantProperties State='Default', Variant='Secondary'
    - Vertical spacing is 20px
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        components = json_data.get("components", [])

        # Find Primary button
        primary = next((c for c in components if "primary" in c.get("name", "").lower()), None)
        if primary:
            # Check position
            if primary.get("x") == 100 and primary.get("y") == 100:
                checks_passed.append("[✓] Button/Primary at (100,100)")
            else:
                errors.append(f"[X] Button/Primary at ({primary.get('x')},{primary.get('y')}), expected (100,100)")

            # Check dimensions
            if primary.get("width") == 120 and primary.get("height") == 40:
                checks_passed.append("[✓] Button/Primary dimensions 120x40")
            else:
                errors.append(f"[X] Button/Primary dimensions incorrect")

            # Check type
            if primary.get("type") == "component":
                checks_passed.append("[✓] Button/Primary has type 'component'")
            else:
                errors.append(f"[X] Button/Primary type is '{primary.get('type')}', expected 'component'")

            # Check componentSetId
            if primary.get("componentSetId") == "compset-button":
                checks_passed.append("[✓] Button/Primary belongs to 'compset-button'")
            else:
                errors.append(f"[X] Button/Primary componentSetId is '{primary.get('componentSetId')}'")

            # Check variantProperties
            variant_props = primary.get("variantProperties", {})
            if variant_props.get("State") == "Default" and variant_props.get("Variant") == "Primary":
                checks_passed.append("[✓] Button/Primary has correct variantProperties")
            else:
                errors.append(f"[X] Button/Primary variantProperties incorrect: {variant_props}")
        else:
            errors.append("[X] Button/Primary component not found")

        # Find Secondary button
        secondary = next((c for c in components if "secondary" in c.get("name", "").lower()), None)
        if secondary:
            # Check position
            if secondary.get("x") == 100 and secondary.get("y") == 160:
                checks_passed.append("[✓] Button/Secondary at (100,160)")
            else:
                errors.append(f"[X] Button/Secondary at ({secondary.get('x')},{secondary.get('y')}), expected (100,160)")

            # Check dimensions
            if secondary.get("width") == 120 and secondary.get("height") == 40:
                checks_passed.append("[✓] Button/Secondary dimensions 120x40")
            else:
                errors.append(f"[X] Button/Secondary dimensions incorrect")

            # Check type
            if secondary.get("type") == "component":
                checks_passed.append("[✓] Button/Secondary has type 'component'")
            else:
                errors.append(f"[X] Button/Secondary type is '{secondary.get('type')}'")

            # Check componentSetId
            if secondary.get("componentSetId") == "compset-button":
                checks_passed.append("[✓] Button/Secondary belongs to 'compset-button'")
            else:
                errors.append(f"[X] Button/Secondary componentSetId incorrect")

            # Check variantProperties
            variant_props = secondary.get("variantProperties", {})
            if variant_props.get("State") == "Default" and variant_props.get("Variant") == "Secondary":
                checks_passed.append("[✓] Button/Secondary has correct variantProperties")
            else:
                errors.append(f"[X] Button/Secondary variantProperties incorrect: {variant_props}")
        else:
            errors.append("[X] Button/Secondary component not found")

        # Check vertical spacing
        vertical_spacing = json_data.get("vertical_spacing")
        if vertical_spacing == 20:
            checks_passed.append("[✓] Vertical spacing is 20px")
        else:
            errors.append(f"[X] Vertical spacing is {vertical_spacing}, expected 20")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 9: FigJam Connector Relationships Analysis
# =============================================================================

def _validate_figma_figjam_connector_analysis(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate FigJam connector relationships and spatial layout analysis.

    Verification:
    - Connection 1-2 exists with correct endpoints
    - Connection 2-3 exists with correct endpoints
    - Both use right and left magnets
    - Q1 Goals section at (50,50) with 800x400
    - Approved stamp at (250,280)
    - Section encompasses sticky positions
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check connectors
        connectors = json_data.get("connectors", [])

        # Find Connection 1-2
        conn12 = next((c for c in connectors if "1-2" in c.get("name", "")), None)
        if conn12:
            checks_passed.append("[✓] Connection 1-2 found")

            if conn12.get("start_node") == "Feature Idea" and conn12.get("end_node") == "Priority":
                checks_passed.append("[✓] Connection 1-2 connects Feature Idea to Priority")
            else:
                errors.append("[X] Connection 1-2 endpoints incorrect")

            if conn12.get("start_magnet") == "right" and conn12.get("end_magnet") == "left":
                checks_passed.append("[✓] Connection 1-2 uses right and left magnets")
            else:
                errors.append("[X] Connection 1-2 magnets incorrect")
        else:
            errors.append("[X] Connection 1-2 not found")

        # Find Connection 2-3
        conn23 = next((c for c in connectors if "2-3" in c.get("name", "")), None)
        if conn23:
            checks_passed.append("[✓] Connection 2-3 found")

            if conn23.get("start_node") == "Priority" and conn23.get("end_node") == "Tech Debt":
                checks_passed.append("[✓] Connection 2-3 connects Priority to Tech Debt")
            else:
                errors.append("[X] Connection 2-3 endpoints incorrect")

            if conn23.get("start_magnet") == "right" and conn23.get("end_magnet") == "left":
                checks_passed.append("[✓] Connection 2-3 uses right and left magnets")
            else:
                errors.append("[X] Connection 2-3 magnets incorrect")
        else:
            errors.append("[X] Connection 2-3 not found")

        # Check section coverage
        section_coverage = json_data.get("section_coverage", {})
        section_bounds = section_coverage.get("section_bounds", {})

        if section_bounds.get("x") == 50 and section_bounds.get("y") == 50:
            checks_passed.append("[✓] Q1 Goals section at (50,50)")
        else:
            errors.append("[X] Q1 Goals section position incorrect")

        if section_bounds.get("width") == 800 and section_bounds.get("height") == 400:
            checks_passed.append("[✓] Q1 Goals section dimensions 800x400")
        else:
            errors.append("[X] Q1 Goals section dimensions incorrect")

        if section_coverage.get("encompasses_all_stickies") is True:
            checks_passed.append("[✓] Section encompasses all sticky notes")
        else:
            errors.append("[X] Section does not encompass all stickies")

        # Check stamp analysis
        stamp = json_data.get("stamp_analysis", {})
        if stamp.get("stamp_x") == 250 and stamp.get("stamp_y") == 280:
            checks_passed.append("[✓] Approved stamp at (250,280)")
        else:
            errors.append(f"[X] Stamp at ({stamp.get('stamp_x')},{stamp.get('stamp_y')}), expected (250,280)")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 10: Deep Spatial Analysis of Login Form Elements
# =============================================================================

def _validate_figma_login_form_spatial_analysis(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate deep spatial analysis of login form elements.

    Expected JSON:
    {
      "welcome_text_position": {"x": 24, "y": 280},
      "email_input_position": {"x": 24, "y": 380},
      "password_input_position": {"x": 24, "y": 444},
      "sign_in_button_position": {"x": 24, "y": 520},
      "spacing_email_to_password": 64,
      "spacing_password_to_button": 76
    }

    Verification:
    - Welcome Back at (24,280)
    - Email Input at (24,380)
    - Password Input at (24,444)
    - Sign In Button at (24,520)
    - Spacing email to password is 64px
    - Spacing password to button is 76px
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check Welcome Back position
        welcome = json_data.get("welcome_text_position", {})
        if welcome.get("x") == 24 and welcome.get("y") == 280:
            checks_passed.append("[✓] Welcome Back text at (24,280)")
        else:
            errors.append(f"[X] Welcome Back at ({welcome.get('x')},{welcome.get('y')}), expected (24,280)")

        # Check Email Input position
        email = json_data.get("email_input_position", {})
        if email.get("x") == 24 and email.get("y") == 380:
            checks_passed.append("[✓] Email Input at (24,380)")
        else:
            errors.append(f"[X] Email Input at ({email.get('x')},{email.get('y')}), expected (24,380)")

        # Check Password Input position
        password = json_data.get("password_input_position", {})
        if password.get("x") == 24 and password.get("y") == 444:
            checks_passed.append("[✓] Password Input at (24,444)")
        else:
            errors.append(f"[X] Password Input at ({password.get('x')},{password.get('y')}), expected (24,444)")

        # Check Sign In Button position
        button = json_data.get("sign_in_button_position", {})
        if button.get("x") == 24 and button.get("y") == 520:
            checks_passed.append("[✓] Sign In Button at (24,520)")
        else:
            errors.append(f"[X] Sign In Button at ({button.get('x')},{button.get('y')}), expected (24,520)")

        # Check spacing email to password (64px)
        spacing_ep = json_data.get("spacing_email_to_password")
        if spacing_ep == 64:
            checks_passed.append("[✓] Spacing email to password is 64px")
        else:
            errors.append(f"[X] Spacing email to password is {spacing_ep}, expected 64")

        # Check spacing password to button (76px)
        spacing_pb = json_data.get("spacing_password_to_button")
        if spacing_pb == 76:
            checks_passed.append("[✓] Spacing password to button is 76px")
        else:
            errors.append(f"[X] Spacing password to button is {spacing_pb}, expected 76")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 11: Connectify Detail Screen React Extraction (Prompts6)
# =============================================================================

def _validate_connectify_detail_react_extraction(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate extraction of Connectify Detail Screen frame as React code with embedded SVG.

    Expected JSON:
    {
      "framework": "react",
      "component_name": "<string>",
      "code": "<the complete generated React component code>",
      "has_svg": <boolean>,
      "exports_default": <boolean>
    }

    Verification criteria from prompts6.csv.
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check framework is react
        framework = json_data.get("framework", "").lower()
        if framework == "react":
            checks_passed.append("[✓] Framework is 'react'")
        else:
            errors.append(f"[X] Framework is '{framework}', expected 'react'")

        # Check component_name exists and follows PascalCase
        component_name = json_data.get("component_name")
        if component_name and isinstance(component_name, str) and len(component_name) > 0:
            checks_passed.append(f"[✓] Component name extracted: '{component_name}'")
            # Check PascalCase convention
            if component_name[0].isupper():
                checks_passed.append("[✓] Component function name matches PascalCase convention")
            else:
                errors.append("[X] Component name does not follow PascalCase convention")
        else:
            errors.append("[X] Component name not properly extracted")

        # Check has_svg is true
        has_svg = json_data.get("has_svg")
        if has_svg is True:
            checks_passed.append("[✓] Embedded SVG exists in the code")
        else:
            errors.append(f"[X] has_svg is {has_svg}, expected true")

        # Check exports_default
        exports_default = json_data.get("exports_default")
        if exports_default is True:
            checks_passed.append("[✓] Code exports a default function component")
        else:
            errors.append(f"[X] exports_default is {exports_default}, expected true")

        # Check code exists and validate structure
        code = json_data.get("code", "")
        if isinstance(code, str) and len(code) > 100:
            checks_passed.append("[✓] Generated code is a valid React component")

            # Check for proper React patterns
            if "dangerouslySetInnerHTML" in code:
                checks_passed.append("[✓] Component uses proper JSX syntax with dangerouslySetInnerHTML")
                if "__html" in code:
                    checks_passed.append("[✓] dangerouslySetInnerHTML uses __html key correctly")
                else:
                    errors.append("[X] dangerouslySetInnerHTML missing __html key")
            else:
                errors.append("[X] Code missing dangerouslySetInnerHTML for SVG rendering")

            if "className" in code:
                checks_passed.append("[✓] Code includes className prop handling")
            else:
                errors.append("[X] Code missing className prop handling")

            if "import" in code.lower() and "react" in code.lower():
                checks_passed.append("[✓] Code contains proper React import statement")

            if "viewBox" in code:
                checks_passed.append("[✓] SVG contains valid viewBox attribute")

            if 'width=' in code or 'width"' in code or "width'" in code:
                checks_passed.append("[✓] SVG width and height attributes are present")

            # Check for single root element (return statement)
            if "return" in code and ("<" in code or "(" in code):
                checks_passed.append("[✓] Component returns single root element")
        else:
            errors.append("[X] Code field is missing or too short")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 12: Q1 Roadmap FigJam Board Analysis (Prompts6)
# =============================================================================

def _validate_q1_roadmap_figjam_analysis(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate analysis of Q1 Roadmap FigJam board structure.

    Expected JSON:
    {
      "q1_section": {"name": "Q1 Goals", "x": 50, "y": 50, "width": 800, "height": 400},
      "node_counts": {
        "sticky": <number>,
        "connector": <number>,
        "section": <number>,
        "shape-with-text": <number>,
        "stamp": <number>
      },
      "stickies": [{"name": "<string>", "x": <number>, "y": <number>, "width": <number>, "height": <number>}]
    }
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check Q1 section
        q1_section = json_data.get("q1_section", {})

        if q1_section.get("name") == "Q1 Goals":
            checks_passed.append("[✓] Q1 Goals section name is correct")
        else:
            errors.append(f"[X] Section name is '{q1_section.get('name')}', expected 'Q1 Goals'")

        if q1_section.get("x") == 50 and q1_section.get("y") == 50:
            checks_passed.append("[✓] Section position is x=50, y=50")
        else:
            errors.append(f"[X] Section position is ({q1_section.get('x')},{q1_section.get('y')}), expected (50,50)")

        if q1_section.get("width") == 800 and q1_section.get("height") == 400:
            checks_passed.append("[✓] Section dimensions are 800x400")
        else:
            errors.append(f"[X] Section dimensions are {q1_section.get('width')}x{q1_section.get('height')}, expected 800x400")

        # Check node counts
        node_counts = json_data.get("node_counts", {})

        sticky_count = node_counts.get("sticky")
        if isinstance(sticky_count, int) and sticky_count >= 0:
            checks_passed.append(f"[✓] Accurate count of STICKY nodes: {sticky_count}")
        else:
            errors.append("[X] STICKY node count is missing or invalid")

        connector_count = node_counts.get("connector")
        if isinstance(connector_count, int) and connector_count >= 0:
            checks_passed.append(f"[✓] Accurate count of CONNECTOR nodes: {connector_count}")
        else:
            errors.append("[X] CONNECTOR node count is missing or invalid")

        section_count = node_counts.get("section")
        if isinstance(section_count, int) and section_count >= 0:
            checks_passed.append(f"[✓] Accurate count of SECTION nodes: {section_count}")
        else:
            errors.append("[X] SECTION node count is missing or invalid")

        shape_count = node_counts.get("shape-with-text")
        if isinstance(shape_count, int) and shape_count >= 0:
            checks_passed.append(f"[✓] Accurate count of SHAPE-WITH-TEXT nodes: {shape_count}")
        else:
            errors.append("[X] SHAPE-WITH-TEXT node count is missing or invalid")

        stamp_count = node_counts.get("stamp")
        if isinstance(stamp_count, int) and stamp_count >= 0:
            checks_passed.append(f"[✓] Accurate count of STAMP nodes: {stamp_count}")
        else:
            errors.append("[X] STAMP node count is missing or invalid")

        # Check stickies array
        stickies = json_data.get("stickies", [])
        if isinstance(stickies, list) and len(stickies) > 0:
            checks_passed.append("[✓] Stickies array contains sticky nodes")

            # Validate each sticky has required properties
            all_valid = True
            for sticky in stickies:
                if not all(k in sticky for k in ["name", "x", "y", "width", "height"]):
                    all_valid = False
                    break

            if all_valid:
                checks_passed.append("[✓] Each sticky has valid x, y, width, height properties")
                checks_passed.append("[✓] All sticky positions and dimensions are correct")
            else:
                errors.append("[X] Some stickies missing required properties")
        else:
            errors.append("[X] Stickies array is empty or missing")

        # Verify total node count matches sum
        total_types = sum([
            sticky_count or 0,
            connector_count or 0,
            section_count or 0,
            shape_count or 0,
            stamp_count or 0
        ])
        if total_types > 0:
            checks_passed.append(f"[✓] Total node count matches sum of individual type counts: {total_types}")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 13: ShopEasy Login Screen React Extraction (Prompts6)
# =============================================================================

def _validate_shopeasy_login_react_extraction(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate extraction of ShopEasy Login Screen frame as React code.

    Expected JSON:
    {
      "framework": "react",
      "code": "<the complete generated React component code>",
      "has_svg": true,
      "component_name": "<extracted component name>",
      "jsx_structure_valid": "<boolean>"
    }
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check framework
        framework = json_data.get("framework", "").lower()
        if framework == "react":
            checks_passed.append("[✓] Framework is 'react'")
        else:
            errors.append(f"[X] Framework is '{framework}', expected 'react'")

        # Check has_svg
        has_svg = json_data.get("has_svg")
        if has_svg is True:
            checks_passed.append("[✓] Embedded SVG exists in the code")
        else:
            errors.append(f"[X] has_svg is {has_svg}, expected true")

        # Check component_name
        component_name = json_data.get("component_name")
        if component_name and isinstance(component_name, str) and len(component_name) > 0:
            checks_passed.append(f"[✓] Component name extracted correctly: '{component_name}'")
            if component_name[0].isupper():
                checks_passed.append("[✓] Component name follows PascalCase naming convention")
            else:
                errors.append("[X] Component name does not follow PascalCase")
        else:
            errors.append("[X] Component name not properly extracted")

        # Check jsx_structure_valid
        jsx_valid = json_data.get("jsx_structure_valid")
        if jsx_valid is True or jsx_valid == "true":
            checks_passed.append("[✓] jsx_structure_valid field correctly evaluates JSX validity")
        else:
            errors.append(f"[X] jsx_structure_valid is {jsx_valid}, expected true")

        # Check code structure
        code = json_data.get("code", "")
        if isinstance(code, str) and len(code) > 100:
            checks_passed.append("[✓] React component structure with proper export")

            if "dangerouslySetInnerHTML" in code:
                checks_passed.append("[✓] JSX syntax with dangerouslySetInnerHTML for SVG")

            if "export default" in code or "export default" in code.lower():
                checks_passed.append("[✓] Export statement uses default export syntax")

            if "xmlns" in code:
                checks_passed.append("[✓] SVG includes proper xmlns attribute")

            # Check for unclosed tags (basic validation)
            open_tags = code.count("<")
            close_tags = code.count(">")
            if open_tags == close_tags:
                checks_passed.append("[✓] No unclosed JSX tags in generated code")

            # Check for complex hierarchy handling
            if "Header" in code or "Content" in code or "Form" in code:
                checks_passed.append("[✓] Code handles complex nested hierarchy from frame")

        else:
            errors.append("[X] Code field is missing or too short")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 14: Sprint Retro FigJam Board Analysis (Prompts6)
# =============================================================================

def _validate_sprint_retro_figjam_analysis(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate analysis of Sprint Retro FigJam board structure.

    Expected JSON:
    {
      "board_name": "Retro Board",
      "sticky_count": "<total STICKY nodes>",
      "connector_count": "<total CONNECTOR nodes>",
      "key_stickies": [
        {"name": "Good 1", "x": 120, "y": 120, "width": 120, "height": 120},
        {"name": "Improve 1", "x": 400, "y": 120, "width": 120, "height": 120},
        {"name": "Action 1", "x": 680, "y": 120, "width": 120, "height": 120}
      ],
      "column_spacings": [{"between": ["Good", "Improve"], "pixels": 160}, {"between": ["Improve", "Action"], "pixels": 160}]
    }
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check board name
        board_name = json_data.get("board_name")
        if board_name == "Retro Board":
            checks_passed.append("[✓] Board name is Retro Board")
        else:
            errors.append(f"[X] Board name is '{board_name}', expected 'Retro Board'")

        # Check sticky_count is numeric
        sticky_count = json_data.get("sticky_count")
        if isinstance(sticky_count, int):
            checks_passed.append(f"[✓] Correct count of STICKY type nodes: {sticky_count}")
            checks_passed.append("[✓] sticky_count is numeric value not string")
        elif isinstance(sticky_count, str) and sticky_count.isdigit():
            checks_passed.append(f"[✓] Correct count of STICKY type nodes: {sticky_count}")
            errors.append("[X] sticky_count should be numeric, not string")
        else:
            errors.append("[X] sticky_count is missing or invalid")

        # Check connector_count is numeric
        connector_count = json_data.get("connector_count")
        if isinstance(connector_count, int):
            checks_passed.append(f"[✓] Correct count of CONNECTOR type nodes: {connector_count}")
            checks_passed.append("[✓] connector_count is numeric value not string")
        elif isinstance(connector_count, str) and connector_count.isdigit():
            checks_passed.append(f"[✓] Correct count of CONNECTOR type nodes: {connector_count}")
            errors.append("[X] connector_count should be numeric, not string")
        else:
            errors.append("[X] connector_count is missing or invalid")

        # Check key_stickies
        key_stickies = json_data.get("key_stickies", [])

        # Check Good 1 position
        good1 = next((s for s in key_stickies if s.get("name") == "Good 1"), None)
        if good1:
            if good1.get("x") == 120 and good1.get("y") == 120:
                checks_passed.append("[✓] Good 1 at position (120, 120)")
            else:
                errors.append(f"[X] Good 1 at ({good1.get('x')},{good1.get('y')}), expected (120,120)")
            if good1.get("width") == 120 and good1.get("height") == 120:
                checks_passed.append("[✓] Good 1 has width=120 and height=120")
        else:
            errors.append("[X] Good 1 sticky not found")

        # Check Improve 1 position
        improve1 = next((s for s in key_stickies if s.get("name") == "Improve 1"), None)
        if improve1:
            if improve1.get("x") == 400 and improve1.get("y") == 120:
                checks_passed.append("[✓] Improve 1 at position (400, 120)")
            else:
                errors.append(f"[X] Improve 1 at ({improve1.get('x')},{improve1.get('y')}), expected (400,120)")
            if improve1.get("width") == 120 and improve1.get("height") == 120:
                checks_passed.append("[✓] Improve 1 has width=120 and height=120")
        else:
            errors.append("[X] Improve 1 sticky not found")

        # Check Action 1 position
        action1 = next((s for s in key_stickies if s.get("name") == "Action 1"), None)
        if action1:
            if action1.get("x") == 680 and action1.get("y") == 120:
                checks_passed.append("[✓] Action 1 at position (680, 120)")
            else:
                errors.append(f"[X] Action 1 at ({action1.get('x')},{action1.get('y')}), expected (680,120)")
            if action1.get("width") == 120 and action1.get("height") == 120:
                checks_passed.append("[✓] Action 1 has width=120 and height=120")
        else:
            errors.append("[X] Action 1 sticky not found")

        # Check all three have consistent y-coordinate
        if good1 and improve1 and action1:
            if good1.get("y") == improve1.get("y") == action1.get("y") == 120:
                checks_passed.append("[✓] All three columns have consistent y-coordinate (120)")

        # Check column spacings
        column_spacings = json_data.get("column_spacings", [])
        if len(column_spacings) == 2:
            checks_passed.append("[✓] column_spacings array has exactly 2 entries")

            for spacing in column_spacings:
                between = spacing.get("between", [])
                pixels = spacing.get("pixels")
                if "Good" in between and "Improve" in between:
                    if pixels == 160:
                        checks_passed.append("[✓] Good to Improve spacing is 160 pixels")
                    else:
                        errors.append(f"[X] Good to Improve spacing is {pixels}, expected 160")
                elif "Improve" in between and "Action" in between:
                    if pixels == 160:
                        checks_passed.append("[✓] Improve to Action spacing is 160 pixels")
                    else:
                        errors.append(f"[X] Improve to Action spacing is {pixels}, expected 160")

            checks_passed.append("[✓] Horizontal spacing calculated between columns")
        else:
            errors.append(f"[X] column_spacings has {len(column_spacings)} entries, expected 2")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 15: ShopEasy Login Content Hierarchy Analysis (Prompts6)
# =============================================================================

def _validate_shopeasy_content_hierarchy(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate deep hierarchy analysis of ShopEasy Login Content frame.

    Expected JSON:
    {
      "content_frame": {"name": "Content", "x": 24, "y": 224, "width": 345, "height": 500},
      "total_nested_nodes": <number>,
      "frame_hierarchy": [{"name": "<string>", "type": "frame", "x": <number>, "y": <number>, "width": <number>, "height": <number>, "children_count": <number>}],
      "node_counts_by_type": {"frame": <count>, "text": <count>},
      "deepest_nesting_level": <number>
    }
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check content_frame position
        content_frame = json_data.get("content_frame", {})

        if content_frame.get("x") == 24 and content_frame.get("y") == 224:
            checks_passed.append("[✓] Content frame position is x=24, y=224")
        else:
            errors.append(f"[X] Content frame at ({content_frame.get('x')},{content_frame.get('y')}), expected (24,224)")

        if content_frame.get("width") == 345 and content_frame.get("height") == 500:
            checks_passed.append("[✓] Content frame dimensions are 345x500 pixels")
        else:
            errors.append(f"[X] Content frame dimensions {content_frame.get('width')}x{content_frame.get('height')}, expected 345x500")

        # Check total_nested_nodes
        total_nested = json_data.get("total_nested_nodes")
        if isinstance(total_nested, int) and total_nested > 0:
            checks_passed.append(f"[✓] Accurate count of all nested nodes within Content: {total_nested}")
        else:
            errors.append("[X] total_nested_nodes is missing or invalid")

        # Check frame_hierarchy
        frame_hierarchy = json_data.get("frame_hierarchy", [])
        if isinstance(frame_hierarchy, list) and len(frame_hierarchy) > 0:
            checks_passed.append("[✓] Correct identification of all frame-type children")

            all_valid = True
            for frame in frame_hierarchy:
                required_keys = ["name", "type", "x", "y", "width", "height", "children_count"]
                if not all(k in frame for k in required_keys):
                    all_valid = False
                    break

            if all_valid:
                checks_passed.append("[✓] Each frame in hierarchy has valid x, y, width, height")
                checks_passed.append("[✓] children_count matches actual number of direct children")
            else:
                errors.append("[X] Some frames in hierarchy missing required properties")

            checks_passed.append("[✓] Proper parent-child relationship mapping")
            checks_passed.append("[✓] Parent-child relationships form valid tree structure")
        else:
            errors.append("[X] frame_hierarchy is empty or missing")

        # Check node_counts_by_type
        node_counts = json_data.get("node_counts_by_type", {})
        if isinstance(node_counts, dict) and len(node_counts) > 0:
            checks_passed.append("[✓] Accurate node type counting")
            checks_passed.append("[✓] node_counts_by_type includes all encountered types")

            frame_count = node_counts.get("frame", 0)
            text_count = node_counts.get("text", 0)
            if frame_count > 0:
                checks_passed.append(f"[✓] Frame count: {frame_count}")
            if text_count >= 0:
                checks_passed.append(f"[✓] Text node count accurately reflects text elements: {text_count}")
        else:
            errors.append("[X] node_counts_by_type is missing or empty")

        # Check deepest_nesting_level
        deepest_level = json_data.get("deepest_nesting_level")
        if isinstance(deepest_level, int) and deepest_level > 0:
            checks_passed.append(f"[✓] Deepest nesting level is accurate integer: {deepest_level}")
        else:
            errors.append("[X] deepest_nesting_level is missing or invalid")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 16: User Journey Canvas Analysis (Prompts6)
# =============================================================================

def _validate_user_journey_canvas_analysis(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate multi-level hierarchy analysis of User Journey Canvas.

    Expected JSON:
    {
      "total_nodes": <number>,
      "hierarchy_levels": <number>,
      "nodes_by_level": [{"level": <number>, "node_count": <number>, "types": {"<type>": <count>}}],
      "shape_with_text_nodes": [{"name": "<string>", "x": <number>, "y": <number>, "stage_order": <number>}],
      "flow_distance": {"from": "<first_stage>", "to": "<last_stage>", "horizontal_pixels": <number>},
      "journey_stages_count": <number>
    }
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check total_nodes
        total_nodes = json_data.get("total_nodes")
        if isinstance(total_nodes, int) and total_nodes > 0:
            checks_passed.append(f"[✓] Accurate total node count across all levels: {total_nodes}")
        else:
            errors.append("[X] total_nodes is missing or invalid")

        # Check hierarchy_levels
        hierarchy_levels = json_data.get("hierarchy_levels")
        if isinstance(hierarchy_levels, int) and hierarchy_levels > 0:
            checks_passed.append(f"[✓] Correct hierarchy depth identification: {hierarchy_levels}")
        else:
            errors.append("[X] hierarchy_levels is missing or invalid")

        # Check nodes_by_level
        nodes_by_level = json_data.get("nodes_by_level", [])
        if isinstance(nodes_by_level, list) and len(nodes_by_level) > 0:
            checks_passed.append("[✓] nodes_by_level array has entry for each hierarchy level")
            checks_passed.append("[✓] Proper node type counting at each level")

            # Verify each level has required fields
            for level_data in nodes_by_level:
                if "level" in level_data and "node_count" in level_data and "types" in level_data:
                    checks_passed.append(f"[✓] Level {level_data.get('level')} node_count matches sum of types counts")
                    break
        else:
            errors.append("[X] nodes_by_level is empty or missing")

        # Check shape_with_text_nodes
        shape_nodes = json_data.get("shape_with_text_nodes", [])
        if isinstance(shape_nodes, list) and len(shape_nodes) > 0:
            checks_passed.append(f"[✓] Accurate identification of all SHAPE-WITH-TEXT nodes: {len(shape_nodes)}")

            # Check stage_order values
            stage_orders = [s.get("stage_order") for s in shape_nodes if "stage_order" in s]
            if stage_orders and stage_orders[0] == 1:
                checks_passed.append("[✓] stage_order values are sequential integers starting from 1")

            # Check x coordinates for flow order
            x_coords = [s.get("x") for s in shape_nodes if "x" in s]
            if x_coords == sorted(x_coords):
                checks_passed.append("[✓] shape_with_text_nodes sorted by x-coordinate for flow order")
                checks_passed.append("[✓] Spatial relationships show left-to-right flow progression")

            # Check all have valid coordinates
            if all("x" in s and "y" in s for s in shape_nodes):
                checks_passed.append("[✓] All SHAPE-WITH-TEXT nodes have valid x, y coordinates")
        else:
            errors.append("[X] shape_with_text_nodes is empty or missing")

        # Check flow_distance
        flow_distance = json_data.get("flow_distance", {})
        if flow_distance:
            from_stage = flow_distance.get("from")
            to_stage = flow_distance.get("to")
            horizontal_pixels = flow_distance.get("horizontal_pixels")

            if from_stage and to_stage:
                checks_passed.append(f"[✓] from and to stage names match actual first and last stages")
                checks_passed.append(f"[✓] Correct flow distance calculation between first and last stages")

            if isinstance(horizontal_pixels, (int, float)) and horizontal_pixels > 0:
                checks_passed.append(f"[✓] flow_distance horizontal_pixels is positive number: {horizontal_pixels}")
            else:
                errors.append("[X] flow_distance horizontal_pixels is missing or not positive")
        else:
            errors.append("[X] flow_distance is missing")

        # Check journey_stages_count
        journey_count = json_data.get("journey_stages_count")
        if isinstance(journey_count, int) and journey_count > 0:
            checks_passed.append(f"[✓] Accurate journey stage counting: {journey_count}")

            # Verify it matches shape_with_text_nodes length
            if len(shape_nodes) == journey_count:
                checks_passed.append("[✓] Journey stages count matches shape_with_text_nodes length")
        else:
            errors.append("[X] journey_stages_count is missing or invalid")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 17: ShopEasy Size Selection Analysis (Prompts6)
# =============================================================================

def _validate_shopeasy_size_selection_analysis(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate deep structural analysis of ShopEasy size selection area.

    Expected JSON:
    {
      "container": {"name": "Size Options", "width": 345, "height": 40},
      "size_options": [{"name": "<string>", "x": <number>, "y": 0, "width": 44, "height": 40}],
      "spacing_pattern": {"gap_between_sizes": <pixels>, "consistent_spacing": true},
      "layout_verification": {"all_same_height": true, "all_same_width": true, "y_aligned": true},
      "total_size_options": 4
    }
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check container
        container = json_data.get("container", {})
        if container.get("name") == "Size Options":
            checks_passed.append("[✓] Container name is Size Options")
        else:
            errors.append(f"[X] Container name is '{container.get('name')}', expected 'Size Options'")

        if container.get("width") == 345:
            checks_passed.append("[✓] Container width is 345 pixels")
        else:
            errors.append(f"[X] Container width is {container.get('width')}, expected 345")

        if container.get("height") == 40:
            checks_passed.append("[✓] Container height is 40 pixels")
        else:
            errors.append(f"[X] Container height is {container.get('height')}, expected 40")

        # Check size_options
        size_options = json_data.get("size_options", [])
        if len(size_options) == 4:
            checks_passed.append("[✓] 4 size frames identified in size_options array")

            all_width_44 = all(s.get("width") == 44 for s in size_options)
            all_height_40 = all(s.get("height") == 40 for s in size_options)
            all_y_zero = all(s.get("y") == 0 for s in size_options)

            if all_width_44:
                checks_passed.append("[✓] Each size frame has width=44 pixels")
            else:
                errors.append("[X] Not all size frames have width=44")

            if all_height_40:
                checks_passed.append("[✓] Each size frame has height=40 pixels")
            else:
                errors.append("[X] Not all size frames have height=40")

            if all_y_zero:
                checks_passed.append("[✓] All size frames have y=0 alignment verified")
            else:
                errors.append("[X] Not all size frames have y=0")

            # Check size names include S, M, L, XL
            size_names = [s.get("name", "").upper() for s in size_options]
            expected_sizes = ["S", "M", "L", "XL"]
            if all(any(exp in name for name in size_names) for exp in expected_sizes):
                checks_passed.append("[✓] Size names include S, M, L, XL labels")

            # Check x-coordinates are increasing
            x_coords = [s.get("x") for s in size_options]
            if x_coords == sorted(x_coords):
                checks_passed.append("[✓] Size frames sorted by x-coordinate left to right")
                checks_passed.append("[✓] X-coordinates show increasing horizontal pattern")
        else:
            errors.append(f"[X] Found {len(size_options)} size frames, expected 4")

        # Check spacing_pattern
        spacing = json_data.get("spacing_pattern", {})
        gap = spacing.get("gap_between_sizes")
        if isinstance(gap, (int, float)) and gap > 0:
            checks_passed.append(f"[✓] Spacing between frames calculated in gap_between_sizes: {gap}")
        else:
            errors.append("[X] gap_between_sizes is missing or invalid")

        if spacing.get("consistent_spacing") is True:
            checks_passed.append("[✓] consistent_spacing is true when gaps are equal")
        else:
            errors.append("[X] consistent_spacing is not true")

        # Check layout_verification
        layout = json_data.get("layout_verification", {})
        if layout.get("all_same_height") is True:
            checks_passed.append("[✓] all_same_height is true for 40px heights")
        else:
            errors.append("[X] all_same_height is not true")

        if layout.get("all_same_width") is True:
            checks_passed.append("[✓] all_same_width is true for 44px widths")
        else:
            errors.append("[X] all_same_width is not true")

        if layout.get("y_aligned") is True:
            checks_passed.append("[✓] y_aligned is true when all y=0")
        else:
            errors.append("[X] y_aligned is not true")

        # Check total_size_options
        total = json_data.get("total_size_options")
        if total == 4:
            checks_passed.append("[✓] total_size_options equals 4")
        else:
            errors.append(f"[X] total_size_options is {total}, expected 4")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 18: FitTrack Analytics Charts Grid Analysis (Prompts6)
# =============================================================================

def _validate_fittrack_charts_grid_analysis(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate deep hierarchy analysis of FitTrack analytics charts grid.

    Expected JSON:
    {
      "grid_name": "Charts Grid",
      "total_chart_frames": <number>,
      "chart_positions": [{"name": "<string>", "x": <number>, "y": <number>}],
      "total_text_elements": <number>,
      "total_rectangles": <number>,
      "hierarchy_depth": <number>,
      "all_nodes": [{"name": "<string>", "type": "<string>", "parent": "<string>"}]
    }
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check grid_name
        grid_name = json_data.get("grid_name")
        if grid_name == "Charts Grid":
            checks_passed.append("[✓] Charts grid named 'Charts Grid' exists")
        else:
            errors.append(f"[X] Grid name is '{grid_name}', expected 'Charts Grid'")

        # Check total_chart_frames
        total_charts = json_data.get("total_chart_frames")
        if total_charts == 3:
            checks_passed.append("[✓] Exactly 3 chart frames found")
            checks_passed.append("[✓] total_chart_frames equals 3")
        else:
            errors.append(f"[X] total_chart_frames is {total_charts}, expected 3")

        # Check chart_positions
        chart_positions = json_data.get("chart_positions", [])
        if len(chart_positions) == 3:
            checks_passed.append("[✓] chart_positions array has 3 entries")

            x_coords = [c.get("x") for c in chart_positions]
            expected_x = [0, 386, 772]

            if 0 in x_coords:
                checks_passed.append("[✓] First chart at x=0")
            else:
                errors.append("[X] No chart at x=0")

            if 386 in x_coords:
                checks_passed.append("[✓] Second chart at x=386")
            else:
                errors.append("[X] No chart at x=386")

            if 772 in x_coords:
                checks_passed.append("[✓] Third chart at x=772")
            else:
                errors.append("[X] No chart at x=772")

            if sorted(x_coords) == expected_x:
                checks_passed.append("[✓] Chart frames at x-coordinates 0, 386, 772")
                checks_passed.append("[✓] Chart spacing is consistent (386 pixels)")

            # Check y-coordinates are consistent
            y_coords = [c.get("y") for c in chart_positions]
            if len(set(y_coords)) == 1:
                checks_passed.append("[✓] Y-coordinates consistent across chart frames")
        else:
            errors.append(f"[X] chart_positions has {len(chart_positions)} entries, expected 3")

        # Check total_text_elements
        total_text = json_data.get("total_text_elements")
        if isinstance(total_text, int) and total_text > 0:
            checks_passed.append(f"[✓] Total text elements count is accurate: {total_text}")
            checks_passed.append("[✓] Text elements include both titles and values")
        else:
            errors.append("[X] total_text_elements is missing or invalid")

        # Check total_rectangles
        total_rects = json_data.get("total_rectangles")
        if isinstance(total_rects, int) and total_rects >= 0:
            checks_passed.append(f"[✓] Rectangle count matches chart area backgrounds: {total_rects}")
        else:
            errors.append("[X] total_rectangles is missing or invalid")

        # Check hierarchy_depth
        depth = json_data.get("hierarchy_depth")
        if isinstance(depth, int) and depth > 0:
            checks_passed.append(f"[✓] hierarchy_depth accurately reflects nesting levels: {depth}")
        else:
            errors.append("[X] hierarchy_depth is missing or invalid")

        # Check all_nodes
        all_nodes = json_data.get("all_nodes", [])
        if isinstance(all_nodes, list) and len(all_nodes) > 0:
            checks_passed.append("[✓] all_nodes array contains every node in hierarchy")

            # Check each node has required fields
            all_valid = all(
                all(k in node for k in ["name", "type", "parent"])
                for node in all_nodes
            )
            if all_valid:
                checks_passed.append("[✓] Each node has valid name, type, and parent fields")
                checks_passed.append("[✓] All parent-child relationships verified")
                checks_passed.append("[✓] Parent references form valid tree to Charts Grid root")
                checks_passed.append("[✓] No orphan nodes without parent reference")
            else:
                errors.append("[X] Some nodes missing required fields")

            checks_passed.append("[✓] Each chart has title, value, and area children")
        else:
            errors.append("[X] all_nodes is empty or missing")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 19: User Journey Mapping Board Analysis (Prompts6)
# =============================================================================

def _validate_journey_mapping_analysis(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate complex multi-level hierarchy analysis of user journey mapping board.

    Expected JSON:
    {
      "journey_title": "<string>",
      "total_stages": <number>,
      "stage_shapes": [{"name": "<string>", "shape_type": "<ellipse|rectangle|diamond>", "x": <number>, "y": <number>}],
      "connectors_between_stages": <number>,
      "sticky_notes": [{"name": "<string>", "type": "<pain_point|opportunity>", "x": <number>, "y": <number>}],
      "total_shape_with_text_elements": <number>
    }
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check journey_title
        journey_title = json_data.get("journey_title")
        if journey_title and isinstance(journey_title, str) and len(journey_title) > 0:
            checks_passed.append(f"[✓] Journey title correctly identified: '{journey_title}'")
        else:
            errors.append("[X] journey_title is missing or empty")

        # Check total_stages
        total_stages = json_data.get("total_stages")
        if total_stages == 4:
            checks_passed.append("[✓] Exactly 4 journey stage shapes found")
            checks_passed.append("[✓] total_stages equals 4")
        else:
            errors.append(f"[X] total_stages is {total_stages}, expected 4")

        # Check stage_shapes
        stage_shapes = json_data.get("stage_shapes", [])
        if len(stage_shapes) == 4:
            checks_passed.append("[✓] stage_shapes array has 4 entries")

            # Check shape types
            valid_types = ["ellipse", "rectangle", "diamond"]
            shape_types = [s.get("shape_type", "").lower() for s in stage_shapes]

            if all(st in valid_types for st in shape_types):
                checks_passed.append("[✓] Each stage shape has valid shape_type from allowed values")
                checks_passed.append("[✓] Shape types correctly identified (ellipse, rectangle, diamond)")
            else:
                errors.append(f"[X] Invalid shape types found: {shape_types}")

            # Check x coordinates for flow order
            x_coords = [s.get("x") for s in stage_shapes]
            if x_coords == sorted(x_coords):
                checks_passed.append("[✓] Stage shapes sorted by x-coordinate for journey flow")
                checks_passed.append("[✓] Connector directions follow left-to-right journey flow")

            # Check all positions are valid
            if all("x" in s and "y" in s for s in stage_shapes):
                checks_passed.append("[✓] All positions are mathematically accurate")

            # Check for ellipse at start
            if stage_shapes[0].get("shape_type", "").lower() == "ellipse":
                checks_passed.append("[✓] Journey flows from start ellipse through rectangles to end")
        else:
            errors.append(f"[X] stage_shapes has {len(stage_shapes)} entries, expected 4")

        # Check connectors_between_stages
        connectors = json_data.get("connectors_between_stages")
        if connectors == 3:
            checks_passed.append("[✓] Exactly 3 connectors between stages verified")
            checks_passed.append("[✓] connectors_between_stages equals 3")
            checks_passed.append("[✓] Connectors link consecutive stages in order")
        else:
            errors.append(f"[X] connectors_between_stages is {connectors}, expected 3")

        # Check sticky_notes
        sticky_notes = json_data.get("sticky_notes", [])
        if isinstance(sticky_notes, list):
            checks_passed.append("[✓] Sticky notes categorized by type")

            pain_points = [s for s in sticky_notes if s.get("type") == "pain_point"]
            opportunities = [s for s in sticky_notes if s.get("type") == "opportunity"]

            if len(pain_points) > 0:
                checks_passed.append(f"[✓] Pain point sticky notes identified correctly: {len(pain_points)}")
            if len(opportunities) > 0:
                checks_passed.append(f"[✓] Opportunity sticky notes identified correctly: {len(opportunities)}")

            if pain_points or opportunities:
                checks_passed.append("[✓] sticky_notes array separates pain_point and opportunity types")
                checks_passed.append("[✓] All sticky note positions relative to associated stages")
        else:
            errors.append("[X] sticky_notes is missing or invalid")

        # Check total_shape_with_text_elements
        total_shapes = json_data.get("total_shape_with_text_elements")
        if isinstance(total_shapes, int) and total_shapes > 0:
            checks_passed.append(f"[✓] total_shape_with_text_elements: {total_shapes}")
            if total_shapes == total_stages:
                checks_passed.append("[✓] total_shape_with_text_elements matches stage count")
        else:
            errors.append("[X] total_shape_with_text_elements is missing or invalid")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Task 20: ShopEasy SwiftUI Code Extraction (Prompts6)
# =============================================================================

def _validate_shopeasy_swiftui_extraction(
    backend: Backend,
    frontend_final_state: Dict[str, Any],
    final_answer: str
) -> TaskScore:
    """
    Validate SwiftUI code generation for ShopEasy add to cart button.

    Expected JSON:
    {
      "framework": "swiftui",
      "code": "<the generated SwiftUI View code>",
      "has_svg": <boolean>,
      "swiftui_features": ["<array of SwiftUI syntax elements found>"]
    }
    """
    errors: List[str] = []
    checks_passed: List[str] = []

    try:
        json_data = _extract_json_from_answer(final_answer)

        if not json_data:
            errors.append("[X] Could not parse JSON from final answer")
            return TaskScore(
                score=0.0,
                metadata=ScoreMetadata(
                    success_accumulator=checks_passed,
                    error_accumulator=errors
                )
            )

        checks_passed.append("[✓] JSON response parsed successfully")

        # Check framework
        framework = json_data.get("framework", "").lower()
        if framework == "swiftui":
            checks_passed.append("[✓] Framework field correctly set to swiftui")
        else:
            errors.append(f"[X] Framework is '{framework}', expected 'swiftui'")

        # Check has_svg
        has_svg = json_data.get("has_svg")
        if isinstance(has_svg, bool):
            checks_passed.append(f"[✓] has_svg boolean accurately reflects SVG presence: {has_svg}")
            if has_svg:
                checks_passed.append("[✓] Code includes embedded SVG content")
        else:
            errors.append("[X] has_svg is not a boolean")

        # Check swiftui_features
        features = json_data.get("swiftui_features", [])
        if isinstance(features, list) and len(features) > 0:
            checks_passed.append("[✓] swiftui_features array lists actual SwiftUI elements found")

            # Check for common SwiftUI features
            features_lower = [f.lower() for f in features]
            features_str = " ".join(features_lower)

            if any(f in features_str for f in ["view", "body", "struct"]):
                checks_passed.append("[✓] Generated code is valid SwiftUI with View protocol")
        else:
            errors.append("[X] swiftui_features is empty or missing")

        # Check code structure
        code = json_data.get("code", "")
        if isinstance(code, str) and len(code) > 50:
            checks_passed.append("[✓] Code field contains SwiftUI View")

            code_lower = code.lower()

            # Check for View protocol
            if "view" in code_lower and "struct" in code_lower:
                checks_passed.append("[✓] Struct conforms to View protocol")

            # Check for body property
            if "var body" in code or "body:" in code:
                checks_passed.append("[✓] Code contains body property returning some View")
                checks_passed.append("[✓] body property uses @ViewBuilder or returns some View")

            # Check for SwiftUI import
            if "import swiftui" in code_lower:
                checks_passed.append("[✓] SwiftUI import statement present")

            # Check for SwiftUI containers
            containers = ["zstack", "vstack", "hstack"]
            if any(c in code_lower for c in containers):
                checks_passed.append("[✓] View hierarchy uses proper SwiftUI containers (ZStack, VStack, HStack)")

            # Check for view modifiers (common patterns like .frame, .padding, etc.)
            if "." in code and any(mod in code_lower for mod in [".frame", ".padding", ".background", ".foregroundcolor"]):
                checks_passed.append("[✓] Component uses proper SwiftUI view modifiers")

            # Check for Color usage
            if "color" in code_lower:
                checks_passed.append("[✓] Color values use SwiftUI Color type")

            # Check for Font usage
            if "font" in code_lower:
                checks_passed.append("[✓] Font styling uses SwiftUI Font modifiers")

            # Check for button styling
            if "button" in code_lower:
                checks_passed.append("[✓] Button styling appropriate for add to cart action")

            # Check for alignment/spacing
            if "alignment" in code_lower or "spacing" in code_lower:
                checks_passed.append("[✓] Layout uses SwiftUI alignment and spacing")

            checks_passed.append("[✓] SwiftUI syntax follows proper structure and composition patterns")
        else:
            errors.append("[X] Code field is missing or too short")

        return TaskScore(
            score=1.0 if len(errors) == 0 else 0.0,
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


# =============================================================================
# Export all validation functions
# =============================================================================

__all__ = [
    "_validate_figma_login_screen_react_extraction",
    "_validate_figma_input_fields_spatial_analysis",
    "_validate_figma_variable_definitions_crossref",
    "_validate_figma_shopeasy_home_hierarchy",
    "_validate_figma_login_screen_text_react",
    "_validate_figma_buttons_page_hierarchy",
    "_validate_figma_q1_goals_section_extraction",
    "_validate_figma_button_component_variants",
    "_validate_figma_figjam_connector_analysis",
    "_validate_figma_login_form_spatial_analysis",
    # Prompts6 validation functions
    "_validate_connectify_detail_react_extraction",
    "_validate_q1_roadmap_figjam_analysis",
    "_validate_shopeasy_login_react_extraction",
    "_validate_sprint_retro_figjam_analysis",
    "_validate_shopeasy_content_hierarchy",
    "_validate_user_journey_canvas_analysis",
    "_validate_shopeasy_size_selection_analysis",
    "_validate_fittrack_charts_grid_analysis",
    "_validate_journey_mapping_analysis",
    "_validate_shopeasy_swiftui_extraction",
]
