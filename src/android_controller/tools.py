"""Tool definitions for LLM function calling."""

from typing import Any, Callable, Optional
import time

from android_controller.client import AndroidController
from android_controller.grid import grid_cell_to_pixels, CELL_SIZE


# OpenAI-compatible function calling schema definitions
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "tap",
            "description": (
                "Simulates a finger tap at the specified grid cell. "
                "The screen is overlaid with a grid where columns are labeled with letters (A, B, C, ...) "
                "and rows are labeled with numbers (1, 2, 3, ...). Specify the cell to tap like 'E10' or 'A1'. "
                "Use this to click buttons, icons, or any UI element."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cell": {
                        "type": "string",
                        "description": "Grid cell to tap (e.g., 'E10', 'A1', 'I20')"
                    }
                },
                "required": ["cell"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tap_sequence",
            "description": (
                "Taps multiple grid cells in sequence. Use this when you need to tap several buttons on the same screen. "
                "This is more efficient than calling tap() multiple times."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cells": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of grid cells to tap in order (e.g., ['B22', 'E22', 'K16', 'B22'])"
                    },
                    "delay_ms": {
                        "type": "number",
                        "description": "Delay between taps in milliseconds (default: 500)",
                        "default": 500
                    }
                },
                "required": ["cells"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "swipe",
            "description": (
                "Simulates a swipe gesture from one grid cell to another. "
                "Use this to scroll through content, dismiss notifications, or navigate. "
                "Common patterns: swipe from E15 to E5 to scroll down, swipe between columns to switch pages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_cell": {
                        "type": "string",
                        "description": "Starting grid cell (e.g., 'E15')"
                    },
                    "end_cell": {
                        "type": "string",
                        "description": "Ending grid cell (e.g., 'E5')"
                    },
                    "duration_ms": {
                        "type": "number",
                        "description": "Duration of swipe in milliseconds (default: 300)",
                        "default": 300
                    }
                },
                "required": ["start_cell", "end_cell"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "input_text",
            "description": (
                "Types the specified text into the currently focused input field. "
                "Make sure an input field is focused (by tapping it first) before calling this. "
                "This will type the text character by character."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to type into the focused input field"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_home",
            "description": (
                "Presses the HOME button to return to the home screen. "
                "Use this to exit apps or return to the launcher."
            ),
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_back",
            "description": (
                "Presses the BACK button to go back to the previous screen. "
                "Use this to navigate backwards, close dialogs, or cancel actions."
            ),
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_enter",
            "description": (
                "Presses the ENTER key. Use this to submit forms, confirm searches, "
                "or send messages after typing text."
            ),
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_recent_apps",
            "description": (
                "Presses the RECENT APPS button to show the app switcher. "
                "Use this to switch between recently used apps."
            ),
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "launch_app",
            "description": (
                "Launches an app by its package name. "
                "Common package names: 'com.android.settings' (Settings), "
                "'com.google.android.youtube' (YouTube), 'com.android.chrome' (Chrome), "
                "'com.whatsapp' (WhatsApp), 'com.google.android.gm' (Gmail)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "package": {
                        "type": "string",
                        "description": "The package name of the app to launch"
                    }
                },
                "required": ["package"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": (
                "Wait for a specified number of seconds before taking the next action. "
                "Use this when you need to wait for content to load, animations to complete, "
                "or apps to start up."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",
                        "description": "Number of seconds to wait (can be decimal, e.g., 1.5)"
                    }
                },
                "required": ["seconds"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_complete",
            "description": (
                "Call this when you have successfully completed the user's requested task. "
                "Provide a brief summary of what was accomplished."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of what was accomplished"
                    }
                },
                "required": ["summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_impossible",
            "description": (
                "Call this if you determine that the task cannot be completed. "
                "Explain why the task is impossible or blocked."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Explanation of why the task cannot be completed"
                    }
                },
                "required": ["reason"]
            }
        }
    }
]


