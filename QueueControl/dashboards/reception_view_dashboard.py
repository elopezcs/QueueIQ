import os
import sys

QUEUE_SIMULATION_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "queue-simulation")
)
if QUEUE_SIMULATION_DIR not in sys.path:
    sys.path.insert(0, QUEUE_SIMULATION_DIR)

from queue_simulation import render_unified_dashboard


def main() -> None:
    render_unified_dashboard(default_dashboard="reception")


if __name__ == "__main__":
    main()
