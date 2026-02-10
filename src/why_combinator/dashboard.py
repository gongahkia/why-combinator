"""Rich Live dashboard for simulation visualization."""
import sys
import tty
import termios
import threading
from collections import deque
from typing import Dict, Any, List, Optional
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.text import Text
from rich.live import Live
from why_combinator.events import Event
from why_combinator.visualization import ascii_relationship_graph, ascii_sentiment_gauge

AGENT_AVATARS = { # ascii art per stakeholder type
    "customer": "[bold green]$[/bold green]",
    "competitor": "[bold red]X[/bold red]",
    "investor": "[bold yellow]&[/bold yellow]",
    "regulator": "[bold blue]#[/bold blue]",
    "employee": "[bold magenta]@[/bold magenta]",
    "partner": "[bold cyan]+[/bold cyan]",
    "critic": "[bold white]![/bold white]",
    "media": "[bold yellow]*[/bold yellow]",
    "supplier": "[bold green]%[/bold green]",
    "advisor": "[bold cyan]?[/bold cyan]",
}
ACTION_COLORS = {
    "buy": "green", "sell": "red", "invest": "yellow", "complain": "red",
    "post_review": "cyan", "partner": "blue", "ignore": "dim", "wait": "dim",
    "send_message": "magenta",
}

def sparkline(values: List[float], width: int = 20) -> str:
    """Generate ASCII sparkline from values."""
    if not values:
        return " " * width
    chars = " _.,:-=!#"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1.0
    recent = values[-width:]
    return "".join(chars[min(int((v - mn) / rng * (len(chars) - 1)), len(chars) - 1)] for v in recent)

def progress_bar(value: float, max_val: float = 100.0, width: int = 20) -> str:
    """ASCII progress bar."""
    ratio = min(max(value / max_val, 0), 1.0) if max_val else 0
    filled = int(ratio * width)
    return f"[{'=' * filled}{' ' * (width - filled)}] {value:.1f}/{max_val:.0f}"

