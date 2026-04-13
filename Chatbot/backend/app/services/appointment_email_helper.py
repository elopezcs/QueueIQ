"""Helper utilities for generating a demo appointment confirmation email preview."""

from __future__ import annotations

import os
from html import escape
from pathlib import Path
import secrets
import smtplib
import string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


CODE_ALPHABET = string.ascii_uppercase + string.digits
BOOKING_PREVIEW_DIR = Path(__file__).resolve().parents[2] / "reports" / "email_previews" / "bookings"


def generate_confirmation_code(length: int = 6) -> str:
    """Generate an uppercase alphanumeric confirmation code."""
    if length <= 0:
        raise ValueError("length must be greater than 0")
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def build_appointment_confirmation_email_html(
    patient_first_name: str,
    patient_last_name: str,
    clinic_name: str,
    appointment_date: str,
    appointment_time: str,
    clinic_address: str,
    visit_type: str,
    confirmation_code: str | None = None,
) -> str:
    """Return a complete HTML email preview for a confirmed appointment."""
    code = confirmation_code or generate_confirmation_code()
    patient_full_name = f"{patient_first_name} {patient_last_name}".strip()

    patient_first_name_safe = escape(patient_first_name)
    patient_full_name_safe = escape(patient_full_name)
    clinic_name_safe = escape(clinic_name)
    appointment_date_safe = escape(appointment_date)
    appointment_time_safe = escape(appointment_time)
    clinic_address_safe = escape(clinic_address)
    visit_type_safe = escape(visit_type)
    confirmation_code_safe = escape(code)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>QueueIQ Appointment Confirmation</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f7fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f4f7fb;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background-color:#ffffff;border:1px solid #e5e7eb;border-radius:14px;overflow:hidden;">
          <tr>
            <td style="background-color:#0b5ed7;padding:22px 28px;">
              <div style="font-size:12px;letter-spacing:1.3px;color:#cfe2ff;font-weight:bold;text-transform:uppercase;">QueueIQ</div>
              <div style="font-size:20px;line-height:1.3;color:#ffffff;font-weight:700;margin-top:6px;">Your Appointment is Confirmed</div>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 28px;">
              <p style="margin:0 0 14px 0;font-size:15px;line-height:1.6;">Hello {patient_first_name_safe},</p>
              <p style="margin:0 0 22px 0;font-size:15px;line-height:1.6;">Thank you for booking with QueueIQ. Your appointment has been confirmed and we look forward to seeing you.</p>

              <div style="border:1px solid #dbe6f5;border-radius:10px;background-color:#f8fbff;padding:16px 18px;">
                <div style="font-size:15px;font-weight:700;margin:0 0 12px 0;color:#0f172a;">Appointment Details</div>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="font-size:14px;line-height:1.5;">
                  <tr>
                    <td style="padding:5px 0;color:#64748b;width:42%;">Patient</td>
                    <td style="padding:5px 0;color:#0f172a;font-weight:600;">{patient_full_name_safe}</td>
                  </tr>
                  <tr>
                    <td style="padding:5px 0;color:#64748b;">Clinic</td>
                    <td style="padding:5px 0;color:#0f172a;font-weight:600;">{clinic_name_safe}</td>
                  </tr>
                  <tr>
                    <td style="padding:5px 0;color:#64748b;">Appointment Date</td>
                    <td style="padding:5px 0;color:#0f172a;font-weight:600;">{appointment_date_safe}</td>
                  </tr>
                  <tr>
                    <td style="padding:5px 0;color:#64748b;">Appointment Time</td>
                    <td style="padding:5px 0;color:#0f172a;font-weight:600;">{appointment_time_safe}</td>
                  </tr>
                  <tr>
                    <td style="padding:5px 0;color:#64748b;">Clinic Address</td>
                    <td style="padding:5px 0;color:#0f172a;font-weight:600;">{clinic_address_safe}</td>
                  </tr>
                  <tr>
                    <td style="padding:5px 0;color:#64748b;">Visit Type</td>
                    <td style="padding:5px 0;color:#0f172a;font-weight:600;">{visit_type_safe}</td>
                  </tr>
                  <tr>
                    <td style="padding:5px 0;color:#64748b;">Confirmation Number</td>
                    <td style="padding:5px 0;color:#0b5ed7;font-weight:700;letter-spacing:0.8px;">{confirmation_code_safe}</td>
                  </tr>
                </table>
              </div>

              <p style="margin:18px 0 8px 0;font-size:14px;line-height:1.6;"><strong>Arrival instructions:</strong> Please arrive 10 minutes early and bring a valid photo ID and your health card.</p>
              <p style="margin:0 0 20px 0;font-size:14px;line-height:1.6;"><strong>Need to change your appointment?</strong> If you need to reschedule or cancel, please contact the clinic as soon as possible.</p>

              <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 18px 0;">
                <tr>
                  <td style="padding:0 10px 10px 0;">
                    <a href="#" style="display:inline-block;padding:10px 14px;background-color:#0b5ed7;color:#ffffff;text-decoration:none;border-radius:6px;font-size:13px;font-weight:600;">View Appointment</a>
                  </td>
                  <td style="padding:0 10px 10px 0;">
                    <a href="#" style="display:inline-block;padding:10px 14px;background-color:#eef2ff;color:#1e3a8a;text-decoration:none;border-radius:6px;font-size:13px;font-weight:600;">Reschedule</a>
                  </td>
                  <td style="padding:0 0 10px 0;">
                    <a href="#" style="display:inline-block;padding:10px 14px;background-color:#f1f5f9;color:#0f172a;text-decoration:none;border-radius:6px;font-size:13px;font-weight:600;">Contact Clinic</a>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 4px 0;font-size:14px;line-height:1.6;">We appreciate the opportunity to support your care.</p>
              <p style="margin:0;font-size:14px;line-height:1.6;">Warm regards,<br />QueueIQ Care Team</p>
            </td>
          </tr>
          <tr>
            <td style="background-color:#f8fafc;padding:14px 28px;border-top:1px solid #e5e7eb;">
              <p style="margin:0;font-size:12px;color:#64748b;line-height:1.5;">This is an automated message from QueueIQ. Please do not reply directly to this email.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def write_appointment_email_preview(html: str, output_path: Path | str) -> Path:
    """Write HTML preview content to disk and return the resulting path."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


def build_booking_preview_output_path(appointment_id: str) -> Path:
    """Return the deterministic HTML preview path for a booked appointment."""
    cleaned_appointment_id = appointment_id.strip()
    if not cleaned_appointment_id:
        raise ValueError("appointment_id is required")
    filename = f"appointment_confirmation_{cleaned_appointment_id}.html"
    return BOOKING_PREVIEW_DIR / filename


def send_appointment_confirmation_email(
    recipient_email: str,
    patient_first_name: str,
    patient_last_name: str,
    clinic_name: str,
    appointment_date: str,
    appointment_time: str,
    clinic_address: str,
    visit_type: str,
    confirmation_code: str | None = None,
) -> str | None:
    """
    Send the appointment confirmation HTML via Gmail SMTP.

    Required .env variables:
    - QUEUEIQ_EMAIL_ENABLED=true  (feature flag; any other value skips sending)
    - QUEUEIQ_EMAIL_SENDER=<gmail address>
    - QUEUEIQ_EMAIL_APP_PASSWORD=<gmail app password>
    """
    # Keep booking flow safe: if disabled, skip without raising.
    feature_enabled = (os.getenv("QUEUEIQ_EMAIL_ENABLED") or "").strip().lower() == "true"
    if not feature_enabled:
        print("Email sending is disabled via feature flag")
        return None

    recipient = (recipient_email or "").strip()
    if not recipient:
        print("Email sending skipped: recipient email is missing")
        return None

    sender = (os.getenv("QUEUEIQ_EMAIL_SENDER") or "").strip()
    app_password = (os.getenv("QUEUEIQ_EMAIL_APP_PASSWORD") or "").strip()
    if not sender or not app_password:
        print("Email sending skipped: QUEUEIQ_EMAIL_SENDER or QUEUEIQ_EMAIL_APP_PASSWORD is missing")
        return None

    resolved_confirmation_code = confirmation_code or generate_confirmation_code()
    html_body = build_appointment_confirmation_email_html(
        patient_first_name=patient_first_name,
        patient_last_name=patient_last_name,
        clinic_name=clinic_name,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        clinic_address=clinic_address,
        visit_type=visit_type,
        confirmation_code=resolved_confirmation_code,
    )

    message = MIMEMultipart("alternative")
    message["Subject"] = "QueueIQ Appointment Confirmation"
    message["From"] = "QueueIQ Care Team <" + sender + ">"
    message["To"] = recipient
    message.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(sender, app_password)
            smtp.sendmail(sender, [recipient], message.as_string())
    except Exception as exc:
        print(f"Email sending failed: {exc}")
        return None

    return resolved_confirmation_code
