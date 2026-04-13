from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import requests

from queueiq_common import COMMON_LIBRARY_NOTES, QUEUEIQ_MODULES, collect_statuses

ROOT_DIR = Path(__file__).resolve().parent
RUNTIME_LOG_DIR = ROOT_DIR / "runtime-logs"
LOCAL_HOST = "127.0.0.1"
PATIENT_DASHBOARD_PORT = 8501


@dataclass(frozen=True)
class LaunchSpec:
    key: str
    name: str
    cwd: Path
    command: tuple[str, ...]
    url: str | None = None
    health_url: str | None = None
    port: int | None = None
    startup_timeout: float = 30.0
    startup_delay: float = 0.0
    helper: bool = False


@dataclass
class LaunchResult:
    spec: LaunchSpec
    process: subprocess.Popen[str] | None = None    
    log_handle: TextIO | None = None
    log_path: Path | None = None
    skipped: bool = False
    reason: str = ""


@dataclass(frozen=True)
class ProbeResult:
    reachable: bool
    detail: str


CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def _is_running_under_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


def _repo_python() -> str:
    return sys.executable


def _npm_command() -> str:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("npm was not found on PATH. Install Node.js 18+ before running the launcher.")
    return npm


def _probe(url: str | None, timeout: float = 1.5) -> ProbeResult:
    if not url:
        return ProbeResult(reachable=False, detail="No URL")

    try:
        response = requests.get(url, timeout=timeout)
        return ProbeResult(reachable=response.ok, detail=f"HTTP {response.status_code}")
    except requests.RequestException as exc:
        return ProbeResult(reachable=False, detail=exc.__class__.__name__)


def _port_is_busy(port: int | None) -> bool:
    if port is None:
        return False

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((LOCAL_HOST, port)) == 0


def _build_specs() -> tuple[LaunchSpec, ...]:
    python = _repo_python()
    npm = _npm_command()

    return (
        LaunchSpec(
            key="chatbot-backend",
            name="QueueIQ API",
            cwd=ROOT_DIR,
            command=(python, "-m", "uvicorn", "API.main:app", "--host", LOCAL_HOST, "--port", "8000"),
            url="http://127.0.0.1:8000/docs",
            health_url="http://127.0.0.1:8000/health",
            port=8000,
        ),
        LaunchSpec(
            key="chatbot-frontend",
            name="Chatbot Frontend",
            cwd=ROOT_DIR / "Chatbot" / "frontend",
            command=(npm, "run", "dev", "--", "--host", LOCAL_HOST, "--port", "5173", "--strictPort"),
            url="http://127.0.0.1:5173",
            port=5173,
            startup_timeout=45.0,
        ),
        LaunchSpec(
            key="queuecontrol-patient-dashboard",
            name="QueueControl Dashboard",
            cwd=ROOT_DIR / "QueueControl",
            command=(
                python,
                "-m",
                "streamlit",
                "run",
                "dashboards/patient_view_dashboard.py",
                "--server.address",
                LOCAL_HOST,
                "--server.port",
                str(PATIENT_DASHBOARD_PORT),
                "--server.headless",
                "true",
            ),
            url=f"http://{LOCAL_HOST}:{PATIENT_DASHBOARD_PORT}",
            port=PATIENT_DASHBOARD_PORT,
            startup_timeout=45.0,
        ),
    )


def _ensure_launcher_prereqs() -> None:
    missing_paths: list[str] = []

    if not (ROOT_DIR / "Chatbot" / "frontend" / "node_modules").exists():
        missing_paths.append("Chatbot/frontend/node_modules (run `npm install` in Chatbot/frontend)")

    if missing_paths:
        joined = "\n- ".join(missing_paths)
        raise RuntimeError(f"Launcher prerequisites are missing:\n- {joined}")


def _open_log(path: Path) -> TextIO:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a", encoding="utf-8")


