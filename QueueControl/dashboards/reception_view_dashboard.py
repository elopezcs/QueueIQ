import os
import sys

QUEUE_SIMULATION_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "queue-simulation")
)
if QUEUE_SIMULATION_DIR not in sys.path:
    sys.path.insert(0, QUEUE_SIMULATION_DIR)

from queue_simulation import inject_styles, load_backend_or_stop, render_dashboard_view, render_sidebar, setup_dashboard_page


def main() -> None:
    setup_dashboard_page("QueueIQ Reception View")
    backend = load_backend_or_stop()
    inject_styles()
    selected_clinic = render_sidebar(
        backend,
        title="Reception View",
        description="Manage front-desk intake for the selected clinic while monitoring live queue pressure.",
        allow_add_patient=True,
        allow_speed_control=True,
    )
    render_dashboard_view(
        backend,
        selected_clinic,
        badge="Reception dashboard",
        hero_title="Front-desk intake and queue supervision",
        hero_description="Add incoming patients, monitor the active waiting room, and watch clinic flow trends as the queue evolves.",
        hero_panel_text=(
            f"Auto-refresh every {backend.sim_config['sim_speed']:.1f} seconds for the active reception queue."
        ),
        show_queue_table=True,
        show_trends=True,
        enable_reception_actions=True,
    )


if __name__ == "__main__":
    main()