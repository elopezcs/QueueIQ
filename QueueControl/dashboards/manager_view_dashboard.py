import os
import sys

QUEUE_SIMULATION_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "queue-simulation")
)
if QUEUE_SIMULATION_DIR not in sys.path:
    sys.path.insert(0, QUEUE_SIMULATION_DIR)

from queue_simulation import inject_styles, load_backend_or_stop, render_dashboard_view, render_sidebar, setup_dashboard_page


def main() -> None:
    setup_dashboard_page("QueueIQ Manager View")
    backend = load_backend_or_stop()
    inject_styles()
    selected_clinic = render_sidebar(
        backend,
        title="Manager View",
        description="Tune simulation controls, staffing, and prediction behavior while monitoring operational performance.",
        allow_staffing=True,
        allow_retrain=True,
        allow_wait_time_retrain=True,
        allow_speed_control=True,
    )
    render_dashboard_view(
        backend,
        selected_clinic,
        badge="Manager dashboard",
        hero_title="Supervise staffing and demand conditions",
        hero_description="Review live clinic pressure, adjust staffing for the selected site, and track queue trends with management controls.",
        hero_panel_text=(
            f"Auto-refresh every {backend.sim_config['sim_speed']:.1f} seconds with {backend.sim_config['doctors_per_clinic'].get(selected_clinic, 1)} doctor(s) assigned to this clinic."
        ),
        show_queue_table=False,
        show_trends=True,
        show_manager_metrics=True,
    )


if __name__ == "__main__":
    main()