def _start_process(spec: LaunchSpec) -> LaunchResult:
    log_path = RUNTIME_LOG_DIR / f"{spec.key}.log"
    log_handle = _open_log(log_path)

    env = os.environ.copy()
    local_api_base = f"http://{LOCAL_HOST}:8000"
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    env["QUEUECONTROL_API_BASE_URL"] = local_api_base
    env["QUEUEIQ_API_BASE_URL"] = local_api_base

    process = subprocess.Popen(
        spec.command,
        cwd=spec.cwd,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        creationflags=CREATE_NEW_PROCESS_GROUP,
    )

    return LaunchResult(spec=spec, process=process, log_handle=log_handle, log_path=log_path)


def _wait_for_service(result: LaunchResult) -> ProbeResult:
    spec = result.spec
    target = spec.health_url or spec.url

    if not target:
        deadline = time.time() + (spec.startup_delay or 1.0)
        while time.time() < deadline:
            if result.process and result.process.poll() is not None:
                return ProbeResult(reachable=False, detail=f"Exited with code {result.process.returncode}")
            time.sleep(0.2)

        if result.process and result.process.poll() is not None:
            return ProbeResult(reachable=False, detail=f"Exited with code {result.process.returncode}")

        return ProbeResult(reachable=True, detail="Started helper process")
    deadline = time.time() + spec.startup_timeout
    while time.time() < deadline:
        if result.process and result.process.poll() is not None:
            return ProbeResult(reachable=False, detail=f"Exited with code {result.process.returncode}")

        probe = _probe(target)
        if probe.reachable:
            return probe
        time.sleep(1.0)

    return ProbeResult(reachable=False, detail=f"Timed out waiting for {target}")


