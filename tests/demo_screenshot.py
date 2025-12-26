#!/usr/bin/env python3
"""Demo script to visualize what the LLM sees with grid overlay.

Captures a screenshot from the connected Android device,
resizes it, overlays a labeled grid, and saves it to files.
"""

from pathlib import Path

from PIL import ImageDraw, ImageFont

from android_controller.client import AndroidController
from android_controller.utils import resize_image
from android_controller.ui_hierarchy import parse_ui_hierarchy


# Grid configuration - square cells
CELL_SIZE = 40  # Each cell is 40x40 pixels in the resized image


def get_column_label(col: int) -> str:
    """Convert column index to letter (0=A, 1=B, ..., 25=Z, 26=AA, etc.)"""
    if col < 26:
        return chr(ord('A') + col)
    return chr(ord('A') + col // 26 - 1) + chr(ord('A') + col % 26)


def overlay_grid(image, cell_size: int = CELL_SIZE):
    """Overlay a labeled grid with square cells on the image.
    
    Args:
        image: PIL Image to overlay grid on
        cell_size: Size of each square cell in pixels
    
    Returns:
        Tuple of (new PIL Image with grid overlay, cols, rows)
    """
    img = image.copy()
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # Calculate grid dimensions based on image size (square cells)
    cols = width // cell_size
    rows = height // cell_size
    
    # Grid line style
    line_color = (255, 0, 0, 180)  # Semi-transparent red
    label_color = (255, 255, 0)    # Yellow for labels
    
    # Try to load a small font, fall back to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except (OSError, IOError):
        font = ImageFont.load_default()
    
    # Draw vertical lines and column labels
    for col in range(cols + 1):
        x = int(col * cell_size)
        draw.line([(x, 0), (x, height)], fill=line_color, width=1)
        
        # Column label at top
        if col < cols:
            label = get_column_label(col)
            label_x = int(col * cell_size + cell_size / 2 - 4)
            draw.text((label_x, 2), label, fill=label_color, font=font)
    
    # Draw horizontal lines and row labels
    for row in range(rows + 1):
        y = int(row * cell_size)
        draw.line([(0, y), (width, y)], fill=line_color, width=1)
        
        # Row label on left
        if row < rows:
            label = str(row + 1)
            label_y = int(row * cell_size + cell_size / 2 - 5)
            draw.text((2, label_y), label, fill=label_color, font=font)
    
    return img, cols, rows


def grid_cell_to_pixels(cell: str, cell_size: int = CELL_SIZE) -> tuple[int, int]:
    """Convert grid cell (e.g., 'C5') to pixel coordinates (center of cell).
    
    Args:
        cell: Grid cell like 'A1', 'C5', 'I20'
        cell_size: Size of each square cell in pixels
    
    Returns:
        (x, y) pixel coordinates at center of the cell
    """
    # Parse cell: letters for column, digits for row
    col_str = ""
    row_str = ""
    for char in cell.upper():
        if char.isalpha():
            col_str += char
        elif char.isdigit():
            row_str += char
    
    # Convert column letters to index (A=0, B=1, ..., Z=25, AA=26, etc.)
    col_idx = 0
    for char in col_str:
        col_idx = col_idx * 26 + (ord(char) - ord('A') + 1)
    col_idx -= 1  # 0-indexed
    
    row_idx = int(row_str) - 1  # 1-indexed to 0-indexed
    
    # Return center of cell
    x = int((col_idx + 0.5) * cell_size)
    y = int((row_idx + 0.5) * cell_size)
    
    return x, y


def main():
    print("📱 Connecting to device...")
    controller = AndroidController()
    
    print("📸 Capturing screenshot...")
    screenshot = controller.get_screenshot()
    original_size = screenshot.size
    
    print(f"   Original: {original_size[0]}x{original_size[1]}")
    
    # Resize exactly like the agent does
    resized = resize_image(screenshot, max_size=1024)
    resized_size = resized.size
    
    print(f"   Resized:  {resized_size[0]}x{resized_size[1]}")
    print(f"   Scale X:  {original_size[0] / resized_size[0]:.2f}x")
    print(f"   Scale Y:  {original_size[1] / resized_size[1]:.2f}x")
    
    # Create grid overlay version (returns image, cols, rows)
    gridded, cols, rows = overlay_grid(resized)
    
    print(f"\n📐 Grid: {cols}x{rows} cells (square, {CELL_SIZE}x{CELL_SIZE} pixels each)")
    
    # Demo: convert a cell to coordinates
    demo_cell = f"{get_column_label(cols // 2)}{rows // 2}"  # Middle cell
    px, py = grid_cell_to_pixels(demo_cell)
    # Scale back to original
    orig_x = int(px * original_size[0] / resized_size[0])
    orig_y = int(py * original_size[1] / resized_size[1])
    print(f"\n📍 Example: Cell '{demo_cell}' → resized ({px}, {py}) → original ({orig_x}, {orig_y})")
    
    # Capture and parse UI hierarchy
    print("\n🌲 Capturing UI hierarchy...")
    try:
        xml_raw = controller.get_ui_hierarchy()
        ui_hierarchy = parse_ui_hierarchy(xml_raw, original_size, resized_size)
        print("\n" + "=" * 60)
        print("UI HIERARCHY (minified with grid cells)")
        print("=" * 60)
        print(ui_hierarchy)
        print("=" * 60)
        
        # Save raw XML for reference
        xml_path = Path("artifacts/ui_hierarchy.xml")
        xml_path.write_text(xml_raw)
        print(f"\n📄 Raw XML saved: {xml_path.absolute()}")
        
        # Save minified version
        minified_path = Path("artifacts/ui_hierarchy_minified.txt")
        minified_path.write_text(ui_hierarchy)
        print(f"📄 Minified saved: {minified_path.absolute()}")
    except Exception as e:
        print(f"⚠️  Could not capture UI hierarchy: {e}")
    
    # Save all versions
    original_path = Path("artifacts/screenshot_original.png")
    resized_path = Path("artifacts/screenshot_resized.png")
    gridded_path = Path("artifacts/screenshot_gridded.png")
    
    screenshot.save(original_path)
    resized.save(resized_path)
    gridded.save(gridded_path)
    
    print(f"\n✅ Saved:")
    print(f"   Original:  {original_path.absolute()}")
    print(f"   Resized:   {resized_path.absolute()}")
    print(f"   With Grid: {gridded_path.absolute()}")


if __name__ == "__main__":
    main()

