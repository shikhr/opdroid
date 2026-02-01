"""MCP (Model Context Protocol) server for Android device control.

Exposes opdroid tools as MCP tools so any LLM client can control Android devices.
"""

import asyncio
import logging
import sys
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

from android_controller.client import AndroidController
from android_controller.tools import ToolExecutor
from android_controller.utils import resize_image, encode_image_base64
from android_controller.grid import overlay_grid
from android_controller.ui_hierarchy import parse_ui_hierarchy
from android_controller.agent import SYSTEM_PROMPT


# Configure logging to stderr (stdout is used for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("opdroid.mcp")

# Global controller and executor (initialized on first use)
_controller: Optional[AndroidController] = None
_executor: Optional[ToolExecutor] = None
_device_serial: Optional[str] = None


def get_controller() -> AndroidController:
    """Get or create the AndroidController instance."""
    global _controller
    if _controller is None:
        logger.info(
            f"Connecting to device{f' ({_device_serial})' if _device_serial else ''}..."
        )
        _controller = AndroidController(serial=_device_serial)
        logger.info(f"✓ Connected to device: {_controller.serial}")
    return _controller


def get_executor() -> ToolExecutor:
    """Get or create the ToolExecutor instance."""
    global _executor
    if _executor is None:
        _executor = ToolExecutor(get_controller())
    return _executor


def set_device_serial(serial: Optional[str]) -> None:
    """Set the device serial for connection."""
    global _device_serial, _controller, _executor
    _device_serial = serial
    # Reset instances so they reconnect with new serial
    _controller = None
    _executor = None


