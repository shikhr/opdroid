"""Image processing and text sanitization utilities."""

import base64
from io import BytesIO
from PIL import Image


def resize_image(image: Image.Image, max_size: int = 1024) -> Image.Image:
    """Resize an image to fit within max_size while preserving aspect ratio.
    
    Args:
        image: PIL Image to resize.
        max_size: Maximum dimension (width or height) in pixels.
    
    Returns:
        Resized PIL Image, or original if already smaller.
    """
    width, height = image.size
    
    if width <= max_size and height <= max_size:
        return image
    
    # Calculate scaling factor to fit within max_size
    scale = min(max_size / width, max_size / height)
    new_width = int(width * scale)
    new_height = int(height * scale)
    
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def encode_image_base64(image: Image.Image, format: str = "PNG") -> str:
    """Encode a PIL Image to a base64 string.
    
    Args:
        image: PIL Image to encode.
        format: Image format (PNG, JPEG, etc.).
    
    Returns:
        Base64-encoded string of the image.
    """
    buffer = BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def image_to_data_url(image: Image.Image, format: str = "PNG") -> str:
    """Convert a PIL Image to a data URL for LLM vision APIs.
    
    Args:
        image: PIL Image to convert.
        format: Image format (PNG, JPEG).
    
    Returns:
        Data URL string (e.g., "data:image/png;base64,...")
    """
    mime_type = f"image/{format.lower()}"
    b64_data = encode_image_base64(image, format)
    return f"data:{mime_type};base64,{b64_data}"


def sanitize_text_for_shell(text: str) -> str:
    """Sanitize text for safe use in ADB shell commands.
    
    Escapes special characters that could cause shell injection.
    
    Args:
        text: Raw text to sanitize.
    
    Returns:
        Sanitized text safe for shell commands.
    """
    # Escape shell special characters
    dangerous_chars = ['\\', '"', "'", '`', '$', '!', '&', '|', ';', '<', '>']
    result = text
    for char in dangerous_chars:
        result = result.replace(char, f"\\{char}")
    return result