class ToolExecutor:
    """Executes tool calls against an AndroidController."""
    
    def __init__(self, controller: AndroidController):
        """Initialize the tool executor.
        
        Args:
            controller: AndroidController instance for device interaction.
        """
        self.controller = controller
        self._tool_map: dict[str, Callable[..., str]] = {
            "tap": self._tap,
            "tap_sequence": self._tap_sequence,
            "swipe": self._swipe,
            "input_text": self._input_text,
            "press_home": self._press_home,
            "press_back": self._press_back,
            "press_enter": self._press_enter,
            "press_recent_apps": self._press_recent_apps,
            "launch_app": self._launch_app,
            "wait": self._wait,
            "task_complete": self._task_complete,
            "task_impossible": self._task_impossible,
        }
        # Screen dimensions for coordinate scaling (set by agent before execution)
        self.original_size: Optional[tuple[int, int]] = None
        self.resized_size: Optional[tuple[int, int]] = None
    
    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name with given arguments.
        
        Args:
            tool_name: Name of the tool to execute.
            arguments: Dictionary of arguments for the tool.
        
        Returns:
            Result string from the tool execution.
        
        Raises:
            ValueError: If tool_name is not recognized.
        """
        if tool_name not in self._tool_map:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        # Coerce arguments to expected types (e.g., string "300" to int 300)
        coerced_args = self._coerce_arguments(tool_name, arguments)
        
        return self._tool_map[tool_name](**coerced_args)

    def _coerce_arguments(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Attempt to coerce argument types for better LLM resilience."""
        coerced = arguments.copy()
        
        # Define which arguments should be numeric for each tool
        numeric_params = {
            "swipe": ["duration_ms"],
            "wait": ["seconds"]
        }
        
        if tool_name in numeric_params:
            for param in numeric_params[tool_name]:
                if param in coerced and isinstance(coerced[param], str):
                    try:
                        # Try int first, then float
                        if "." in coerced[param]:
                            coerced[param] = float(coerced[param])
                        else:
                            coerced[param] = int(coerced[param])
                    except ValueError:
                        pass # Leave as is if not convertible
        
        return coerced
    
    def _cell_to_device_pixels(self, cell: str) -> tuple[int, int]:
        """Convert a grid cell to device pixel coordinates.
        
        First converts cell to resized image pixels, then scales to device pixels.
        """
        # Get pixel coordinates in resized image
        resized_x, resized_y = grid_cell_to_pixels(cell, CELL_SIZE)
        
        # Scale to original device dimensions
        if self.original_size and self.resized_size:
            scale_x = self.original_size[0] / self.resized_size[0]
            scale_y = self.original_size[1] / self.resized_size[1]
            device_x = int(resized_x * scale_x)
            device_y = int(resized_y * scale_y)
        else:
            # Fallback: assume no scaling needed
            device_x, device_y = resized_x, resized_y
        
        return device_x, device_y
    
    def _tap(self, cell: str) -> str:
        """Tap at the center of the specified grid cell."""
        x, y = self._cell_to_device_pixels(cell)
        return self.controller.tap(x, y)
    
    def _tap_sequence(self, cells: list[str], delay_ms: float = 500) -> str:
        """Tap multiple cells in sequence with delay between each."""
        results = []
        for i, cell in enumerate(cells):
            x, y = self._cell_to_device_pixels(cell)
            self.controller.tap(x, y)
            results.append(cell)
            # Add delay between taps (except after last one)
            if i < len(cells) - 1:
                time.sleep(delay_ms / 1000)
        return f"Tapped sequence: {' -> '.join(results)}"
    
    def _swipe(
        self,
        start_cell: str,
        end_cell: str,
        duration_ms: float = 300
    ) -> str:
        """Swipe from one grid cell to another."""
        start_x, start_y = self._cell_to_device_pixels(start_cell)
        end_x, end_y = self._cell_to_device_pixels(end_cell)
        return self.controller.swipe(
            start_x, start_y, end_x, end_y, int(duration_ms)
        )
    
    def _input_text(self, text: str) -> str:
        return self.controller.input_text(text)
    
    def _press_home(self) -> str:
        return self.controller.press_home()
    
    def _press_back(self) -> str:
        return self.controller.press_back()
    
    def _press_enter(self) -> str:
        return self.controller.press_enter()
    
    def _press_recent_apps(self) -> str:
        return self.controller.press_recent_apps()
    
    def _launch_app(self, package: str) -> str:
        return self.controller.launch_app(package)
    
    def _wait(self, seconds: float) -> str:
        time.sleep(seconds)
        return f"Waited {seconds} seconds"
    
    def _task_complete(self, summary: str) -> str:
        return f"TASK_COMPLETE: {summary}"
    
    def _task_impossible(self, reason: str) -> str:
        return f"TASK_IMPOSSIBLE: {reason}"
