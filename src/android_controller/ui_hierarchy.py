"""UI hierarchy parsing and minification utilities.

Parses Android UI hierarchy XML and converts to a compact, readable format
with grid cell coordinates instead of pixel bounds.
"""

import re
import xml.etree.ElementTree as ET
from typing import Optional

from android_controller.grid import pixels_to_grid_cell, CELL_SIZE


def parse_bounds(bounds_str: str) -> tuple[int, int, int, int]:
    """Parse bounds string like '[0,42][1080,177]' to (x1, y1, x2, y2)."""
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if not match:
        return (0, 0, 0, 0)
    return tuple(map(int, match.groups()))


def bounds_to_cell_info(
    bounds_str: str,
    original_size: tuple[int, int],
    resized_size: tuple[int, int],
    cell_size: int = CELL_SIZE
) -> tuple[str, str]:
    """Convert pixel bounds to grid cell range and click-cell.
    
    Returns two values:
    - bound: Cell range like '[H17,I20]' showing element coverage
    - click_cell: Single cell computed from center of raw pixel bounds
    
    Args:
        bounds_str: Bounds like '[0,42][1080,177]'
        original_size: Original screen size (width, height)
        resized_size: Resized image size (width, height)
        cell_size: Grid cell size in pixels
    
    Returns:
        Tuple of (bound_range, click_cell)
    """
    x1, y1, x2, y2 = parse_bounds(bounds_str)
    
    # Scale from original to resized coordinates
    scale_x = resized_size[0] / original_size[0]
    scale_y = resized_size[1] / original_size[1]
    
    x1_scaled = x1 * scale_x
    y1_scaled = y1 * scale_y
    x2_scaled = x2 * scale_x
    y2_scaled = y2 * scale_y
    
    # Find cells whose CENTERS are within the bounds for the bound range
    import math
    from android_controller.grid import get_column_label
    
    start_col = math.ceil(x1_scaled / cell_size - 0.5)
    end_col = math.ceil(x2_scaled / cell_size - 0.5) - 1
    start_row = math.ceil(y1_scaled / cell_size - 0.5)
    end_row = math.ceil(y2_scaled / cell_size - 0.5) - 1
    
    # Ensure valid range
    if end_col < start_col:
        end_col = start_col
    if end_row < start_row:
        end_row = start_row
    
    start_cell = f"{get_column_label(start_col)}{start_row + 1}"
    end_cell = f"{get_column_label(end_col)}{end_row + 1}"
    
    if start_cell == end_cell:
        bound_range = f"[{start_cell}]"
    else:
        bound_range = f"[{start_cell},{end_cell}]"
    
    # Calculate click-cell from center of RAW pixel bounds (before scaling)
    # This gives better accuracy for the actual center point
    center_x_raw = (x1 + x2) / 2
    center_y_raw = (y1 + y2) / 2
    
    # Scale the center point
    center_x_scaled = center_x_raw * scale_x
    center_y_scaled = center_y_raw * scale_y
    
    # Convert to cell
    click_col = int(center_x_scaled // cell_size)
    click_row = int(center_y_scaled // cell_size)
    click_cell = f"{get_column_label(click_col)}{click_row + 1}"
    
    return bound_range, click_cell


def _get_short_class_name(full_class: str) -> str:
    """Extract short class name from fully qualified name."""
    if '.' in full_class:
        return full_class.split('.')[-1]
    return full_class


def _collect_interactive_elements(
    element: ET.Element,
    original_size: tuple[int, int],
    resized_size: tuple[int, int],
    elements: list[str]
) -> None:
    """Recursively collect interactive elements into a flat list.
    
    Only includes elements that are clickable, scrollable, or have text/description.
    """
    # Extract attributes
    class_name = _get_short_class_name(element.get('class', 'View'))
    text = element.get('text', '')
    resource_id = element.get('resource-id', '')
    content_desc = element.get('content-desc', '')
    clickable = element.get('clickable', 'false') == 'true'
    scrollable = element.get('scrollable', 'false') == 'true'
    bounds = element.get('bounds', '')
    
    # Only include interactive or identifiable elements
    is_interactive = clickable or scrollable
    has_identity = text or content_desc
    
    if is_interactive and bounds:
        # Build element description
        parts = [f"[{class_name}]"]
        
        if text:
            parts.append(f'"{text}"')
        elif content_desc:
            parts.append(f'desc="{content_desc}"')
        
        if resource_id:
            short_id = resource_id.split('/')[-1] if '/' in resource_id else resource_id
            parts.append(f'id="{short_id}"')
        
        # Get click cell
        _, click_cell = bounds_to_cell_info(bounds, original_size, resized_size)
        parts.append(f'position="{click_cell}"')
        
        if scrollable:
            parts.append('(scrollable)')
        
        elements.append('{ ' + ' '.join(parts) + ' }')
    
    # Recurse into children
    for child in element:
        _collect_interactive_elements(child, original_size, resized_size, elements)


def parse_ui_hierarchy(
    xml_string: str,
    original_size: tuple[int, int],
    resized_size: tuple[int, int]
) -> str:
    """Parse UI hierarchy XML and convert to flat list of interactive elements.
    
    Args:
        xml_string: Raw XML from uiautomator dump
        original_size: Original screen size (width, height)
        resized_size: Resized image size (width, height)
    
    Returns:
        Flat list of clickable elements with their click cells
    """
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        return f"Error parsing UI hierarchy: {e}"
    
    elements: list[str] = []
    for child in root:
        _collect_interactive_elements(child, original_size, resized_size, elements)
    
    if not elements:
        return "No interactive elements found"
    
    return '\n'.join(elements)