class SimulationDashboard:
    """Real-time Rich Live dashboard for simulation."""
    def __init__(self, console: Console, simulation_name: str = ""):
        self.console = console
        self.simulation_name = simulation_name
        self.tick = 0
        self.sim_date = ""
        self.status = "running"
        self.agents: List[Dict[str, Any]] = []
        self.event_log: deque = deque(maxlen=15)
        self.metrics: Dict[str, List[float]] = {}
        self.sentiments: Dict[str, float] = {}
        self.relationship_edges: List[Any] = []
        self._live: Optional[Live] = None
    def build_header(self) -> Panel:
        status_color = {"running": "green", "paused": "yellow", "stopped": "red"}.get(self.status, "white")
        txt = Text()
        txt.append(f" {self.simulation_name} ", style="bold")
        txt.append(f" | Tick: {self.tick} | {self.sim_date} | ", style="dim")
        txt.append(f"[{self.status.upper()}]", style=f"bold {status_color}")
        return Panel(txt, title="Why-Combinator", border_style=status_color)
    def build_agents_panel(self) -> Panel:
        table = Table(show_header=True, header_style="bold", expand=True, padding=(0, 1))
        table.add_column("", width=2)
        table.add_column("Name", style="bold")
        table.add_column("Role")
        table.add_column("Type")
        for a in self.agents:
            avatar = AGENT_AVATARS.get(a.get("type", ""), "?")
            table.add_row(avatar, a.get("name", ""), a.get("role", ""), a.get("type", ""))
        return Panel(table, title=f"Agents ({len(self.agents)})", border_style="cyan")
    def build_event_feed(self) -> Panel:
        lines = []
        for e in self.event_log:
            color = ACTION_COLORS.get(e.get("action", ""), "white")
            agent_name = e.get("agent_name", e.get("agent_id", "?")[:8])
            lines.append(f"[{color}]{agent_name}[/{color}] {e.get('action', '?')} -> {e.get('target', '?')}: {str(e.get('content', ''))[:60]}")
        content = "\n".join(lines) if lines else "[dim]No events yet...[/dim]"
        return Panel(content, title="Event Feed", border_style="yellow")
    def build_metrics_panel(self) -> Panel:
        lines = []
        for name, values in self.metrics.items():
            current = values[-1] if values else 0.0
            spark = sparkline(values)
            lines.append(f"{name:>15}: {current:>8.2f}  {spark}")
        content = "\n".join(lines) if lines else "[dim]No metrics yet...[/dim]"
        return Panel(content, title="Metrics", border_style="green")
    def build_relationships_panel(self) -> Panel:
        content = ascii_relationship_graph(self.agents, self.relationship_edges) if self.relationship_edges else "[dim]No relationships yet...[/dim]"
        return Panel(content, title="Relationships", border_style="magenta")
    def build_sentiment_panel(self) -> Panel:
        content = ascii_sentiment_gauge(self.sentiments) if self.sentiments else "[dim]No sentiment data...[/dim]"
        return Panel(content, title="Sentiment", border_style="blue")
    def build_controls_hint(self) -> Text:
        t = Text()
        t.append(" p", style="bold yellow")
        t.append("=pause ", style="dim")
        t.append("r", style="bold green")
        t.append("=resume ", style="dim")
        t.append("q", style="bold red")
        t.append("=quit ", style="dim")
        t.append("Ctrl-C", style="bold")
        t.append("=toggle", style="dim")
        return t
    def render(self) -> Group:
        return Group(
            self.build_header(),
            self.build_agents_panel(),
            self.build_event_feed(),
            self.build_metrics_panel(),
            self.build_relationships_panel(),
            self.build_sentiment_panel(),
            self.build_controls_hint(),
        )
    def on_tick(self, event: Event):
        self.tick = event.payload.get("tick", self.tick)
        self.sim_date = event.payload.get("date", self.sim_date)
        if self._live:
            self._live.update(self.render())
    def on_interaction(self, event: Event):
        agent_id = event.payload.get("agent_id", "")
        agent_name = agent_id[:8]
        for a in self.agents:
            if a.get("id") == agent_id:
                agent_name = a.get("name", agent_id[:8])
                break
        self.event_log.append({
            "agent_id": agent_id,
            "agent_name": agent_name,
            "action": event.payload.get("action", ""),
            "target": event.payload.get("target", ""),
            "content": str(event.payload.get("outcome", ""))[:60],
        })
    def on_metric(self, event: Event):
        name = event.payload.get("metric_type", "unknown")
        val = event.payload.get("value", 0.0)
        self.metrics.setdefault(name, []).append(val)
    def on_pause(self, event: Event):
        self.status = "paused"
        if self._live:
            self._live.update(self.render())
    def on_resume(self, event: Event):
        self.status = "running"
        if self._live:
            self._live.update(self.render())
    def on_stop(self, event: Event):
        self.status = "stopped"
        if self._live:
            self._live.update(self.render())
    def on_sentiment(self, event: Event):
        self.sentiments = event.payload.get("sentiments", {})
    def on_relationships(self, event: Event):
        self.relationship_edges = event.payload.get("edges", [])
    def set_live(self, live: Live):
        self._live = live

class KeyboardListener:
    """Non-blocking keyboard input reader for terminal controls."""
    def __init__(self, engine):
        self.engine = engine
        self._thread: Optional[threading.Thread] = None
        self._running = False
    def start(self):
        if not sys.stdin.isatty():
            return
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
    def stop(self):
        self._running = False
    def _read_loop(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while self._running and self.engine.is_running:
                ch = sys.stdin.read(1)
                if ch == "p":
                    self.engine.pause()
                elif ch == "r":
                    self.engine.resume()
                elif ch == "q":
                    self.engine.stop()
                    break
        except Exception:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
