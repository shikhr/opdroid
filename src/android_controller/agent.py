"""Main agent loop implementing the observe-think-act cycle."""

import json
from typing import Any, Optional
import time
import re

import litellm
litellm.suppress_debug_info = True
try:
    from rich.console import Console, Group
except ImportError:
    from rich.console import Console
    try:
        from rich.group import Group
    except ImportError:
        # Fallback if Group is completely missing (unlikely but safe)
        class Group:
            def __init__(self, *args): self.args = args
            def __rich__(self): return "\n".join(str(a) for a in self.args)

from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner

from android_controller.client import AndroidController
from android_controller.tools import TOOL_DEFINITIONS, ToolExecutor
from android_controller.utils import resize_image, image_to_data_url
from android_controller.grid import overlay_grid


# Default system prompt for the Android operator agent
SYSTEM_PROMPT = """You are an expert Android device operator. Your task is to control an Android device to accomplish user objectives.

You receive screenshots of the device screen overlaid with a labeled grid. The grid has:
- COLUMNS labeled with letters (A, B, C, ...) from left to right
- ROWS labeled with numbers (1, 2, 3, ...) from top to bottom

The exact number of columns and rows will be shown with each screenshot.

To interact with the screen, specify grid cells like 'E10' (column E, row 10).

## How to think step-by-step:
1. Analyze the current screen state from the screenshot
2. Identify which grid cell contains the UI element you need to interact with
3. Choose the appropriate action using grid cell references

## IMPORTANT GUIDELINES:
- Use tap(cell="E10") to tap on a specific grid cell
- Use swipe(start_cell="E15", end_cell="E5") to scroll (swipe up to scroll down)
- Wait for content to load after navigating (use wait tool)
- If you need to type, first tap the input field to focus it
- Look at the grid labels on the screenshot to identify the correct cell

When the task is complete, call the task_complete tool with a summary.
If the task is impossible, call the task_impossible tool with an explanation."""


