import logging
import uuid
import mailtrap as mt

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def _send_email(to_email: str, subject: str, html_content: str, category: str):
    """
    Funksioni ndihmës bazë për të komunikuar me Mailtrap SDK.
    """
    try:
        if not settings.MAILTRAP_TOKEN:
            logger.warning("MAILTRAP_TOKEN is not configured; email was not sent.")
            return

        mail = mt.Mail(
            sender=mt.Address(email=settings.MAILTRAP_SENDER_EMAIL, name=settings.MAIL_FROM_NAME),
            to=[mt.Address(email=to_email)],
            subject=subject,
            html=html_content,
            category=category,
        )
        client = mt.MailtrapClient(token=settings.MAILTRAP_TOKEN)
        client.send(mail)
        logger.info(f"Email sent successfully to {to_email} (Category: {category})")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}. Error: {e}")

async def send_reset_password_email(email_to: str, reset_token: str):
    """
    Dërgon emailin reale me token-in për reset fjalëkalimi duke përdorur Mailtrap.
    """
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    html_content = f"""
    <h2>Përshëndetje!</h2>
    <p>Keni kërkuar rikthimin e fjalëkalimit për llogarinë tuaj në platformën <b>KaPak</b>.</p>
    <p>Kilkoni linkun më poshtë për ta krijuar fjalëkalimin e ri:</p>
    <a href="{reset_url}" style="padding: 10px 15px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">Ndërro Fjalëkalimin</a>
    <br><br>
    <p>Nëse nuk keni kërkuar një fjalëkalim të ri, thjesht injorojeni këtë email.</p>
    """
    
    _send_email(email_to, "Rikthe Fjalëkalimin - KaPak", html_content, "Password Reset")


def create_super_simple_token() -> str:
    # Gjeneron një token të thjeshtë unik si zëvendësues
    return str(uuid.uuid4())
