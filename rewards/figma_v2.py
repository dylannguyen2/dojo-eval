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
]