def _stop_process(result: LaunchResult) -> None:
    if result.process and result.process.poll() is None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(result.process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            result.process.terminate()
            try:
                result.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                result.process.kill()

    if result.log_handle:
        result.log_handle.close()


def run_workspace_launcher() -> int:
    try:
        _ensure_launcher_prereqs()
        specs = _build_specs()
    except Exception as exc:
        print(f"QueueIQ launcher setup failed: {exc}")
        return 1

    print("Starting QueueIQ from the repo root .venv...")
    print("This will launch Chatbot frontend/backend plus the unified QueueControl dashboard.")
    print()

    launched: list[LaunchResult] = []
    try:
        for spec in specs:
            target = spec.health_url or spec.url
            if target:
                existing = _probe(target)
                if existing.reachable:
                    print(f"[skip] {spec.name} already responding at {target} ({existing.detail})")
                    launched.append(LaunchResult(spec=spec, skipped=True, reason=existing.detail))
                    continue

            if _port_is_busy(spec.port):
                reason = f"port {spec.port} is already busy"
                print(f"[error] {spec.name} could not start because {reason}.")
                return 1

            result = _start_process(spec)
            launched.append(result)
            log_display = result.log_path.relative_to(ROOT_DIR) if result.log_path else Path('runtime-logs/unknown.log')
            print(f"[start] {spec.name} -> {' '.join(spec.command)}")
            print(f"        logs: {log_display}")

            probe = _wait_for_service(result)
            if not probe.reachable:
                print(f"[error] {spec.name} failed to become ready: {probe.detail}")
                return 1

            detail = probe.detail if target else "Started"
            print(f"[ready] {spec.name} ({detail})")

        print()
        print("QueueIQ is running.")
        print("- Chatbot frontend: http://127.0.0.1:5173")
        print("- QueueIQ API:  http://127.0.0.1:8000/docs")
        print("- Dashboards: open them from the main frontend UI")
        print()
        print("Press Ctrl+C in this terminal to stop every process started by the launcher.")

        while True:
            for result in launched:
                if result.skipped or not result.process:
                    continue
                if result.process.poll() is not None:
                    print(f"[exit] {result.spec.name} stopped unexpectedly with code {result.process.returncode}.")
                    return 1
            time.sleep(2.0)
    except KeyboardInterrupt:
        print("\nStopping QueueIQ services...")
        return 0
    finally:
        for result in reversed(launched):
            _stop_process(result)


def render_workspace_page() -> None:
    import streamlit as st

    st.set_page_config(
        page_title="QueueIQ Unified Workspace",
        page_icon="Q",
        layout="wide",
    )

    statuses = collect_statuses(QUEUEIQ_MODULES)
    live_services = sum(status.reachable for status in statuses)

    st.title("QueueIQ Unified Workspace")
    st.caption(
        "Use the repo root as the common entry point. Run `python app.py` to launch the full stack, "
        "or `streamlit run app.py` to open this landing page by itself."
    )

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Product modules", len(QUEUEIQ_MODULES))
    metric_col2.metric("Detected live services", live_services)
    metric_col3.metric("Single launcher", ".\\.venv\\Scripts\\python.exe app.py")

    home_tab, services_tab, setup_tab = st.tabs(["Overview", "Services", "Root Setup"])

    with home_tab:
        st.subheader("One project, two operational experiences")
        st.write(
            "QueueIQ uses the repo root as the shared landing area. Each module keeps its own code, "
            "while one root launcher can start the full experience for demos and local testing."
        )

        st.markdown("### QueueControl dashboard views")
        queue_dashboard_cols = st.columns(3)
        queue_dashboard_links = (
            ("Patient View", f"http://{LOCAL_HOST}:{PATIENT_DASHBOARD_PORT}?view=patient", "Patient-facing live queue view"),
            ("Reception View", f"http://{LOCAL_HOST}:{PATIENT_DASHBOARD_PORT}?view=reception", "Front-desk intake and queue supervision"),
            ("Manager View", f"http://{LOCAL_HOST}:{PATIENT_DASHBOARD_PORT}?view=manager", "Staffing, prediction, and trend controls"),
        )
        for column, (label, url, description) in zip(queue_dashboard_cols, queue_dashboard_links):
            with column:
                st.link_button(label, url, use_container_width=True)
                st.caption(description)

        for module in QUEUEIQ_MODULES:
            st.markdown(f"### {module.name}")
            left_col, right_col = st.columns([1.3, 1.0])

            with left_col:
                st.write(module.description)
                st.caption(f"Folder: {module.folder}")
                for highlight in module.highlights:
                    st.write(f"- {highlight}")

            with right_col:
                st.markdown(f"**{module.tagline}**")
                for service in module.services:
                    st.link_button(f"Open {service.name}", service.url, use_container_width=True)
                    st.caption(service.description)

        st.subheader("Shared repo direction")
        for note in COMMON_LIBRARY_NOTES:
            st.write(f"- {note}")

    with services_tab:
        st.subheader("Live service status")
        for status in statuses:
            badge = "Online" if status.reachable else "Offline"
            tone = st.success if status.reachable else st.warning
            tone(f"{status.module_name} - {status.service_name}: {badge} ({status.detail})")
            st.caption(status.url)

    with setup_tab:
        st.subheader("Run the full stack from the repo root")
        st.code("python -m venv .venv\n.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt\ncd Chatbot\\frontend\nnpm install\ncd ..\\..\n.\\.venv\\Scripts\\python.exe app.py", language="bash")
        st.write(
            "The root launcher starts Chatbot frontend/backend plus the unified QueueControl dashboard "
            "using the same Python environment."
        )

        chatbot_col, queue_col = st.columns(2)

        with chatbot_col:
            st.markdown("### Chatbot")
            st.code("\n".join(QUEUEIQ_MODULES[0].run_steps), language="bash")

        with queue_col:
            st.markdown("### QueueControl")
            st.code("\n".join(QUEUEIQ_MODULES[1].run_steps), language="bash")

        st.info(
            "Keep one root `.venv` as the shared Python environment. The module-level `.venv` folders "
            "can be removed later after you confirm the root launcher works for your workflow."
        )


def main() -> int:

    DATABASE_URL = os.getenv("DATABASE_URL")
    print(f"Connecting to database at: {DATABASE_URL}")
    
    if _is_running_under_streamlit():
        render_workspace_page()
        return 0
    return run_workspace_launcher()


if __name__ == "__main__":
    raise SystemExit(main())







