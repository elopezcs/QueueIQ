from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

from app.services.appointment_email_helper import (  # noqa: E402
    build_appointment_confirmation_email_html,
    write_appointment_email_preview,
)


def main() -> None:
    """Generate a local demo appointment confirmation email preview.

    Output path:
      Chatbot/backend/reports/email_previews/appointment_confirmation_demo.html

    Regenerate:
      python scripts/generate_demo_appointment_email.py
    """
    html = build_appointment_confirmation_email_html(
        patient_first_name="Alex",
        patient_last_name="Johnson",
        clinic_name="QueueIQ Downtown Walk-In Clinic",
        appointment_date="May 2, 2026",
        appointment_time="10:30 AM",
        clinic_address="123 King Street West, Kitchener, ON",
        visit_type="General Consultation",
    )

    output_path = BACKEND_ROOT / "reports" / "email_previews" / "appointment_confirmation_demo.html"
    written_path = write_appointment_email_preview(html=html, output_path=output_path)
    relative_path = written_path.relative_to(BACKEND_ROOT)

    print(f"Demo appointment email preview generated: {relative_path}")
    print("To regenerate, run: python scripts/generate_demo_appointment_email.py")


if __name__ == "__main__":
    main()
