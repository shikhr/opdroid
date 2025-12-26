"""Grid overlay utilities for coordinate-based screen interaction.

Provides functions to overlay a labeled grid on screenshots and convert
grid cell references (like "E10") to pixel coordinates.
"""

from PIL import Image, ImageDraw, ImageFont


# Grid configuration - square cells
CELL_SIZE = 40  # Each cell is 40x40 pixels in the resized image


def get_column_label(col: int) -> str:
    """Convert column index to letter (0=A, 1=B, ..., 25=Z, 26=AA, etc.)"""
    if col < 26:
        return chr(ord('A') + col)
    return chr(ord('A') + col // 26 - 1) + chr(ord('A') + col % 26)


def overlay_grid(image: Image.Image, cell_size: int = CELL_SIZE) -> tuple[Image.Image, int, int]:
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
        (x, y) pixel coordinates at center of the cell in the resized image
    """
    # Parse cell: letters for column, digits for row
    col_str = ""
    row_str = ""
    for char in cell.upper():
        if char.isalpha():
            col_str += char
        elif char.isdigit():
            row_str += char
    
    if not col_str or not row_str:
        raise ValueError(f"Invalid cell format: {cell}. Expected format like 'A1', 'E10', etc.")
    
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


def pixels_to_grid_cell(x: int, y: int, cell_size: int = CELL_SIZE) -> str:
    """Convert pixel coordinates to a grid cell label.
    
    Args:
        x: X coordinate in pixels
        y: Y coordinate in pixels
        cell_size: Size of each square cell in pixels
    
    Returns:
        Grid cell label like 'A1', 'E10', etc.
    """
    col_idx = x // cell_size
    row_idx = y // cell_size
    
    col_label = get_column_label(col_idx)
    row_label = str(row_idx + 1)  # 1-indexed
    
    return f"{col_label}{row_label}"