# MCP Tool definitions
MCP_TOOLS = [
    Tool(
        name="get_screen",
        description=(
            "Capture the current Android screen state. Returns a screenshot with a labeled grid overlay "
            "(columns A-Z, rows 1-N) and a list of interactive UI elements with their tap positions. "
            "Use this to see what's on screen before taking actions."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="tap",
        description=(
            "Tap on the screen at a grid cell position. The grid uses letters for columns (A, B, C...) "
            "and numbers for rows (1, 2, 3...). Example: 'E10' means column E, row 10. "
            "First call get_screen to see available elements and their positions."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cell": {
                    "type": "string",
                    "description": "Grid cell to tap (e.g., 'E10', 'A1', 'I20')",
                }
            },
            "required": ["cell"],
        },
    ),
    Tool(
        name="tap_sequence",
        description=(
            "Tap multiple grid cells in sequence. Useful for entering numbers on keypads, "
            "tapping multiple buttons, etc."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cells": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of grid cells to tap in order (e.g., ['B22', 'E22', 'K16'])",
                },
                "delay_ms": {
                    "type": "number",
                    "description": "Delay between taps in milliseconds (default: 500)",
                    "default": 500,
                },
            },
            "required": ["cells"],
        },
    ),
    Tool(
        name="swipe",
        description=(
            "Swipe from one grid cell to another. Use for scrolling: "
            "swipe from E15 to E5 to scroll down, E5 to E15 to scroll up. "
            "Also useful for dismissing notifications or switching pages."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "start_cell": {
                    "type": "string",
                    "description": "Starting grid cell (e.g., 'E15')",
                },
                "end_cell": {
                    "type": "string",
                    "description": "Ending grid cell (e.g., 'E5')",
                },
                "duration_ms": {
                    "type": "number",
                    "description": "Duration of swipe in milliseconds (default: 300)",
                    "default": 300,
                },
            },
            "required": ["start_cell", "end_cell"],
        },
    ),
    Tool(
        name="input_text",
        description=(
            "Type text into the currently focused input field. "
            "Make sure an input field is focused (by tapping it first) before calling this."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to type into the focused input field",
                }
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="press_home",
        description="Press the HOME button to return to the home screen.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="press_back",
        description=(
            "Press the BACK button to go back to the previous screen, "
            "close dialogs, or hide the keyboard."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="press_enter",
        description="Press the ENTER key to submit forms, confirm searches, or send messages.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="press_recent_apps",
        description="Press the RECENT APPS button to show the app switcher.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="launch_app",
        description=(
            "Launch an app by its package name. Common packages: "
            "'com.android.settings' (Settings), 'com.google.android.youtube' (YouTube), "
            "'com.android.chrome' (Chrome), 'com.whatsapp' (WhatsApp)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "package": {
                    "type": "string",
                    "description": "The package name of the app to launch",
                }
            },
            "required": ["package"],
        },
    ),
    Tool(
        name="wait",
        description="Wait for a specified number of seconds (for content to load, animations, etc.).",
        inputSchema={
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "Number of seconds to wait (can be decimal, e.g., 1.5)",
                }
            },
            "required": ["seconds"],
        },
    ),
    Tool(
        name="list_devices",
        description="List all connected Android devices.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="opdroid_root_system_prompt",
        description=(
            "Get the recommended system prompt for controlling Android devices with opdroid. "
            "Use this prompt to understand how to interact with the device effectively, "
            "including the grid system, available actions, and best practices."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
]


def _capture_screen_state() -> tuple[str, str]:
    """Capture screenshot with grid overlay and UI elements list.

    Returns:
        Tuple of (base64_image, ui_elements_text)
    """
    controller = get_controller()
    executor = get_executor()

    # Capture screenshot
    screenshot = controller.get_screenshot()
    original_size = screenshot.size

    # Resize for processing
    resized = resize_image(screenshot, max_size=1024)
    resized_size = resized.size

    # Update executor with sizes for coordinate conversion
    executor.original_size = original_size
    executor.resized_size = resized_size

    # Overlay grid
    gridded_image, cols, rows = overlay_grid(resized)

    # Encode image
    image_b64 = encode_image_base64(gridded_image, format="PNG")

    # Get UI hierarchy
    try:
        ui_xml = controller.get_ui_hierarchy()
        ui_elements = parse_ui_hierarchy(ui_xml, original_size, resized_size)
    except Exception:
        ui_elements = "(Unable to parse UI hierarchy)"

    return image_b64, ui_elements


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("opdroid")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return the list of available tools."""
        return MCP_TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
        """Execute a tool and return the result."""
        logger.info(f"→ {name}({arguments if arguments else ''})")

        # Special handling for get_screen - returns image + text
        if name == "get_screen":
            try:
                image_b64, ui_elements = await asyncio.to_thread(_capture_screen_state)
                logger.info(f"  ✓ Screen captured")
                return [
                    ImageContent(type="image", data=image_b64, mimeType="image/png"),
                    TextContent(
                        type="text",
                        text=f"## Interactive UI Elements\n\n{ui_elements}\n\n"
                        f"Use the 'position' value from the elements above to tap on them.",
                    ),
                ]
            except Exception as e:
                logger.error(f"  ✗ Error capturing screen: {e}")
                return [TextContent(type="text", text=f"Error capturing screen: {e}")]

        # Special handling for list_devices
        if name == "list_devices":
            try:
                from adbutils import AdbClient

                client = AdbClient(host="127.0.0.1", port=5037)
                devices = client.device_list()
                if not devices:
                    logger.info("  ✓ No devices found")
                    return [
                        TextContent(type="text", text="No Android devices connected.")
                    ]
                device_list = "\n".join(f"- {d.serial}" for d in devices)
                logger.info(f"  ✓ Found {len(devices)} device(s)")
                return [
                    TextContent(type="text", text=f"Connected devices:\n{device_list}")
                ]
            except Exception as e:
                logger.error(f"  ✗ Error listing devices: {e}")
                return [TextContent(type="text", text=f"Error listing devices: {e}")]

        # Special handling for opdroid_root_system_prompt
        if name == "opdroid_root_system_prompt":
            logger.info("  ✓ Returned system prompt")
            return [
                TextContent(
                    type="text",
                    text=f"# Android Device Control System Prompt\n\n{SYSTEM_PROMPT}",
                )
            ]

        # All other tools use ToolExecutor
        try:
            executor = get_executor()
            controller = get_controller()

            # Ensure executor has screen size info
            if executor.original_size is None:
                executor.original_size = controller.get_screen_size()
                # Use default resized size
                executor.resized_size = (460, 1024)

            # Execute the tool in a thread to not block
            result = await asyncio.to_thread(executor.execute, name, arguments)
            logger.info(f"  ✓ {result}")
            return [TextContent(type="text", text=result)]
        except ValueError as e:
            logger.error(f"  ✗ Unknown tool: {name}")
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")
            return [TextContent(type="text", text=f"Error executing {name}: {e}")]

    return server


async def run_server(serial: Optional[str] = None) -> None:
    """Run the MCP server over stdio."""
    logger.info("🤖 opdroid MCP server starting...")
    logger.info(f"   Tools available: {len(MCP_TOOLS)}")

    if serial:
        set_device_serial(serial)
        logger.info(f"   Target device: {serial}")

    server = create_server()
    logger.info("✓ Server ready, waiting for connections...")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def main(serial: Optional[str] = None) -> None:
    """Entry point for the MCP server."""
    asyncio.run(run_server(serial))


if __name__ == "__main__":
    main()
