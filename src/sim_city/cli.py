"""SimCity CLI - AI-powered startup simulation engine."""

import typer
from rich.console import Console

app = typer.Typer(
    name="sim-city",
    help="AI-powered startup simulation engine. Simulate your startup's journey with AI agents.",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()


@app.callback()
def main():
    """
    SimCity: AI-powered startup simulation engine.

    Simulate your startup's journey through AI-driven stakeholder interactions.
    """
    pass


@app.command()
def version():
    """Show the current version."""
    from sim_city import __version__
    console.print(f"[bold cyan]SimCity[/bold cyan] v{__version__}")


if __name__ == "__main__":
    app()
