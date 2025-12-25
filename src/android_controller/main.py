"""Typer CLI application for opdroid."""

import os
from typing import Optional

# Load .env FIRST, before any imports that might read API keys
from dotenv import load_dotenv, find_dotenv

import typer
from rich.console import Console
from rich.panel import Panel

from android_controller.client import AndroidController
from android_controller.agent import Agent

load_dotenv(find_dotenv(usecwd=True))

# Create Typer app
app = typer.Typer(
    name="opdroid",
    help="🤖 LLM-controlled Android device automation via ADB",
    add_completion=False,
    rich_markup_mode="rich"
)

console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    model: str = typer.Option(
        None,
        "--model", "-m",
        help="LiteLLM model to use (default: gpt-4o or MODEL env var)"
    ),
    serial: Optional[str] = typer.Option(
        None,
        "--serial", "-s",
        help="Device serial number (auto-detect if not specified)"
    ),
    max_iterations: int = typer.Option(
        50,
        "--max-iterations", "-n",
        help="Maximum number of observe-think-act cycles"
    ),
    max_images: int = typer.Option(
        5,
        "--max-images", "-i",
        help="Maximum number of images to keep in context history"
    )
):
    """🤖 LLM-controlled Android device automation via ADB.
    
    If no command is provided, starts an interactive chat session.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Interactive mode
    resolved_model = _resolve_model(model)

    console.print(Panel.fit(
        "[bold blue]🤖 opdroid (Interactive Mode)[/bold blue]\n"
        f"[dim]Model: {resolved_model}[/dim]\n"
        "[dim]Type 'exit' or 'quit' to end session.[/dim]",
        border_style="blue"
    ))

    try:
        console.print("[yellow]📱 Connecting to device...[/yellow]")
        controller = AndroidController(serial=serial)
        console.print(f"[green]✓ Connected to:[/green] {controller.serial}")
        
        width, height = controller.get_screen_size()
        console.print(f"[dim]  Screen: {width}x{height}[/dim]")

        agent = Agent(
            controller=controller,
            model=resolved_model,
            max_iterations=max_iterations,
            max_images=max_images,
            console=console
        )

        while True:
            objective = console.input("\n[bold magenta]User > [/bold magenta]")
            
            if objective.lower() in ["exit", "quit", "e", "q"]:
                console.print("[yellow]Goodbye! 👋[/yellow]")
                break
            
            if not objective.strip():
                continue

            if objective.lower() == "clear":
                console.clear()
                continue

            try:
                result = agent.run(objective)
                console.print(Panel.fit(
                    f"[bold green]✅ Result:[/bold green]\n{result}",
                    border_style="green"
                ))
            except Exception as e:
                console.print(f"[bold red]❌ Error during task:[/bold red] {e}")

    except RuntimeError as e:
        console.print(f"[bold red]❌ Device Error:[/bold red] {e}")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Session ended by user[/yellow]")
        raise typer.Exit(0)



@app.command()
def devices() -> None:
    """List connected Android devices."""
    from adbutils import AdbClient
    
    client = AdbClient(host="127.0.0.1", port=5037)
    device_list = client.device_list()
    
    if not device_list:
        console.print("[yellow]No devices connected.[/yellow]")
        console.print("[dim]Make sure ADB is running: adb start-server[/dim]")
        return
    
    console.print("[bold]Connected devices:[/bold]\n")
    for device in device_list:
        console.print(f"  📱 {device.serial}")


@app.command()
def screenshot(
    output: str = typer.Option(
        "screenshot.png",
        "--output", "-o",
        help="Output file path"
    ),
    serial: Optional[str] = typer.Option(
        None,
        "--serial", "-s",
        help="Device serial number"
    )
) -> None:
    """Capture a screenshot from the device."""
    try:
        controller = AndroidController(serial=serial)
        img = controller.get_screenshot()
        img.save(output)
        console.print(f"[green]✓ Screenshot saved to:[/green] {output}")
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        raise typer.Exit(1)


def _resolve_model(model: Optional[str]) -> str:
    """Resolve the model from args, env, or default."""
    if model:
        return model
    
    env_model = os.getenv("MODEL")
    if env_model:
        return env_model
        
    return "gpt-4o"


if __name__ == "__main__":
    app()
