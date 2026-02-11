#!/usr/bin/env python3
"""Generate SVG/PNG screenshots of Why-Combinator CLI output for README documentation."""
import subprocess
import sys
import os

# Ensure we're in the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

# Ensure venv python is used
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, "assets", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Import Rich for SVG capture (must be available in the running interpreter)
from rich.console import Console
from rich.text import Text


def capture(filename: str, title: str, cmd_args: list, width: int = 100):
    """Run a CLI command and capture its output as SVG."""
    output_path = os.path.join(SCREENSHOTS_DIR, filename)
    full_cmd = [VENV_PYTHON, "-m", "why_combinator.cli"] + cmd_args
    env = {**os.environ, "COLUMNS": str(width), "FORCE_COLOR": "1", "TERM": "xterm-256color"}
    result = subprocess.run(full_cmd, capture_output=True, text=True, env=env, cwd=PROJECT_ROOT)
    output = result.stdout + result.stderr

    console = Console(record=True, width=width, force_terminal=True)
    for line in output.splitlines():
        console.print(Text.from_ansi(line))
    svg = console.export_svg(title=title)
    with open(output_path, "w") as f:
        f.write(svg)
    print(f"  Saved: {output_path}")


def convert_svg_to_png():
    """Convert all SVGs to PNGs using rsvg-convert."""
    for f in sorted(os.listdir(SCREENSHOTS_DIR)):
        if f.endswith(".svg") and not f.startswith("_"):
            svg_path = os.path.join(SCREENSHOTS_DIR, f)
            png_path = svg_path.replace(".svg", ".png")
            subprocess.run(["rsvg-convert", "-o", png_path, svg_path], check=True)
            print(f"  Converted: {png_path}")


# Existing simulation IDs
SIM_ID_1 = "33d4049e-37f0-4129-bc6a-4c74b666a6a5"
SIM_ID_2 = "0072aede-0199-4b7b-ac04-680ca18c17e7"
SIM_ID_3 = "a06754d0-c4b5-4493-aa56-d7b2fa2c8e53"
AGENT_ID = "d1b6b642-5409-4a94-b755-7c0c4e458966"  # Early Adopter

