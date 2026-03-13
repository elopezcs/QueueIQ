import logging
import smtplib
from email.message import EmailMessage

from app.core.settings import settings

logger = logging.getLogger('queueiq.email')


class EmailDeliveryResult(dict):
    sent: bool
    provider: str


def send_email(to_email: str, subject: str, body: str) -> dict[str, str | bool]:
    if not settings.smtp_host:
        logger.warning('SMTP is not configured. Email to %s was not sent. Subject=%s Body=%s', to_email, subject, body)
        return {'sent': False, 'provider': 'log'}

    msg = EmailMessage()
    msg['From'] = settings.email_sender
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)

    return {'sent': True, 'provider': 'smtp'}


def send_otp_email(to_email: str, full_name: str, code: str, expires_in_minutes: int) -> dict[str, str | bool]:
    subject = 'Your QueueIQ login code'
    body = (
        f'Hello {full_name},\n\n'
        f'Your QueueIQ one-time login code is: {code}\n\n'
        f'This code expires in {expires_in_minutes} minutes.\n\n'
        'If you did not request this code, you can ignore this email.'
    )
    return send_email(to_email, subject, body)


def send_appointment_reminder_email(to_email: str, full_name: str, clinic_name: str, scheduled_for: str) -> dict[str, str | bool]:
    subject = 'QueueIQ appointment reminder'
    body = (
        f'Hello {full_name},\n\n'
        f'This is a reminder that your appointment with {clinic_name} is scheduled for {scheduled_for}.\n'
        'Your appointment time is within the next 15 minutes.\n\n'
        'If your plans changed, please contact the clinic as soon as possible.'
    )
    return send_email(to_email, subject, body)
