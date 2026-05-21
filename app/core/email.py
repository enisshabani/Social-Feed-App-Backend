import logging
import uuid
import mailtrap as mt

logger = logging.getLogger(__name__)

# MAILTRAP CONFIG
# Këshillë: Në produksion mbaje këtë token në .env dhe importoje përmes settings!
MAILTRAP_TOKEN = "97a4ccc34a82bb6d787d89eb6c41a306"
SENDER_EMAIL = "hello@demomailtrap.co"
SENDER_NAME = "KaPak App"

def _send_email(to_email: str, subject: str, html_content: str, category: str):
    """
    Funksioni ndihmës bazë për të komunikuar me Mailtrap SDK.
    """
    try:
        mail = mt.Mail(
            sender=mt.Address(email=SENDER_EMAIL, name=SENDER_NAME),
            to=[mt.Address(email=to_email)],
            subject=subject,
            html=html_content,
            category=category,
        )
        client = mt.MailtrapClient(token=MAILTRAP_TOKEN)
        client.send(mail)
        logger.info(f"Email sent successfully to {to_email} (Category: {category})")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}. Error: {e}")

async def send_reset_password_email(email_to: str, reset_token: str):
    """
    Dërgon emailin reale me token-in për reset fjalëkalimi duke përdorur Mailtrap.
    """
    reset_url = f"http://localhost:5173/reset-password?token={reset_token}"

    html_content = f"""
    <h2>Përshëndetje!</h2>
    <p>Keni kërkuar rikthimin e fjalëkalimit për llogarinë tuaj në platformën <b>KaPak</b>.</p>
    <p>Kilkoni linkun më poshtë për ta krijuar fjalëkalimin e ri:</p>
    <a href="{reset_url}" style="padding: 10px 15px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">Ndërro Fjalëkalimin</a>
    <br><br>
    <p>Nëse nuk keni kërkuar një fjalëkalim të ri, thjesht injorojeni këtë email.</p>
    """
    
    _send_email(email_to, "Rikthe Fjalëkalimin - KaPak", html_content, "Password Reset")

async def send_verification_email(email_to: str, verification_token: str):
    """
    Dërgon emailin e verifikimit të llogarisë.
    """
    verify_url = f"http://localhost:5173/verify-email?token={verification_token}"

    html_content = f"""
    <h2>Mirësevini!</h2>
    <p>Faleminderit që u regjistruat në <b>KaPak</b>.</p>
    <p>Të lutem kliko butonin e mëposhtëm për të verifikuar adresën tënde të emailit:</p>
    <a href="{verify_url}" style="padding: 10px 15px; background-color: #28a745; color: white; text-decoration: none; border-radius: 5px;">Verifiko Llogarinë</a>
    <br><br>
    <p>Nëse nuk jeni regjistruar ju, thjesht injoroni këtë mesazh.</p>
    """
    
    _send_email(email_to, "Verifiko Llogarinë Tënde - KaPak", html_content, "Email Verification")

def create_super_simple_token() -> str:
    # Gjeneron një token të thjeshtë unik si zëvendësues
    return str(uuid.uuid4())