if __name__ == "__main__":
    print("=" * 60)
    print("Generating Why-Combinator Screenshots")
    print(f"  Python: {VENV_PYTHON}")
    print(f"  Output: {SCREENSHOTS_DIR}")
    print("=" * 60)

    # 1. Main CLI help
    print("\n[1/20] Main help...")
    capture("01_main_help.svg", "why-combinator --help", ["--help"])

    # 2. Simulate subcommand help
    print("\n[2/20] Simulate help...")
    capture("02_simulate_help.svg", "why-combinator simulate --help", ["simulate", "--help"])

    # 3. Tutorial panel
    print("\n[3/20] Tutorial...")
    capture("03_tutorial.svg", "why-combinator simulate tutorial", ["simulate", "tutorial"], width=90)

    # 4. Dry-run SaaS template
    print("\n[4/20] SaaS template dry-run...")
    capture("04_saas_dry_run.svg", "why-combinator simulate new --template saas --dry-run",
            ["simulate", "new", "--template", "saas", "--name", "CloudSync Pro",
             "--industry", "SaaS", "--description", "B2B collaboration platform",
             "--stage", "mvp", "--dry-run"])

    # 5. Dry-run Fintech template
    print("\n[5/20] Fintech template dry-run...")
    capture("05_fintech_dry_run.svg", "why-combinator simulate new --template fintech --dry-run",
            ["simulate", "new", "--template", "fintech", "--name", "PayFlow",
             "--industry", "Fintech", "--description", "Next-gen payment processing",
             "--stage", "launch", "--dry-run"])

    # 6. Dry-run Hardware template
    print("\n[6/20] Hardware template dry-run...")
    capture("06_hardware_dry_run.svg", "why-combinator simulate new --template hardware --dry-run",
            ["simulate", "new", "--template", "hardware", "--name", "SenseAI Device",
             "--industry", "Hardware", "--description", "Smart IoT sensor platform",
             "--stage", "idea", "--dry-run"])

    # 7. Dry-run Marketplace template
    print("\n[7/20] Marketplace template dry-run...")
    capture("07_marketplace_dry_run.svg", "why-combinator simulate new --template marketplace --dry-run",
            ["simulate", "new", "--template", "marketplace", "--name", "TradeHub",
             "--industry", "Marketplace", "--description", "B2B procurement marketplace",
             "--stage", "growth", "--dry-run"])

    # 8. List simulations
    print("\n[8/20] Simulation list...")
    capture("08_simulation_list.svg", "why-combinator simulate list", ["simulate", "list"])

    # 9. Simulation history
    print("\n[9/20] Simulation history...")
    capture("09_simulation_history.svg", "why-combinator simulate history", ["simulate", "history"])

    # 10. Simulation status
    print("\n[10/20] Simulation status...")
    capture("10_simulation_status.svg", "why-combinator simulate status",
            ["simulate", "status", SIM_ID_1], width=110)

    # 11. Agent inspection
    print("\n[11/20] Agent inspection...")
    capture("11_agent_inspect.svg", "why-combinator simulate inspect --agent-id",
            ["simulate", "inspect", SIM_ID_1, "--agent-id", AGENT_ID])

    # 12. Interaction logs (all)
    print("\n[12/20] Interaction logs...")
    capture("12_logs_all.svg", "why-combinator simulate logs --limit 12",
            ["simulate", "logs", SIM_ID_1, "--limit", "12"], width=110)

    # 13. Filtered logs (buy actions)
    print("\n[13/20] Filtered logs (buy)...")
    capture("13_logs_buy.svg", "why-combinator simulate logs --type buy",
            ["simulate", "logs", SIM_ID_1, "--type", "buy", "--limit", "10"], width=110)

    # 14. Filtered logs (complain actions)
    print("\n[14/20] Filtered logs (complain)...")
    capture("14_logs_complain.svg", "why-combinator simulate logs --type complain",
            ["simulate", "logs", SIM_ID_1, "--type", "complain", "--limit", "10"], width=110)

    # 15. Compare simulations
    print("\n[15/20] Compare simulations...")
    capture("15_compare.svg", "why-combinator simulate compare",
            ["simulate", "compare", SIM_ID_1, SIM_ID_2])

    # 16. JSON status output
    print("\n[16/20] JSON status output...")
    capture("16_json_status.svg", "why-combinator simulate status --json",
            ["simulate", "status", SIM_ID_3, "--json"], width=120)

    # 17. JSON logs output
    print("\n[17/20] JSON logs output...")
    capture("17_json_logs.svg", "why-combinator simulate logs --json",
            ["simulate", "logs", SIM_ID_1, "--limit", "3", "--json"], width=120)

    # 18. Export as markdown
    print("\n[18/20] Export as markdown...")
    capture("18_export_md.svg", "why-combinator simulate export --format md",
            ["simulate", "export", SIM_ID_1, "--format", "md", "--output", "/tmp/wc-screenshots"])

    # 19. Export as CSV
    print("\n[19/20] Export as CSV...")
    capture("19_export_csv.svg", "why-combinator simulate export --format csv",
            ["simulate", "export", SIM_ID_1, "--format", "csv", "--output", "/tmp/wc-screenshots"])

    # 20. Run help (showing all model/speed/duration options)
    print("\n[20/20] Run help...")
    capture("20_run_help.svg", "why-combinator simulate run --help",
            ["simulate", "run", "--help"], width=100)

    # Convert SVGs to PNGs
    print("\n" + "=" * 60)
    print("Converting SVGs to PNGs...")
    print("=" * 60)
    convert_svg_to_png()

    print("\n" + "=" * 60)
    count = len([f for f in os.listdir(SCREENSHOTS_DIR) if f.endswith('.png')])
    print(f"Done! {count} PNGs generated in:")
    print(f"  {SCREENSHOTS_DIR}")
    print("=" * 60)
