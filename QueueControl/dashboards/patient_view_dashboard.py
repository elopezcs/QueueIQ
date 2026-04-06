import os
import sys

QUEUE_SIMULATION_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "queue-simulation")
)
if QUEUE_SIMULATION_DIR not in sys.path:
    sys.path.insert(0, QUEUE_SIMULATION_DIR)

from queue_simulation import inject_styles, load_backend_or_stop, render_dashboard_view, render_sidebar, setup_dashboard_page


def main() -> None:
    setup_dashboard_page("QueueIQ Patient View")
    backend = load_backend_or_stop()
    inject_styles()
    selected_clinic = render_sidebar(
        backend,
        title="Patient View",
        description="Track your clinic queue, wait pressure, and rush-hour outlook without intake controls.",
        allow_speed_control=True,
    )
    render_dashboard_view(
        backend,
        selected_clinic,
        badge="Patient dashboard",
        hero_title="Follow your clinic queue in real time",
        hero_description="See the current queue, estimated wait conditions, and rush-hour pressure for the selected clinic.",
        hero_panel_text=(
            f"Auto-refresh every {backend.sim_config['sim_speed']:.1f} seconds for a patient-friendly live queue view."
        ),
        show_queue_table=True,
        show_trends=False,
    )


if __name__ == "__main__":
    main()