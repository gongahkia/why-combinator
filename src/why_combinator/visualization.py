"""ASCII visualization system for simulation data."""
import hashlib
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from sim_city.dashboard import AGENT_AVATARS

def ascii_relationship_graph(agents: List[Dict[str, Any]], edges: List[Tuple[str, str, Dict[str, Any]]]) -> str:
    """Build ASCII relationship graph showing connections."""
    name_map = {a["id"]: a.get("name", a["id"][:8]) for a in agents}
    lines = []
    for src, tgt, data in edges:
        src_name = name_map.get(src, src[:8])
        tgt_name = name_map.get(tgt, tgt[:8])
        rel_type = data.get("type", "neutral")
        strength = data.get("strength", 0)
        if rel_type == "alliance":
            arrow = "<=>" if strength > 0.5 else "<->"
        elif rel_type == "rivalry":
            arrow = ">X<" if strength < -0.5 else ">-<"
        else:
            arrow = "---"
        lines.append(f"  {src_name:>20} {arrow} {tgt_name:<20} ({rel_type} {strength:+.2f})")
    return "\n".join(lines) if lines else "  No relationships yet."

def ascii_interaction_indicators(interactions: List[Dict[str, Any]], limit: int = 10) -> str:
    """Text-based interaction indicators with arrows and symbols."""
    symbols = {"buy": "->$", "sell": "<-$", "invest": "->$$", "complain": "->!", "partner": "<=>", "send_message": ">>", "wait": "...", "post_review": "->*"}
    lines = []
    for inter in interactions[-limit:]:
        sym = symbols.get(inter.get("action", ""), "->")
        agent = inter.get("agent_id", "?")[:8]
        target = inter.get("target", "?")[:12]
        lines.append(f"  {agent} {sym} {target}")
    return "\n".join(lines) if lines else "  No interactions yet."

def ascii_bar_chart(data: Dict[str, float], width: int = 30, title: str = "") -> str:
    """ASCII horizontal bar chart."""
    if not data:
        return f"  {title}: No data"
    max_val = max(abs(v) for v in data.values()) or 1
    lines = [f"  {title}"] if title else []
    for label, value in data.items():
        bar_len = int(abs(value) / max_val * width)
        bar = "=" * bar_len
        lines.append(f"  {label:>15} |{bar:<{width}}| {value:.2f}")
    return "\n".join(lines)

def ascii_heatmap(data: List[List[float]], row_labels: List[str], col_labels: List[str]) -> str:
    """ASCII heatmap using block characters."""
    blocks = " ._:=!#@"
    if not data:
        return "  No data for heatmap."
    flat = [v for row in data for v in row]
    mn, mx = min(flat), max(flat)
    rng = mx - mn if mx != mn else 1.0
    header = "  " + " ".join(f"{c[:3]:>3}" for c in col_labels)
    lines = [header]
    for i, row in enumerate(data):
        label = row_labels[i][:8] if i < len(row_labels) else "?"
        cells = "".join(blocks[min(int((v - mn) / rng * (len(blocks) - 1)), len(blocks) - 1)] for v in row)
        lines.append(f"  {label:>8} |{cells}|")
    return "\n".join(lines)

def ascii_timeline(events: List[Dict[str, Any]], width: int = 60) -> str:
    """Timeline view of events with timestamps."""
    if not events:
        return "  No events to display."
    lines = []
    for e in events[-20:]: # last 20
        tick = e.get("tick", "?")
        desc = e.get("description", e.get("action", "?"))[:50]
        marker = f"T{tick:>4}"
        lines.append(f"  {marker} | {desc}")
    return "\n".join(lines)

def ascii_sentiment_gauge(sentiments: Dict[str, float]) -> str:
    """Sentiment gauge using ASCII progress bars."""
    lines = []
    for agent, score in sentiments.items():
        normalized = (score + 1) / 2 # -1..1 -> 0..1
        bar_width = 20
        filled = int(normalized * bar_width)
        bar = "-" * filled + "|" + " " * (bar_width - filled)
        emoji = "+" if score > 0.2 else ("-" if score < -0.2 else "~")
        lines.append(f"  {agent[:15]:>15} [{bar}] {score:+.2f} {emoji}")
    return "\n".join(lines) if lines else "  No sentiment data."

def ascii_logo(name: str) -> str:
    """Generate a simple ASCII art logo from simulation name."""
    h = int(hashlib.md5(name.encode()).hexdigest()[:2], 16)
    borders = ["*", "#", "=", "+", "~", "@"]
    border = borders[h % len(borders)]
    width = max(len(name) + 6, 20)
    top = border * width
    mid = f"{border}  {name.center(width - 4)}  {border}"
    return f"{top}\n{mid}\n{top}"

def color_coded_event(event_type: str) -> str:
    """Return Rich color markup for event type."""
    colors = {
        "simulation_started": "[bold green]",
        "simulation_stopped": "[bold red]",
        "simulation_paused": "[bold yellow]",
        "agent_created": "[cyan]",
        "interaction_occurred": "[white]",
        "metric_changed": "[green]",
        "agent_message": "[magenta]",
    }
    return colors.get(event_type, "[dim]")