class Agent:
    """LLM-powered agent for autonomous Android device control."""
    
    def __init__(
        self,
        controller: AndroidController,
        model: str = "gpt-4o",
        max_iterations: int = 50,
        console: Optional[Console] = None
    ):
        """Initialize the agent.
        
        Args:
            controller: AndroidController for device interaction.
            model: LiteLLM model identifier (e.g., "gpt-4o", "claude-sonnet-4-20250514").
            max_iterations: Maximum number of observe-think-act cycles.
            console: Rich console for output (creates one if not provided).
        """
        self.controller = controller
        self.model = model
        self.max_iterations = max_iterations
        self.console = console or Console()
        self.tool_executor = ToolExecutor(controller)
        self.message_history: list[dict[str, Any]] = []
        self._task_finished = False
        self._task_result: Optional[str] = None
    
    def run(self, objective: str) -> str:
        """Run the agent to accomplish the given objective.
        
        Args:
            objective: The task to accomplish (e.g., "Open YouTube and search for cats").
        
        Returns:
            Final status message (completion summary or failure reason).
        """
        self.console.print(f"\n[bold blue]🎯 Objective:[/bold blue] {objective}\n")
        
        # Initialize message history with system prompt
        self.message_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        
        # Add initial user message with objective
        self.message_history.append({
            "role": "user",
            "content": f"Your objective: {objective}\n\nI will now show you the current screen state."
        })
        
        self._task_finished = False
        self._task_result = None
        
        for iteration in range(1, self.max_iterations + 1):
            self.console.print(f"[dim]─── Iteration {iteration}/{self.max_iterations} ───[/dim]")
            
            try:
                # Step 1: Observe - capture and process screenshot
                observation = self._observe()
                
                # Step 2: Think - get LLM response
                response = self._think(observation)
                
                # Step 3: Act - execute tool calls
                self._act(response, observation)
                
                # Check if task is complete
                if self._task_finished:
                    self.console.print(
                        f"\n[bold green]✅ Task Complete:[/bold green] {self._task_result}"
                    )
                    return self._task_result or "Task completed"
                    
            except Exception as e:
                self.console.print(f"[bold red]❌ Error:[/bold red] {e}")
                raise
        
        # Max iterations reached
        final_msg = f"Max iterations ({self.max_iterations}) reached without completion"
        self.console.print(f"\n[bold yellow]⚠️ {final_msg}[/bold yellow]")
        return final_msg
    
    def _observe(self) -> dict[str, Any]:
        """Capture the current screen state with grid overlay.
        
        Returns:
            Dict with screenshot data URL and screen dimensions.
        """
        screenshot = self.controller.get_screenshot()
        
        # Resize for efficiency (max 800px on longest edge for better grid visibility)
        resized = resize_image(screenshot, max_size=800)
        
        # Overlay grid on the resized image
        gridded, grid_cols, grid_rows = overlay_grid(resized)
        
        # Get dimensions for coordinate reference
        original_size = screenshot.size
        resized_size = resized.size
        
        # Convert gridded image to data URL
        data_url = image_to_data_url(gridded, format="PNG")
        
        self.console.print(Panel(
            f"[dim]Screen: {original_size[0]}x{original_size[1]} → {resized_size[0]}x{resized_size[1]} | Grid: {grid_cols}x{grid_rows}[/dim]",
            title="[yellow]👁️ Observation[/yellow]",
            border_style="yellow",
            expand=False
        ))
        
        return {
            "data_url": data_url,
            "original_size": original_size,
            "resized_size": resized_size,
            "grid_cols": grid_cols,
            "grid_rows": grid_rows
        }
    
    def _think(self, observation: dict[str, Any]) -> Any:
        """Get LLM response for the current state with retry logic for rate limits.
        
        Args:
            observation: Screenshot observation data.
        
        Returns:
            LiteLLM completion response.
        """
        # Build vision message with screenshot
        grid_cols = observation["grid_cols"]
        grid_rows = observation["grid_rows"]
        last_col_letter = chr(ord('A') + grid_cols - 1) if grid_cols <= 26 else 'Z+'
        
        vision_message = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Current screen with {grid_cols}x{grid_rows} grid "
                        f"(columns A-{last_col_letter}, rows 1-{grid_rows}). "
                        f"What action should I take next?"
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": observation["data_url"],
                        "detail": "high"
                    }
                }
            ]
        }
        
        self.message_history.append(vision_message)
        
        max_retries = 3
        base_delay = 5
        
        for attempt in range(max_retries + 1):
            try:
                # Rate limit mitigation: wait 1 second before each request
                time.sleep(1)
                
                # Limit image history to avoid 5-image limit on Groq
                self._manage_history()
                
                with Live(Spinner("dots", text="[yellow]🧠 Thinking...[/yellow]"), console=self.console, refresh_per_second=10, transient=True):
                    # Call LLM with tools
                    response = litellm.completion(
                        model=self.model,
                        messages=self.message_history,
                        tools=TOOL_DEFINITIONS,
                        tool_choice="auto"
                    )
                
                # Log thinking
                assistant_message = response.choices[0].message
                if assistant_message.content:
                    self.console.print(Panel(
                        f"[cyan]{assistant_message.content}[/cyan]",
                        title="[cyan]🧠 Thought[/cyan]",
                        border_style="cyan"
                    ))
                
                # Add assistant response to history
                self.message_history.append(assistant_message.model_dump())
                
                return response

            except litellm.RateLimitError as e:
                # ... existing rate limit code ...
                if attempt == max_retries:
                    self.console.print("[bold red]❌ Max retries reached for rate limit.[/bold red]")
                    raise
                
                error_msg = str(e)
                wait_time = base_delay * (2 ** attempt)
                
                seconds_match = re.search(r"try again in ([\d.]+)s", error_msg)
                if seconds_match:
                    wait_time = float(seconds_match.group(1)) + 1
                
                self.console.print(
                    f"[bold yellow]⏳ Rate limit hit. Waiting {wait_time:.2f}s before retry...[/bold yellow]"
                )
                time.sleep(wait_time)
                continue
            
            except Exception:
                raise
    
    def _manage_history(self, max_images: int = 5) -> None:
        """Limit the number of images in the message history.
        
        Groq and some other providers have limits on the number of images per request.
        This method converts older vision messages to text-only descriptions.
        """
        image_count = 0
        # Iterate backwards to keep the most recent images
        for i in range(len(self.message_history) - 1, -1, -1):
            msg = self.message_history[i]
            if isinstance(msg.get("content"), list):
                has_image = any(item.get("type") == "image_url" for item in msg["content"])
                if has_image:
                    image_count += 1
                    if image_count > max_images:
                        # Convert to text-only
                        text_parts = [
                            item["text"] for item in msg["content"] 
                            if item.get("type") == "text"
                        ]
                        msg["content"] = " ".join(text_parts) + " [Screenshot removed for history management]"
    
    def _act(self, response: Any, observation: dict[str, Any]) -> None:
        """Execute tool calls from the LLM response.
        
        Args:
            response: LiteLLM completion response.
            observation: The observation used for this thought.
        """
        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls
        
        if not tool_calls:
            return

        # Set screen dimensions on tool executor for coordinate conversion
        self.tool_executor.original_size = observation["original_size"]
        self.tool_executor.resized_size = observation["resized_size"]
        
        action_results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}
            
            action_line = f"[green]🔧 [{tool_name}][/green] {json.dumps(arguments)}"
            
            try:
                result = self.tool_executor.execute(tool_name, arguments)
                action_line += f"\n[dim]   → {result}[/dim]"
                
                # Check for task completion
                if result.startswith("TASK_COMPLETE:"):
                    self._task_finished = True
                    self._task_result = result.replace("TASK_COMPLETE: ", "")
                elif result.startswith("TASK_IMPOSSIBLE:"):
                    self._task_finished = True
                    self._task_result = result.replace("TASK_IMPOSSIBLE: ", "")
                
                # Append tool result to history
                self.message_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
                
            except Exception as e:
                error_msg = f"Error executing {tool_name}: {e}"
                action_line += f"\n[red]   ❌ {error_msg}[/red]"
                
                self.message_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": error_msg
                })
            
            action_results.append(action_line)
        
        self.console.print(Panel(
            Group(*action_results),
            title="[green]🔧 Actions[/green]",
            border_style="green"
        ))
