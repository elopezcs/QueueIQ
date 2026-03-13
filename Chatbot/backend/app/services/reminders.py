from datetime import datetime, timedelta, timezone

from app.config.loader import get_clinic_by_id
from app.services.emailer import send_appointment_reminder_email
from app.storage.repo import AppointmentRepo


class ReminderService:
    def __init__(self) -> None:
        self.repo = AppointmentRepo()

    def send_due_reminders(self) -> list[dict[str, str | bool]]:
        window_end = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        reminders = self.repo.list_due_reminders(window_end)
        results: list[dict[str, str | bool]] = []

        for appointment in reminders:
            clinic = get_clinic_by_id(appointment['clinic_id'])
            clinic_name = clinic['name'] if clinic else appointment['clinic_id']
            delivery = send_appointment_reminder_email(
                to_email=appointment['email'],
                full_name=appointment['full_name'],
                clinic_name=clinic_name,
                scheduled_for=appointment['scheduled_for'],
            )
            status = 'sent' if delivery['sent'] else 'queued'
            detail = f"provider={delivery['provider']}"
            self.repo.log_notification(
                appointment_id=appointment['appointment_id'],
                notification_type='reminder_15m',
                scheduled_for=appointment['scheduled_for'],
                status=status,
                detail=detail,
            )
            results.append({
                'appointment_id': appointment['appointment_id'],
                'email': appointment['email'],
                'status': status,
                'provider': str(delivery['provider']),
            })
        return results
