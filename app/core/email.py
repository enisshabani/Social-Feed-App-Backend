import logging
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

mail_config = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM or "noreply@kapak.com",
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

async def send_reset_password_email(email_to: str, reset_token: str):
    """
    Dërgon emailin reale me token-in për reset fjalëkalimi.
    """
    if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
        logger.warning("Email credentials are not set. The email will NOT be sent.")
        # Në zhvillim, mund t'i bësh print linkut në konsolë që ta shohësh pa pasur email real.
        print(f"\n[DEV PREVIEW: Email do dërgohej] \nTo: {email_to} \nReset token: {reset_token}\nUrl: http://localhost:5173/reset-password?token={reset_token}\n")
        return

    # Linku pritet të kapet nga faqja jote e Frontend React (kur ti e krijon ate)
    reset_url = f"http://localhost:5173/reset-password?token={reset_token}"

    html_content = f"""
    <h2>Përshëndetje!</h2>
    <p>Keni kërkuar rikthimin e fjalëkalimit për llogarinë tuaj në platformën <b>KaPak</b>.</p>
    <p>Kilkoni linkun më poshtë (ose kopjoni në shfletues) për ta krijuar fjalëkalimin e ri:</p>
    <a href="{reset_url}">{reset_url}</a>
    <br><br>
    <p>Nëse nuk keni kërkuar një fjalëkalim të ri, thjesht injorojeni këtë email.</p>
    """

    message = MessageSchema(
        subject="Rikthe Fjalëkalimin - KaPak",
        recipients=[email_to],
        body=html_content,
        subtype=MessageType.html
    )

    try:
        fm = FastMail(mail_config)
        await fm.send_message(message)
        logger.info(f"Reset email sent successfully to {email_to}")
    except Exception as e:
        logger.error(f"Failed to send email to {email_to}. Error: {e}")

def create_super_simple_token() -> str:
    # Gjeneron një token të thjeshtë unik si zëvendësues (shumë i gjerë dhe unik).
    # Idealisht, duhet të ruhet te DB si p.sh tabela (password_resets).
    return str(uuid.uuid4())
